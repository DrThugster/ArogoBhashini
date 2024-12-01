# backend/app/services/translation_service/bhashini_service.py
from typing import Dict, Optional, List, Any
import aiohttp
import json
import os
from dotenv import load_dotenv
import logging
from datetime import datetime
from fastapi import HTTPException
from app.config.language_metadata import LanguageMetadata
from app.utils.translation_cache import TranslationCache
import asyncio
import base64

logger = logging.getLogger(__name__)
load_dotenv()

class BhashiniResponseModel:
    """Structured response models for Bhashini services"""
    ASR_RESPONSE = {
        "text": str,
        "language": str,
        "confidence": float,
        "metadata": Dict
    }
    
    TTS_RESPONSE = {
        "audio_data": str,
        "language": str,
        "metadata": Dict
    }
    
    TRANSLATION_RESPONSE = {
        "text": str,
        "source_language": str,
        "target_language": str,
        "confidence": float,
        "metadata": Dict
    }

class BhashiniService:
    def __init__(self):
        # Core configurations
        self.user_id = os.getenv("BHASHINI_USER_ID")
        self.ulca_api_key = os.getenv("BHASHINI_ULCA_API_KEY")
        self.pipeline_id = os.getenv("BHASHINI_PIPELINE_ID")

        # Add debug logging for initialization
        logger.debug(f"Initializing BhashiniService with pipeline ID: {self.pipeline_id}")
        
        # API endpoints
        self.config_url = "https://meity-auth.ulcacontrib.org/ulca/apis/v0/model/getModelsPipeline"
        self.compute_url = None
        self.compute_auth_header = None
        
        # Service configurations
        self.max_retries = 3
        self.retry_delay = 1  # seconds
        self.timeout = aiohttp.ClientTimeout(total=30)
        
        # Initialize translation cache
        self.translation_cache = TranslationCache()
        
        # Connection pooling
        self.session = None
        
    async def initialize(self):
        """Initialize service and create session pool"""
        try:
            self.session = aiohttp.ClientSession(timeout=self.timeout)
            # Initialize compute URL and auth
            await self._initialize_compute_endpoints()
            logger.info("BhashiniService initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize BhashiniService: {str(e)}")
            raise

    async def _initialize_compute_endpoints(self):
        """Initialize compute endpoints with retry logic"""
        retry_count = 0
        while retry_count < self.max_retries:
            try:
                # Make initial config call
                tasks = [
                    {"taskType": "asr", "config": {"language": {}}},
                    {"taskType": "translation", "config": {"language": {}}},
                    {"taskType": "tts", "config": {"language": {}}}
                ]
                
                config_data = await self._make_config_call(tasks)
                
                if "pipelineInferenceAPIEndPoint" in config_data:
                    endpoint = config_data["pipelineInferenceAPIEndPoint"]
                    self.compute_url = endpoint["callbackUrl"]
                    auth_key = endpoint["inferenceApiKey"]
                    self.compute_auth_header = {auth_key["name"]: auth_key["value"]}
                    return
                    
                retry_count += 1
                await asyncio.sleep(self.retry_delay * retry_count)
                
            except Exception as e:
                logger.error(f"Compute endpoint initialization failed: {str(e)}")
                retry_count += 1
                if retry_count >= self.max_retries:
                    raise

    async def _make_config_call(self, tasks: List[Dict]) -> Dict:
        """Make pipeline config call with retries"""
        if not self.session:
            await self.initialize()
            
        headers = {
            "userID": self.user_id,
            "ulcaApiKey": self.ulca_api_key,
            "Content-Type": "application/json"
        }
        
        # Format payload for Bhashini API
        payload = {
            "pipelineTasks": [
                {
                    "taskType": task["taskType"],
                    "config": {
                        "language": task["config"]["language"]
                    }
                } for task in tasks
            ],
            "pipelineRequestConfig": {
                "pipelineId": self.pipeline_id
            }
        }
        
        logger.debug("Making Bhashini API config call:")
        logger.debug(f"URL for Config: {self.config_url}")
        logger.debug(f"Payload for Config: {json.dumps(payload, indent=2)}")

        for retry in range(self.max_retries):
            try:
                async with self.session.post(
                    self.config_url,
                    json=payload,
                    headers=headers
                ) as response:
                    response_text = await response.text()
                    logger.info(f"Response status: {response.status}")
                    
                    if response.status == 200:
                        return json.loads(response_text)
                        
                    if retry < self.max_retries - 1:
                        await asyncio.sleep(self.retry_delay * (retry + 1))
                        continue
                        
                    raise Exception(f"Config call failed: {response_text}")
                    
            except aiohttp.ClientError as e:
                if retry < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (retry + 1))
                    continue
                raise

    async def _make_compute_call(
        self,
        tasks: List[Dict],
        input_data: Dict,
        retry_count: int = 0
    ) -> Dict:
        """Make pipeline compute call with retry logic"""
        if not self.compute_url or not self.compute_auth_header:
            await self._initialize_compute_endpoints()
            
        try:
            # Format payload for compute API
            payload = {
                "pipelineTasks": [
                    {
                        "taskType": task["taskType"],
                        "config": {
                            "language": task["config"]["language"],
                            **({"serviceId": task["config"].get("serviceId")} if task["config"].get("serviceId") else {}),
                            **({"audioFormat": task["config"].get("audioFormat")} if task["taskType"] == "asr" else {}),
                            **({"samplingRate": task["config"].get("samplingRate")} if task["taskType"] == "asr" else {}),
                            **({"gender": task["config"].get("gender")} if task["taskType"] == "tts" else {})
                        }
                    } for task in tasks
                ],
                "inputData": {
                    "input": [{"source": input_data.get("input", [{"source": ""}])[0].get("source", "")}]
                }
            }

            # Only add audio data for ASR/TTS tasks
            if any(task["taskType"] in ["asr", "tts"] for task in tasks):
                payload["inputData"]["audio"] = [{"audioContent": input_data.get("audio", [{"audioContent": ""}])[0].get("audioContent", "")}]

            # Detailed request logging
            logger.info("Making compute call:")
            logger.info(f"URL: {self.compute_url}")
            logger.info(f"Tasks: {json.dumps(tasks, indent=2)}")

            # Safe audio size logging
            if "audio" in input_data and input_data.get("audio"):
                audio_content = input_data["audio"][0].get("audioContent", "")
                logger.info(f"Input data summary: Audio size={len(str(audio_content))}")

            async with self.session.post(
                self.compute_url,
                json=payload,
                headers=self.compute_auth_header
            ) as response:
                response_text = await response.text()
                logger.debug(f"Response status: {response.status}")
                logger.info(f"Response body: {response_text[:200]}...")
                
                if response.status == 200:
                    return json.loads(response_text)
                    
                if retry_count < self.max_retries:
                    await asyncio.sleep(self.retry_delay * (retry_count + 1))
                    return await self._make_compute_call(tasks, input_data, retry_count + 1)
                    
                raise Exception(f"Compute call failed: {response_text}")
                
        except Exception as e:
            logger.error(f"Compute call error on attempt {retry_count + 1}: {str(e)}")
            if retry_count < self.max_retries:
                await asyncio.sleep(self.retry_delay * (retry_count + 1))
                return await self._make_compute_call(tasks, input_data, retry_count + 1)
            raise



    async def speech_to_text(
        self,
        audio_data: bytes,
        source_language: str,
        auto_detect: bool = False
    ) -> Dict:
        """Convert speech to text with language detection"""
        try:
            # Configure ASR task
            asr_task = {
                "taskType": "asr",
                "config": {
                    "language": {
                        "sourceLanguage": "auto"  # Always use auto for initial detection
                    },
                    "audioFormat": "wav",
                    "samplingRate": 16000
                }
            }
            
            logger.info("Initiating speech detection")
            
            # Get pipeline config
            config_response = await self._make_config_call([asr_task])
            
            # Let Bhashini handle model selection
            if "pipelineResponseConfig" in config_response:
                for task_config in config_response["pipelineResponseConfig"]:
                    if task_config["taskType"] == "asr":
                        asr_task["config"]["serviceId"] = task_config["config"][0]["serviceId"]
                        logger.info(f"Using ASR service: {asr_task['config']['serviceId']}")
            
            # Process speech
            compute_payload = {
                "pipelineTasks": [asr_task],
                "inputData": {
                    "input": [{"source": ""}],
                    "audio": [{"audioContent": base64.b64encode(audio_data).decode('utf-8')}]
                }
            }
            
            response = await self._make_compute_call(
                [asr_task],
                compute_payload["inputData"]
            )
            
            # Extract response and detected language
            if "pipelineResponse" in response and response["pipelineResponse"]:
                task_response = response["pipelineResponse"][0]
                
                # Extract language from response or use source_language as fallback
                config_data = task_response.get("config", {})
                language_data = config_data.get("language", {}) if config_data else {}
                detected_lang = language_data.get("sourceLanguage", source_language)
                
                # Extract text from response
                output_text = task_response["output"][0]["source"] if task_response.get("output") else ""
                
                result = {
                    "text": output_text,
                    "language": detected_lang,
                    "confidence": task_response.get("confidence", 1.0),
                    "metadata": {
                        "detected_language": detected_lang,
                        "original_language": source_language,
                        "model_used": asr_task["config"]["serviceId"],
                        "timestamp": datetime.utcnow().isoformat(),
                        "pipeline_config": config_data
                    }
                }
                
                logger.info(f"Speech processed successfully. Detected language: {detected_lang}")
                return result
                
            raise Exception("No ASR output in response")
            
        except Exception as e:
            logger.error(f"Speech to text error: {str(e)}")
            raise

    async def translate_text(
        self,
        text: str,
        source_language: str,
        target_language: str,
        preserve_medical_terms: bool = True
    ) -> Dict:
        """Translate text with medical term preservation"""
        try:
            truncated_text = text[:100] + "..." if len(text) > 100 else text
            logger.info(f"Input text to translate: {truncated_text}")
            logger.debug(f"Full text length: {len(text)} characters")

            translation_task = {
                "taskType": "translation",
                "config": {
                    "language": {
                        "sourceLanguage": source_language,
                        "targetLanguage": target_language
                    },
                    "preserveTerms": preserve_medical_terms
                }
            }
            logger.debug(f"Translation task configuration: {json.dumps(translation_task)}")

            # Get pipeline config
            config_response = await self._make_config_call([translation_task])
            
            # Update service ID
            if "pipelineResponseConfig" in config_response:
                for task_config in config_response["pipelineResponseConfig"]:
                    if task_config["taskType"] == "translation":
                        service_id = task_config["config"][0]["serviceId"]
                        translation_task["config"]["serviceId"] = service_id
                        logger.info(f"Translation service ID: {service_id}")

            # Process translation
            logger.info("Executing translation compute call")
            compute_response = await self._make_compute_call(
                [translation_task],
                {
                    "input": [{"source": text}],
                    "audio": None
                }
            )
            
            # Return complete pipeline response for proper extraction
            if "pipelineResponse" in compute_response:
                pipeline_response = compute_response["pipelineResponse"]
                if pipeline_response and isinstance(pipeline_response, list):
                    task_response = pipeline_response[0]
                    if task_response["taskType"] == "translation" and task_response.get("output"):
                        output = task_response["output"][0]
                        translated_text = output["target"]
                        confidence = task_response.get("confidence", 1.0)
                        preserved_terms = task_response.get("preservedTerms", [])
                        
                        logger.info("Translation completed successfully")
                        logger.info(f"Confidence score: {confidence}")
                        logger.debug(f"Translated text (truncated): {translated_text[:100]}...")
                        logger.info(f"Output length: {len(translated_text)} characters")
                        
                        if preserved_terms:
                            logger.info(f"Preserved {len(preserved_terms)} medical terms: {preserved_terms}")
                        
                        return {
                            "pipelineResponse": [{
                                "taskType": "translation",
                                "config": translation_task["config"],
                                "output": [{
                                    "source": text,
                                    "target": translated_text
                                }],
                                "confidence": confidence,
                                "preservedTerms": preserved_terms,
                                "metadata": {
                                    "service_id": translation_task["config"]["serviceId"],
                                    "timestamp": datetime.utcnow().isoformat()
                                }
                            }]
                        }

            logger.error("Translation failed - No valid output in response")
            raise ValueError("Invalid translation response structure")
            
        except Exception as e:
            logger.error(f"Translation error: {str(e)}", exc_info=True)
            raise



    async def text_to_speech(
        self,
        text: str,
        target_language: str,
        gender: str = "female",
        style: Optional[str] = None
    ) -> Dict:
        """Convert text to speech"""
        try:
            # Validate voice options
            voice_config = LanguageMetadata.get_voice_config()
            gender, style = LanguageMetadata.validate_voice_options(gender, style)
            
            # Configure TTS task
            tts_task = {
                "taskType": "tts",
                "config": {
                    "language": {
                        "sourceLanguage": target_language
                    },
                    "gender": gender,
                    "style": style
                }
            }
            
            # Get pipeline config
            config_response = await self._make_config_call([tts_task])
            
            # Update task with serviceId
            if "pipelineResponseConfig" in config_response:
                for task_config in config_response["pipelineResponseConfig"]:
                    if task_config["taskType"] == "tts":
                        tts_task["config"]["serviceId"] = task_config["config"][0]["serviceId"]
            
            # Process TTS with correct input structure
            response = await self._make_compute_call(
                [tts_task],
                {
                    "input": [
                        {
                            "source": text
                        }
                    ],
                    "audio": [
                        {
                            "audioContent": None
                        }
                    ]
                }
            )
            
            # Extract result
            if "pipelineResponse" in response:
                for task_response in response["pipelineResponse"]:
                    if task_response["taskType"] == "tts":
                        return {
                            "audio_data": task_response["audio"][0]["audioContent"],
                            "language": target_language,
                            "metadata": {
                                "gender": gender,
                                "style": style,
                                "timestamp": datetime.utcnow().isoformat()
                            }
                        }
            
            raise Exception("No TTS output in response")
            
        except Exception as e:
            logger.error(f"Text to speech error: {str(e)}")
            raise


    async def cleanup(self):
        """Cleanup service resources"""
        try:
            if self.session and not self.session.closed:
                await self.session.close()
        except Exception as e:
            logger.error(f"Cleanup error: {str(e)}")