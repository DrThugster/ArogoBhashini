# backend/app/routes/speech.py
from fastapi import Form, APIRouter, WebSocket, UploadFile, File, HTTPException, Query, BackgroundTasks
from fastapi.responses import JSONResponse, StreamingResponse
from typing import Optional, List
from pydantic import BaseModel, Field
import logging
from datetime import datetime
import asyncio
import json
from app.utils.speech_processor import SpeechProcessor, ProcessedSpeech
from app.config.language_metadata import LanguageMetadata
from app.utils.response_validator import AIResponseValidator
from app.config.database import redis_client, consultations_collection 
from app.routes.consultation import consultation_manager
from app.routes.websocket import manager, WebSocketMessage, WebSocketResponse, WebSocketDisconnect 
from typing import Dict
from typing import Union 

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize services
speech_processor = SpeechProcessor()
response_validator = AIResponseValidator()

class SpeechRequest(BaseModel):
    """Model for speech processing requests"""
    source_language: Optional[str] = Field(None, description="Source language code")
    target_language: Optional[str] = Field(None, description="Target language code")
    enable_auto_detect: bool = Field(True, description="Enable language auto-detection")
    voice_gender: str = Field("female", description="Preferred voice gender")
    voice_style: Optional[str] = None
    stream: bool = Field(False, description="Enable streaming response")
    preserve_medical_terms: bool = Field(True, description="Preserve medical terms in translation")

class StreamingState(BaseModel):
    """Model for streaming state"""
    session_id: str
    buffer: bytes = b""
    chunk_count: int = 0
    is_final: bool = False
    start_time: datetime = Field(default_factory=datetime.utcnow)
    last_activity: datetime = Field(default_factory=datetime.utcnow)
    language_code: str = "en"  # Added for language path
    is_english_path: bool = True  # Added for path separation


# Keep track of streaming sessions
streaming_sessions: Dict[str, StreamingState] = {}

@router.post("/speech-to-text")
async def speech_to_text(
    audio: UploadFile = File(...),
    consultation_id: str = Form(...),
    background_tasks: BackgroundTasks = None
):
    """Convert speech audio to text with separate English/non-English paths"""
    try:
        logger.info("Receiving audio file for speech-to-text conversion")
        
        session = await consultation_manager.get_session(consultation_id)
        if not session:
            raise HTTPException(status_code=404, detail="Consultation session not found")
            
        language_prefs = session["language_preferences"]
        preferred_language = language_prefs.get("preferred", "en")
        auto_detect = language_prefs.get("auto_detect", True)
        
        is_english = preferred_language == "en"
        logger.info(f"Processing speech on {'English' if is_english else 'Translation'} path")
        
        contents = await audio.read()
        if not contents:
            raise ValueError("Empty audio file received")
            
        # Process with language-specific path
        result = await speech_processor.process_input(
            content=contents,
            source_language=preferred_language,
            is_audio=True,
            session_id=consultation_id
        )
        
        # Validate content
        validation = await response_validator.validate_response(
            result.original_text,
            result.language_code
        )
        
        # Update session for auto-detect
        if auto_detect and result.language_code != preferred_language:
            await consultation_manager.update_session(
                consultation_id,
                {"language_preferences": {"preferred": result.language_code}}
            )
            logger.info(f"Updated session language to: {result.language_code}")
        
        if background_tasks:
            background_tasks.add_task(cleanup_audio_file, audio.filename)
        
        # Return language-specific response
        response_data = {
            "status": "success",
            "text": result.original_text,
            "language": {
                "detected": result.language_code,
                "name": result.language_name,
                "confidence": result.confidence,
                "metadata": LanguageMetadata.get_language_metadata(result.language_code)
            },
            "validation": validation[2] if validation[0] else None,
            "metadata": {
                **result.metadata,
                "processing_path": "english_direct" if is_english else "translation",
                "timestamp": datetime.utcnow().isoformat()
            }
        }

        # Add translation info only for non-English
        if not is_english:
            response_data["english_text"] = result.english_text
            
        return JSONResponse(content=response_data)
        
    except Exception as e:
        logger.error(f"Speech to text error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={"error": str(e), "type": "processing_error"}
        )

