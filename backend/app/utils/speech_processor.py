# backend/app/utils/speech_processor.py
from typing import Dict, List, Optional, BinaryIO, Union, Any
from fastapi import HTTPException
from pydantic import BaseModel, Field
from datetime import datetime
import asyncio
import logging
import uuid
import io
import os
import base64
import numpy as np
from concurrent.futures import ThreadPoolExecutor
from pydub import AudioSegment
from app.config.language_metadata import LanguageMetadata
from app.services.bhashini_service import BhashiniService
import json

logger = logging.getLogger(__name__)

class AudioConfig(BaseModel):
    """Audio configuration settings"""
    sample_rate: int = Field(default=16000, description="Sample rate in Hz")
    channels: int = Field(default=1, description="Number of audio channels")
    format: str = Field(default="wav", description="Audio format")
    chunk_size: int = Field(default=4096, description="Streaming chunk size")
    max_duration: int = Field(default=300, description="Maximum audio duration in seconds")
    min_duration: float = Field(default=0.5, description="Minimum audio duration in seconds")

class ProcessedSpeech(BaseModel):
    """Model for processed speech results following our flow"""
    original_text: str = Field(..., description="Text in original language")
    english_text: Optional[str] = Field(None, description="Translated English text")
    language_code: str
    language_name: str
    confidence: float
    duration: float
    timestamp: datetime
    metadata: Dict = {}

class AudioProcessor:
    """Handles core audio processing functionality"""
    def __init__(self, config: AudioConfig):
        self.config = config
        self.thread_pool = ThreadPoolExecutor(max_workers=2)
        self._setup_temp_directory()

    def _setup_temp_directory(self):
        """Setup temporary directory for audio processing"""
        self.temp_dir = os.path.join(os.getcwd(), 'temp', 'audio')
        os.makedirs(self.temp_dir, exist_ok=True)

    async def validate_and_convert(self, audio_data: bytes) -> tuple[bytes, Dict]:
        """Validate and convert audio to required format"""
        try:
            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                self.thread_pool,
                self._process_audio,
                audio_data
            )
        except Exception as e:
            logger.error(f"Audio processing error: {str(e)}")
            raise HTTPException(status_code=400, detail="Invalid audio data")

    def _process_audio(self, audio_data: bytes) -> tuple[bytes, Dict]:
        """Process audio data synchronously"""
        temp_path = os.path.join(self.temp_dir, f"{uuid.uuid4()}.wav")
        try:
            # Write audio data
            with open(temp_path, 'wb') as f:
                f.write(audio_data)

            # Load and validate audio
            audio = AudioSegment.from_file(temp_path)
            
            # Validate duration
            duration = len(audio) / 1000.0
            if not (self.config.min_duration <= duration <= self.config.max_duration):
                raise ValueError(f"Audio duration {duration}s out of range")

            # Convert to required format
            audio = self._convert_audio(audio)

            # Get audio metadata
            metadata = {
                'duration': duration,
                'sample_rate': audio.frame_rate,
                'channels': audio.channels,
                'sample_width': audio.sample_width,
                'frame_count': len(audio.get_array_of_samples())
            }

            # Export to bytes
            output = io.BytesIO()
            audio.export(output, format=self.config.format)
            return output.getvalue(), metadata

        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def _convert_audio(self, audio: AudioSegment) -> AudioSegment:
        """Convert audio to required format"""
        if audio.frame_rate != self.config.sample_rate:
            audio = audio.set_frame_rate(self.config.sample_rate)
        if audio.channels != self.config.channels:
            audio = audio.set_channels(self.config.channels)
        return audio