@router.post("/text-to-speech")
async def text_to_speech(
    text: str,
    target_language: str,
    voice_gender: str = "female",
    voice_style: Optional[str] = None
):
    """Convert text to speech with separate English/non-English paths"""
    try:
        logger.info("Receiving text-to-speech request")
        is_english = target_language == "en"
        logger.info(f"Processing on {'English' if is_english else 'Translation'} path")
        
        if not LanguageMetadata.is_language_supported(target_language):
            raise ValueError(f"Language {target_language} not supported")
        
        voice_config = LanguageMetadata.get_voice_config(target_language)
        
        if voice_gender not in voice_config["available_genders"]:
            voice_gender = voice_config["default_gender"]
            logger.warning(f"Using default gender: {voice_gender}")
        
        if voice_style and voice_style not in voice_config["supported_styles"]:
            voice_style = None
            logger.warning("Requested voice style not supported")
        
        # Process with language-specific path
        result = await speech_processor.process_output(
            input_text=text,
            english_text=text if is_english else None,
            target_language=target_language,
            generate_speech=True
        )
        
        response_data = {
            "status": "success",
            "audio_data": result.get("audio_data"),
            "text": result.get("translated_text") if not is_english else text,
            "language": {
                "code": target_language,
                "name": LanguageMetadata.get_language_name(target_language),
                "metadata": LanguageMetadata.get_language_metadata(target_language)
            },
            "voice": {
                "gender": voice_gender,
                "style": voice_style,
                "config": voice_config
            },
            "metadata": {
                **result.get("metadata", {}),
                "processing_path": "english_direct" if is_english else "translation",
                "timestamp": datetime.utcnow().isoformat()
            }
        }
        
        # Add translation info only for non-English
        if not is_english:
            response_data["original_text"] = text
            
        return JSONResponse(content=response_data)
        
    except Exception as e:
        logger.error(f"Text to speech error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={"error": str(e), "type": "processing_error"}
        )

async def process_streaming_chunk(
    session_id: str, 
    chunk_data: bytes,
    language_code: str
) -> Optional[Dict]:
    """Process streaming audio chunk with language path separation"""
    try:
        session = streaming_sessions.get(session_id)
        if not session:
            raise ValueError("Invalid streaming session")
        
        # Add language validation
        if not LanguageMetadata.is_language_supported(language_code):
            raise ValueError(f"Unsupported language: {language_code}")
            
        
        is_english = language_code == "en"
        session.buffer += chunk_data
        session.chunk_count += 1
        
        if len(session.buffer) > 1024 * 1024:  # 1MB limit
            logger.warning("Stream buffer exceeded limit - clearing")
            session.buffer = chunk_data  # Keep only newest chunk
        else:
            session.buffer += chunk_data
                    
            # Use process_input instead of process_speech_to_text
            result = await speech_processor.process_input(
                content=session.buffer,
                source_language=language_code,
                is_audio=True,
                stream=True
            )
            
            session.buffer = b""
            
            if result:
                response = {
                    "status": "success",
                    "text": result.original_text,
                    "language": {
                        "code": result.language_code,
                        "name": result.language_name,
                        "confidence": result.confidence
                    },
                    "is_final": session.is_final,
                    "metadata": {
                        **result.metadata,
                        "processing_path": "english_direct" if is_english else "translation"
                    }
                }
                
                # Add translation info only for non-English
                if not is_english and result.english_text:
                    response["english_text"] = result.english_text
                    
                return response
                
        return None
        
    except Exception as e:
        logger.error(f"Chunk processing error: {str(e)}")
        raise