class SpeechProcessor:
    """Main speech processor following our flow:
    Input Path: Audio/Text → Native STT/Text → English Translation → Return ProcessedSpeech
    Output Path: English Text → Native Translation → TTS → Return ProcessedResponse
    """
    def __init__(self):
        self.audio_config = AudioConfig()
        self.audio_processor = AudioProcessor(self.audio_config)
        self.bhashini_service = BhashiniService()
        
        # Async resources
        self.processing_semaphore = asyncio.Semaphore(5)
        self.stream_buffers: Dict[str, io.BytesIO] = {}
        
        # Cache for session metadata
        self.session_metadata: Dict[str, Dict] = {}
        self.initialized = False

    async def initialize(self):
        """Initialize services with proper error handling"""
        try:
            if not self.initialized:
                await self.bhashini_service.initialize()
                self.initialized = True
                logger.info("Speech processor initialized successfully")
        except Exception as e:
            logger.error(f"Speech processor initialization failed: {str(e)}", exc_info=True)
            raise RuntimeError(f"Initialization failed: {str(e)}")

    async def process_input(
        self,
        content: Union[str, bytes],
        source_language: str,
        is_audio: bool = False,
        session_id: Optional[str] = None,
        stream: bool = False
    ) -> ProcessedSpeech:
        """Process input with enhanced flow tracking"""
        if not self.initialized:
            await self.initialize()

        async with self.processing_semaphore:
            try:
                start_time = datetime.utcnow()
                session_id = session_id or str(uuid.uuid4())
                
                logger.info(f"""
    === Input Processing Started ===
    Session ID: {session_id}
    Source Language: {source_language}
    Input Type: {'Audio' if is_audio else 'Text'}
    Stream Mode: {stream}
    Start Time: {start_time.isoformat()}
                """)

                detected_language = source_language
                audio_metadata = {}

                # Audio Processing Phase
                if is_audio:
                    logger.info("=== Starting Audio Processing Phase ===")
                    processed_audio, audio_metadata = await self.audio_processor.validate_and_convert(content)
                    logger.info(f"""
    Audio Processing Results:
    - Duration: {audio_metadata['duration']}s
    - Sample Rate: {audio_metadata.get('sample_rate')}
    - Channels: {audio_metadata.get('channels')}
                    """)

                    stt_result = await self.bhashini_service.speech_to_text(
                        processed_audio,
                        source_language=source_language
                    )
                    original_text = self._extract_text_from_stt(stt_result)
                    
                    if not original_text:
                        raise ValueError("STT extraction failed")
                    
                    logger.info(f"""
    Speech-to-Text Results:
    - Text Length: {len(original_text)}
    - Preview: '{original_text[:100]}...'
                    """)
                else:
                    original_text = content
                    logger.info(f"Text Input Length: {len(original_text)}")

                # Translation Phase
                english_text = original_text
                english_source = "original"
                translation_metrics = {}

                if source_language != "en":
                    logger.info("=== Starting Translation Phase ===")
                    translation_result = await self.translate_text(
                        text=original_text,
                        source_language=source_language,
                        target_language="en"
                    )
                    
                    if "error" not in translation_result:
                        english_text = translation_result["translated_text"]
                        english_source = "translation"
                        translation_metrics = translation_result.get("metadata", {})
                        
                        logger.info(f"""
    Translation Results:
    - Success: True
    - Original Length: {len(original_text)}
    - Translated Length: {len(english_text)}
    - Confidence: {translation_result.get('confidence', 'N/A')}
                        """)
                    else:
                        logger.warning(f"Translation failed: {translation_result['error']}")

                # Response Creation Phase
                processing_path = [
                    "audio_processing" if is_audio else "text_input",
                    "stt" if is_audio else None,
                    "translation" if source_language != "en" else None
                ]
                
                response = ProcessedSpeech(
                    original_text=original_text,
                    english_text=english_text,
                    language_code=source_language,
                    language_name=LanguageMetadata.get_language_name(source_language),
                    confidence=translation_metrics.get('confidence', 1.0),
                    duration=audio_metadata.get('duration', 0.0),
                    timestamp=datetime.utcnow(),
                    metadata={
                        "session_id": session_id,
                        "input_type": "audio" if is_audio else "text",
                        "audio_metadata": audio_metadata,
                        "source_language": source_language,
                        "detected_language": detected_language,
                        "english_text_source": english_source,
                        "processing_path": processing_path,
                        "translation_metrics": translation_metrics,
                        "timestamps": {
                            "start": start_time.isoformat(),
                            "completion": datetime.utcnow().isoformat()
                        }
                    }
                )

                logger.info(f"""
    === Input Processing Completed ===
    Session: {session_id}
    Duration: {(datetime.utcnow() - start_time).total_seconds()}s
    Processing Path: {' -> '.join(filter(None, processing_path))}
                """)

                return response

            except Exception as e:
                logger.error(f"""
    === Critical Input Processing Error ===
    Session ID: {session_id}
    Error: {str(e)}
    Source Language: {source_language}
    Processing Stage: {locals().get('current_stage', 'unknown')}
                """, exc_info=True)
                raise HTTPException(
                    status_code=500,
                    detail={
                        "error": str(e),
                        "session_id": session_id,
                        "language": source_language
                    }
                )


    async def process_output(
        self,
        input_text: str,
        english_text: Optional[str],
        target_language: str,
        generate_speech: bool = True
    ) -> Dict:
        """Process output with enhanced flow tracking"""
        try:
            start_time = datetime.utcnow()
            logger.info(f"""
    === Output Processing Started ===
    Target Language: {target_language}
    Generate Speech: {generate_speech}
    Input Text Length: {len(input_text)}
    English Text Present: {english_text is not None}
    Start Time: {start_time.isoformat()}
            """)

            # Translation Phase
            text_to_translate = english_text or input_text
            translated_text = text_to_translate
            translation_success = False
            confidence = 1.0
            translation_metrics = {}

            if target_language != "en":
                logger.info("=== Starting Translation Phase ===")
                translation_result = await self.bhashini_service.translate_text(
                    text=text_to_translate,
                    source_language="en",
                    target_language=target_language,
                    preserve_medical_terms=True
                )

                if "pipelineResponse" in translation_result:
                    pipeline_response = translation_result["pipelineResponse"][0]
                    if pipeline_response.get("output"):
                        translated_text = pipeline_response["output"][0]["target"]
                        confidence = pipeline_response.get("confidence", 1.0)
                        translation_success = True
                        translation_metrics = {
                            "preserved_terms": translation_result.get("preservedTerms", []),
                            "pipeline_id": translation_result.get("pipelineId"),
                            "service_id": translation_result.get("serviceId")
                        }
                        
                        logger.info(f"""
    Translation Results:
    - Success: True
    - Text Length: {len(translated_text)}
    - Confidence: {confidence}
    - Preserved Terms: {len(translation_metrics['preserved_terms'])}
                        """)

            # Speech Generation Phase
            audio_data = None
            tts_success = False
            tts_metrics = {}

            if generate_speech:
                logger.info(f"=== Starting Speech Generation Phase ===")
                tts_result = await self.bhashini_service.text_to_speech(
                    text=translated_text,
                    target_language=target_language,
                    gender="female"
                )

                if tts_result and "audio_data" in tts_result:
                    audio_data = tts_result["audio_data"]
                    tts_success = True
                    tts_metrics = {
                        "audio_size": len(audio_data),
                        "format": "wav",
                        "gender": "female"
                    }
                    
                    logger.info(f"""
    Speech Generation Results:
    - Success: True
    - Audio Size: {tts_metrics['audio_size']} bytes
    - Format: {tts_metrics['format']}
                    """)

            # Create Enhanced Response
            completion_time = datetime.utcnow()
            processing_duration = (completion_time - start_time).total_seconds()

            response = {
                "translated_text": translated_text,
                "audio_data": audio_data,
                "language": target_language,
                "confidence": confidence,
                "metadata": {
                    "source_text": input_text,
                    "english_text": english_text,
                    "translation_status": {
                        "success": translation_success,
                        "confidence": confidence,
                        "metrics": translation_metrics
                    },
                    "tts_status": {
                        "success": tts_success,
                        "metrics": tts_metrics
                    },
                    "processing_path": {
                        "translation": target_language != "en",
                        "tts": generate_speech,
                        "flow": "translation_tts" if target_language != "en" else "direct_tts"
                    },
                    "performance": {
                        "start_time": start_time.isoformat(),
                        "completion_time": completion_time.isoformat(),
                        "duration_seconds": processing_duration
                    },
                    "language_info": {
                        "code": target_language,
                        "name": LanguageMetadata.get_language_name(target_language),
                        "script": LanguageMetadata.get_language_metadata(target_language).get("script")
                    }
                }
            }

            logger.info(f"""
    === Output Processing Completed ===
    Duration: {processing_duration}s
    Flow: {response['metadata']['processing_path']['flow']}
    Translation: {'Success' if translation_success else 'Not Required'}
    Speech: {'Generated' if tts_success else 'Not Generated'}
            """)

            return response

        except Exception as e:
            logger.error(f"""
    === Critical Output Processing Error ===
    Target Language: {target_language}
    Error: {str(e)}
    Processing Stage: {locals().get('current_stage', 'unknown')}
            """, exc_info=True)
            raise RuntimeError(f"Output processing failed: {str(e)}")



    async def translate_text(
        self,
        text: str,
        source_language: str,
        target_language: str,
        max_retries: int = 3
    ) -> Dict:
        """Translate text with retries and error handling"""
        retry_count = 0
        last_error = None

        # Input validation
        if not text or not text.strip():
            logger.error("Empty text provided for translation")
            return {
                "translated_text": text,
                "confidence": 0.0,
                "error": "Empty input text",
                "metadata": {
                    "timestamp": datetime.utcnow().isoformat()
                }
            }

        # Language validation
        if not LanguageMetadata.is_language_supported(source_language) or \
        not LanguageMetadata.is_language_supported(target_language):
            logger.error(f"Unsupported language pair: {source_language} -> {target_language}")
            return {
                "translated_text": text,
                "confidence": 0.0,
                "error": "Unsupported language combination",
                "metadata": {
                    "source_language": source_language,
                    "target_language": target_language,
                    "timestamp": datetime.utcnow().isoformat()
                }
            }

        while retry_count < max_retries:
            try:
                logger.info(f"Translation attempt {retry_count + 1} - {source_language} to {target_language}")
                logger.debug(f"Input text: {text[:100]}...")

                # Call Bhashini service with payload validation
                translation = await self.bhashini_service.translate_text(
                    text=text,
                    source_language=source_language,
                    target_language=target_language,
                    preserve_medical_terms=True
                )

                # Extract and validate translation
                translated_text = self._extract_translation(translation)
                if translated_text:
                    logger.info(f"Translation successful - Length: {len(translated_text)} chars")
                    return {
                        "translated_text": translated_text,
                        "confidence": translation.get("confidence", 1.0),
                        "metadata": {
                            "source_text": text,
                            "source_language": source_language,
                            "target_language": target_language,
                            "retry_count": retry_count,
                            "timestamp": datetime.utcnow().isoformat(),
                            "preserved_terms": translation.get("preservedTerms", []),
                            "service_id": translation.get("serviceId", "default")
                        }
                    }

                # Handle empty translation
                retry_count += 1
                last_error = "Empty translation result"
                logger.warning(f"Empty translation on attempt {retry_count}")
                
                if retry_count < max_retries:
                    await asyncio.sleep(0.5 * retry_count)
                    continue

            except Exception as e:
                retry_count += 1
                last_error = str(e)
                logger.warning(
                    f"Translation attempt {retry_count} failed: {last_error}",
                    exc_info=True
                )

                if retry_count < max_retries:
                    await asyncio.sleep(0.5 * retry_count)
                    continue

        # Return fallback response after all retries
        logger.error(f"Translation failed after {max_retries} attempts")
        return {
            "translated_text": text,
            "confidence": 0.0,
            "error": last_error,
            "metadata": {
                "source_text": text,
                "source_language": source_language,
                "target_language": target_language,
                "retry_count": retry_count,
                "last_error": last_error,
                "timestamp": datetime.utcnow().isoformat(),
                "fallback": True
            }
        }


    def _extract_text_from_stt(self, stt_result: Dict) -> str:
        """Extract text from STT response with validation"""
        try:
            if isinstance(stt_result, dict):
                if "text" in stt_result:
                    return stt_result["text"]
                elif "pipelineResponse" in stt_result:
                    pipeline_response = stt_result["pipelineResponse"]
                    if pipeline_response and isinstance(pipeline_response, list):
                        response_data = pipeline_response[0]
                        if "output" in response_data and response_data["output"]:
                            text = response_data["output"][0].get("source", "")
                            if text:
                                return text
            logger.warning("Failed to extract text from STT response")
            return ""
        except Exception as e:
            logger.error(f"STT text extraction error: {str(e)}")
            return ""

    def _extract_translation(self, translation: Dict) -> str:
        """Extract translated text from translation response with validation"""
        try:
            logger.debug(f"Processing translation response: {json.dumps(translation, indent=2)}")
            
            # Validate response structure
            if not isinstance(translation, dict):
                logger.error("Invalid translation response type")
                return ""

            if "pipelineResponse" not in translation:
                logger.error("Missing pipelineResponse in translation")
                return ""

            pipeline_resp = translation["pipelineResponse"]
            
            # Validate pipeline response
            if not pipeline_resp or not isinstance(pipeline_resp, list):
                logger.error("Invalid pipeline response format")
                return ""

            first_response = pipeline_resp[0]
            logger.debug(f"Pipeline first response: {json.dumps(first_response, indent=2)}")

            # Extract and validate output
            if not first_response or "output" not in first_response:
                logger.error("Missing output in pipeline response")
                return ""

            outputs = first_response["output"]
            if not outputs or not isinstance(outputs, list):
                logger.error("Invalid outputs format")
                return ""

            first_output = outputs[0]
            if not first_output or "target" not in first_output:
                logger.error("Missing target in output")
                return ""

            # Process translated text
            translated_text = first_output["target"].strip()
            if not translated_text:
                logger.warning("Empty translated text received")
                return ""

            # Log success with metadata
            logger.info(f"Translation extracted successfully:")
            logger.info(f"- Source: {first_output.get('source', 'N/A')}")
            logger.info(f"- Target: {translated_text[:50]}...")
            logger.info(f"- Length: {len(translated_text)} characters")
            logger.info(f"- Task Type: {first_response.get('taskType', 'N/A')}")

            return translated_text

        except Exception as e:
            logger.error(
                "Translation extraction failed",
                extra={
                    "error": str(e),
                    "response_type": type(translation).__name__,
                    "has_pipeline": "pipelineResponse" in translation if isinstance(translation, dict) else False
                },
                exc_info=True
            )
            return ""


    async def cleanup(self):
        """Cleanup resources with error handling"""
        try:
            # Cleanup stream buffers
            for buffer in self.stream_buffers.values():
                try:
                    buffer.close()
                except Exception as e:
                    logger.error(f"Buffer cleanup error: {str(e)}")
            self.stream_buffers.clear()
            
            # Cleanup session metadata
            self.session_metadata.clear()
            
            # Cleanup services
            await self.bhashini_service.cleanup()
            
            # Cleanup thread pool
            self.audio_processor.thread_pool.shutdown()
            
            logger.info("Speech processor cleanup completed successfully")
            
        except Exception as e:
            logger.error(f"Speech processor cleanup error: {str(e)}", exc_info=True)
            raise RuntimeError(f"Cleanup failed: {str(e)}")