async def stream_speech(websocket: WebSocket, session_id: str):
    """Handle streaming speech processing with language-specific paths and native responses"""
    try:
        if not manager.initialized:
            await manager.initialize()
            
        # Get language preferences with proper fallback
        language_prefs = {'preferred': 'en', 'interface': 'en'}
        try:
            session_data = await redis_client.get(f"consultation:{session_id}")
            if session_data:
                session_info = json.loads(session_data)
                language_prefs = session_info.get('language_preferences', language_prefs)
            else:
                consultation = await consultations_collection.find_one(
                    {"consultation_id": session_id}
                )
                if consultation:
                    language_prefs = consultation.get('language_preferences', language_prefs)
                else:
                    logger.warning(f"No language preferences found for session {session_id}, using defaults")
        except Exception as e:
            logger.error(f"Error fetching language preferences: {str(e)}")
        
        source_language = language_prefs['preferred']
        is_english = source_language == "en"
        logger.info(f"Starting stream processing on {'English' if is_english else 'Translation'} path")
            
        await manager.connect(
            websocket=websocket,
            consultation_id=session_id,
            language_preferences=language_prefs
        )
        
        # Initialize streaming session with language info
        streaming_sessions[session_id] = StreamingState(
            session_id=session_id,
            start_time=datetime.utcnow(),
            language_code=source_language,
            is_english_path=is_english
        )
        
        try:
            while True:
                data = await websocket.receive_bytes()
                
                # Process streaming chunk based on language path
                result = await process_streaming_chunk(
                    session_id=session_id,
                    chunk_data=data,
                    language_code=source_language
                )
                
                if result:
                    # Prepare response based on language path
                    response_content = result["text"]
                    response_data = {
                        'type': "speech_result",
                        'content': response_content,
                        'language': {
                            'code': result["language"]["code"],
                            'name': result["language"]["name"]
                        },
                        'metadata': {
                            'path': 'english_direct' if is_english else 'translation',
                            'confidence': result["language"]["confidence"],
                            'is_final': result["is_final"],
                            'timestamp': datetime.utcnow().isoformat()
                        }
                    }

                    # Add translation info for non-English
                    if not is_english and result.get("english_text"):
                        response_data["original_content"] = result["english_text"]
                        response_data["metadata"]["translation_info"] = {
                            "source_language": source_language,
                            "target_language": "en"
                        }

                    # Generate streaming audio response if final
                    if result["is_final"] and result.get("generate_audio", True):
                        try:
                            audio_response = await speech_processor.process_output(
                                input_text=result["text"],
                                english_text=result.get("english_text"),
                                target_language=source_language,
                                generate_speech=True
                            )
                            if audio_response and audio_response.get("audio_data"):
                                response_data["audio"] = audio_response["audio_data"]
                        except Exception as audio_error:
                            logger.error(f"Stream audio generation error: {str(audio_error)}")

                    response = WebSocketResponse(**response_data)
                    await manager._send_response(session_id, response)
                    
        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected: {session_id}")
            await manager.disconnect(session_id)
            
        except Exception as e:
            logger.error(f"Streaming error: {str(e)}")
            error_response = WebSocketResponse(
                type="error",
                content=str(e),
                language={'code': source_language},
                metadata={
                    'error_type': 'streaming_error',
                    'path': 'english_direct' if is_english else 'translation',
                    'timestamp': datetime.utcnow().isoformat()
                }
            )
            await manager._send_response(session_id, error_response)
            
        finally:
            if session_id in streaming_sessions:
                del streaming_sessions[session_id]
                logger.info(f"Cleaned up streaming session: {session_id}")
                
            try:
                await manager.disconnect(session_id)
                logger.info(f"Disconnected WebSocket for session: {session_id}")
            except Exception as cleanup_error:
                logger.error(f"Error during session cleanup: {str(cleanup_error)}")
            
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        try:
            await websocket.close(code=1011)
        except:
            pass


async def cleanup_audio_file(filename: str):
    """Cleanup temporary audio files"""
    try:
        # Implement cleanup logic
        pass
    except Exception as e:
        logger.error(f"Cleanup error for {filename}: {str(e)}")

@router.get("/supported-languages")
async def get_supported_languages():
    """Get information about supported languages"""
    try:
        # Get supported languages from processor
        supported = await speech_processor.get_supported_languages()
        
        # Enrich with metadata
        for lang_code in supported["supported_languages"]:
            supported["supported_languages"][lang_code].update({
                "metadata": LanguageMetadata.get_language_metadata(lang_code),
                "voice_config": LanguageMetadata.get_voice_config(lang_code)
            })
        
        return JSONResponse(content=supported)
        
    except Exception as e:
        logger.error(f"Error getting supported languages: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={"error": str(e), "type": "configuration_error"}
        )