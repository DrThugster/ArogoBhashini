# backend/app/routes/websocket.py
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, Optional, Set, List, Any
import logging
from datetime import datetime, date
import json
from pydantic import BaseModel, Field, validator
import base64
from app.utils.speech_processor import SpeechProcessor, ProcessedSpeech
from app.services.chat_service import ChatService
from app.utils.response_validator import AIResponseValidator
from app.config.language_metadata import LanguageMetadata
from app.config.database import redis_client, DatabaseConfig, consultations_collection
from app.utils.serializers import StreamingStateSerializer
from typing import Union
import os

logger = logging.getLogger(__name__)
router = APIRouter()

class LanguageConfig(BaseModel):
    source: str
    autoDetect: bool = True

class WebSocketMessage(BaseModel):
    """WebSocket message model"""
    
class WebSocketMessage(BaseModel):
    """WebSocket message model"""
    type: str
    content: str
    language: Union[str, Dict[str, Any]]  # Changed to accept both string and dict
    metadata: Optional[Dict] = {}

    @validator('language')
    def validate_language(cls, v):
        if isinstance(v, dict):
            # If autoDetect is present but source is missing, set a default
            if 'autoDetect' in v and 'source' not in v:
                v['source'] = 'en'
            return LanguageConfig(**v).source
        return v

class WebSocketResponse(BaseModel):
    """WebSocket response model"""
    type: str = Field(..., description="Response type: 'response', 'error', 'warning'")
    content: str = Field(..., description="Response content")
    original_content: Optional[str] = Field(None, description="Original English content if translated")
    language: Dict[str, str] = Field(..., description="Response language information")
    audio: Optional[str] = Field(None, description="Base64 encoded audio response")
    metadata: Dict = Field(default_factory=dict, description="Additional response metadata")

class StreamingState(BaseModel):
    is_streaming: bool = Field(default=False)
    buffer: str = Field(default="")
    start_time: Optional[datetime] = None
    total_bytes: int = Field(default=0)
    chunks_processed: int = Field(default=0)

    def set_buffer(self, data: bytes) -> None:
        self.buffer = base64.b64encode(data).decode() if data else ""

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}

class SessionManager:
    def __init__(self, redis_client, prefix: str = "ws_session:", ttl: int = 3600):
        self.redis = redis_client
        self.prefix = prefix
        self.ttl = ttl

    async def cache_session(self, session_id: str, data: Dict) -> None:
        """Single responsibility for session caching"""
        key = f"{self.prefix}{session_id}"
        serialized = json.dumps(data, default=self._json_serializer)
        await self.redis.setex(key, self.ttl, serialized)

    @staticmethod
    def _json_serializer(obj):
        """Handle special type serialization"""
        if isinstance(obj, bytes):
            return base64.b64encode(obj).decode()
        if isinstance(obj, datetime):
            return obj.isoformat()
        return str(obj)


class ConnectionState(BaseModel):
    """Connection state with enhanced tracking"""
    websocket: WebSocket
    language_preferences: Dict = Field(..., description="Language preferences")
    last_activity: datetime = Field(default_factory=datetime.utcnow)
    message_count: int = Field(default=0, description="Messages in current window")
    rate_info: Dict = Field(default_factory=lambda: {
        'count': 0,
        'window_start': datetime.utcnow()
    })
    streaming_state: StreamingState = Field(default_factory=StreamingState)
    user_details: Dict = Field(default_factory=dict)
    context_id: Optional[str] = Field(None, description="Conversation context ID")
    original_language: str = Field(None, description="Original language preference")
    language_path: str = Field(default="translation", description="Current language processing path")

    def __init__(self, **data):
        super().__init__(**data)
        # Set original language from user preferences without hardcoding
        self.original_language = self.language_preferences.get('preferred')
        self.language_path = "english_direct" if self.original_language == "en" else "translation"

    def get_processing_language(self) -> str:
        """Get the correct language for processing"""
        return self.original_language

    def update_activity(self):
        """Update activity timestamp"""
        self.last_activity = datetime.utcnow()

    class Config:
        arbitrary_types_allowed = True


class ConnectionManager:
    def __init__(self):
        # Core services
        self.session_manager = SessionManager(redis_client)
        self.speech_processor = SpeechProcessor()
        self.chat_service = ChatService()
        self.response_validator = AIResponseValidator()

        # Database clients
        self.db_config = None
        self.mongodb = None
        self.redis = None
        
        # Connection tracking
        self.active_connections: Dict[str, ConnectionState] = {}
        self.language_groups: Dict[str, Set[str]] = {}
        
        # Resource management
        self.max_concurrent_streams = asyncio.Semaphore(5)
        self.max_message_size = 1024 * 1024  # 1MB
        self.chunk_size = 32768  # 32KB chunks
        
        # Performance configuration
        self.rate_limits = {
            'messages_per_minute': 30,
            'audio_duration_limit': 300,  # seconds
            'max_retries': 3
        }
        
        # Redis configuration
        self.redis_prefix = "consultation:"
        self.cache_ttl = 3600  # 1 hour
        
        # State tracking
        self.initialized = False
        
    async def _check_rate_limit(self, consultation_id: str) -> bool:
        """Check if the client has exceeded rate limits"""
        now = datetime.utcnow()
        rate_info = self.active_connections[consultation_id].rate_info
        
        if (now - rate_info['window_start']).seconds > 60:
            rate_info['count'] = 1
            rate_info['window_start'] = now
            return True
            
        rate_info['count'] += 1
        return rate_info['count'] <= self.rate_limits['messages_per_minute']
    
    async def _send_error_message(self, consultation_id: str, error_message: str):
        """Send error message to client"""
        error_response = WebSocketResponse(
            type="error",
            content="Message processing failed",
            language={"code": "en"},
            metadata={
                'error': error_message,
                'timestamp': datetime.utcnow().isoformat()
            }
        )
        await self._send_response(consultation_id, error_response)
    
    async def _send_rate_limit_warning(self, consultation_id: str):
        """Send rate limit warning to client"""
        warning = WebSocketResponse(
            type="warning",
            content="Rate limit exceeded. Please wait before sending more messages.",
            metadata={'timestamp': datetime.utcnow().isoformat()}
        )
        await self._send_response(consultation_id, warning)

    async def initialize(self):
        """Initialize WebSocket manager and services"""
        if not self.initialized:
            try:
                # Initialize database config
                db_config = DatabaseConfig()
                await db_config.initialize()
                await db_config._initialized.wait()
                
                # Get MongoDB client and collection
                mongodb = db_config.get_mongodb()
                if not mongodb:
                    raise RuntimeError("MongoDB client not available")
                    
                db = mongodb[os.getenv("DATABASE_NAME", "arogo_bhasini2")]
                global consultations_collection
                consultations_collection = db.consultations
                
                # Get Redis client after initialization
                self.redis_client = db_config.get_redis()
                if not self.redis_client:
                    raise RuntimeError("Redis client not available")

                # Initialize other services
                await self.speech_processor.initialize()
                await self.chat_service.initialize()
                
                self.initialized = True
                logger.info("""
                WebSocket Manager Initialized:
                - Database connections established
                - Collections configured
                - Services ready
                """)
                
            except Exception as e:
                logger.error(f"WebSocket initialization error: {str(e)}")
                raise

    
    async def _cache_session_data(self, session_id: str, state: ConnectionState):
        """Cache session data in Redis with proper error handling"""
        try:
            if not self.redis_client:
                await self.initialize()
                if not self.redis_client:
                    raise RuntimeError("Redis client unavailable")
                    
            cache_key = f"{self.redis_prefix}session:{session_id}"
            
            # Use serializer for streaming state
            streaming_state = StreamingStateSerializer.serialize(
                state.streaming_state.model_dump()
            )
            
            session_data = {
                "language_preferences": state.language_preferences,
                "last_activity": state.last_activity.isoformat(),
                "message_count": state.message_count,
                "streaming_state": streaming_state,
                "user_details": state.user_details,
                "context_id": state.context_id
            }
            
            await self.redis_client.setex(
                cache_key,
                self.cache_ttl,
                json.dumps(session_data)
            )
            
            logger.debug("Session cached", extra={"session_id": session_id})
                
        except Exception as e:
            logger.error(
                "Session cache error",
                extra={
                    "session_id": session_id,
                    "error": str(e)
                },
                exc_info=True
            )
            raise RuntimeError(f"Session caching failed: {str(e)}")

          
    async def connect(
        self,
        websocket: WebSocket,
        consultation_id: str,
        language_preferences: Dict
    ):
        """Handle new WebSocket connection with consultation context and error handling"""
        try:
            if not self.initialized:
                await self.initialize()

            await websocket.accept()

            # Get consultation data for context
            db_config = DatabaseConfig()
            await db_config.initialize()
            await db_config._initialized.wait()

            consultation_data = await consultations_collection.find_one(
                {"consultation_id": consultation_id}
            )

            if consultation_data:
                # Use stored language preferences from consultation
                stored_preferences = consultation_data.get("language_preferences", {})
                language_preferences = stored_preferences
                
                # Get user details for context
                user_details = consultation_data.get("user_details", {})
            else:
                user_details = {}

            # Validate language preferences
            preferred_language = language_preferences.get('preferred', 'en')
            if not LanguageMetadata.is_language_supported(preferred_language):
                raise ValueError(f"Unsupported language: {preferred_language}")

            # Create connection state with full context
            state = ConnectionState(
                websocket=websocket,
                language_preferences=language_preferences,
                last_activity=datetime.utcnow(),
                user_details=user_details,
                context_id=consultation_id,
                original_language=preferred_language,
                language_path="english_direct" if preferred_language == "en" else "translation"
            )

            # Store connection state
            self.active_connections[consultation_id] = state

            # Initialize language group
            if preferred_language not in self.language_groups:
                self.language_groups[preferred_language] = set()
            self.language_groups[preferred_language].add(consultation_id)

            # Cache session data with language context
            await self._cache_session_data(consultation_id, state)

            # Send welcome message in preferred language
            await self._send_welcome_message(consultation_id)

            logger.info(f"""
            WebSocket Connected:
            Consultation ID: {consultation_id}
            Language: {preferred_language}
            Processing Path: {state.language_path}
            User: {user_details.get('first_name', 'Patient')}
            """)

        except Exception as e:
            logger.error(f"Connection error: {str(e)}")
            await self.disconnect(consultation_id)
            raise


    async def process_message(self, consultation_id: str, message: WebSocketMessage):
        """Process messages following our flow:
        English Path: Speech/Text → STT/Direct → AI → TTS
        Non-English Path: Speech/Text → Native STT/Process → Translation → AI → Translation → TTS
        """
        try:
            state = self.active_connections[consultation_id]
            
            # Rate limiting check
            if not await self._check_rate_limit(consultation_id):
                await self._send_rate_limit_warning(consultation_id)
                return
            
            # Update state
            state.last_activity = datetime.utcnow()
            state.message_count += 1
            
            # Get and maintain original language preference
            original_language = state.original_language
            is_english = original_language == "en"
            
            logger.info(f"""
    === Starting Message Processing ===
    Consultation ID: {consultation_id}
    Initial Language: {original_language}
    Message Type: {message.type}
    Start Time: {datetime.utcnow().isoformat()}
            """)

            # Process input based on type
            input_result = await self.speech_processor.process_input(
                content=base64.b64decode(message.content) if message.type in ['audio', 'speech'] else message.content,
                source_language=original_language,
                is_audio=message.type in ['audio', 'speech'],
                session_id=consultation_id
            )

            # Process with AI using English text but maintain original language
            ai_response = await self.chat_service.process_message(
                consultation_id=consultation_id,
                message=input_result.english_text,
                source_language=original_language
            )

            # Handle output processing based on original language
            if not is_english:
                # Translate AI response to original language
                translation_result = await self.speech_processor.process_output(
                    input_text=ai_response.original_text,
                    english_text=ai_response.original_text,
                    target_language=original_language,
                    generate_speech=False
                )
                
                # Generate speech in original language
                output_result = await self.speech_processor.process_output(
                    input_text=translation_result.get("translated_text"),
                    english_text=ai_response.original_text,
                    target_language=original_language,
                    generate_speech=True
                )
                response_text = translation_result.get("translated_text")
            else:
                output_result = await self.speech_processor.process_output(
                    input_text=ai_response.original_text,
                    english_text=ai_response.original_text,
                    target_language="en",
                    generate_speech=True
                )
                response_text = ai_response.original_text

            # Create response with original language
            response = WebSocketResponse(
                type="response",
                content=response_text,
                original_content=ai_response.original_text if not is_english else None,
                audio=output_result.get("audio_data"),
                language={
                    'code': original_language,
                    'name': LanguageMetadata.get_language_name(original_language)
                },
                metadata={
                    'input_processing': {
                        'original_text': input_result.original_text,
                        'english_text': input_result.english_text if not is_english else None,
                        'confidence': input_result.confidence,
                        'duration': input_result.duration if message.type in ['audio', 'speech'] else None
                    },
                    'translation_status': {
                        'input_translated': not is_english,
                        'output_translated': not is_english,
                        'confidence': output_result.get("confidence", 1.0)
                    },
                    'processing_flow': {
                        'type': 'speech_to_speech' if message.type in ['audio', 'speech'] else 'text_to_speech',
                        'path': 'english_direct' if is_english else 'translation',
                        'timestamp': datetime.utcnow().isoformat()
                    }
                }
            )

            # Send response
            await self._send_response(consultation_id, response)

            # Update context with original language
            await self._update_conversation_context(
                consultation_id=consultation_id,
                user_message={
                    "text": input_result.original_text,
                    "english_text": input_result.english_text,
                    "language": original_language,
                    "timestamp": datetime.utcnow().isoformat()
                },
                ai_response={
                    "text": response_text,
                    "english_text": ai_response.original_text,
                    "language": original_language,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )

            logger.info(f"""
    === Message Processing Completed ===
    Consultation ID: {consultation_id}
    Response Length: {len(response_text)}
    Translation Path: {'Direct' if is_english else 'Translated'}
    Language: {original_language}
            """)

        except Exception as e:
            logger.error(f"Message processing error: {str(e)}", exc_info=True)
            await self._send_error_message(consultation_id, str(e))




    async def _process_audio_message(
        self,
        consultation_id: str,
        message: WebSocketMessage
    ):
        """Handle audio following our flow"""
        state = self.active_connections[consultation_id]
        streaming = state.streaming_state
        
        try:
            # Decode and validate audio data
            try:
                audio_data = base64.b64decode(message.content)
                if len(audio_data) > self.max_message_size:
                    raise ValueError("Audio data too large")
            except Exception as decode_error:
                raise ValueError(f"Invalid audio data: {str(decode_error)}")

            source_language = message.language or state.language_preferences['preferred']
            
            # Streaming logic
            if message.metadata.get('streaming_start'):
                # Initialize streaming state
                streaming.is_streaming = True
                streaming.buffer = b""
                streaming.start_time = datetime.utcnow()
                streaming.total_bytes = 0
                streaming.chunks_processed = 0
            
            # Process audio with concurrency control
            async with self.max_concurrent_streams:
                if streaming.is_streaming:
                    # Accumulate streaming data
                    streaming.buffer += audio_data
                    streaming.total_bytes += len(audio_data)
                    
                    # Process if chunk size reached or stream ended
                    should_process = (
                        len(streaming.buffer) >= self.chunk_size or
                        message.metadata.get('streaming_end')
                    )
                    
                    if should_process:
                        await self._process_audio_chunk(
                            consultation_id,
                            bytes(streaming.buffer),
                            source_language
                        )
                        streaming.buffer = b""
                        streaming.chunks_processed += 1
                else:
                    # Process complete audio
                    await self._process_audio_chunk(
                        consultation_id,
                        audio_data,
                        source_language
                    )
            
            # Handle stream end
            if message.metadata.get('streaming_end'):
                streaming.is_streaming = False
                logger.info(f"Audio stream ended: {streaming.total_bytes} bytes, {streaming.chunks_processed} chunks")
                
        except Exception as e:
            logger.error(f"Audio processing error: {str(e)}")
            streaming.is_streaming = False
            await self._send_error_message(consultation_id, str(e))

    async def _process_audio_chunk(
        self,
        consultation_id: str,
        audio_data: bytes,
        source_language: str
    ):
        """Process audio chunk following our flow"""
        try:
            state = self.active_connections[consultation_id]
            
            # 1. Speech to Text (Native)
            speech_result = await self.speech_processor.process_speech(
                audio_data=audio_data,
                source_language=source_language
            )
            
            # 2. Get English text (either direct or translated)
            english_text = (
                speech_result.original_text 
                if source_language == "en" 
                else speech_result.english_text
            )
            
            if not english_text:
                logger.warning(f"No text extracted from audio in {source_language}")
                return
            
            # 3. Process with AI
            ai_response = await self.chat_service.process_message(
                consultation_id=consultation_id,
                message=english_text,
                context=await self._get_conversation_context(consultation_id)
            )
            
            # 4. Translation handling
            target_language = state.language_preferences['preferred']
            response_text = ai_response["response"]
            
            if target_language != "en":
                translated = await self.chat_service.translate_to_language(
                    text=response_text,
                    source_language="en",
                    target_language=target_language
                )
                response_text = translated["text"]
            
            # 5. Audio response if enabled
            audio_response = None
            if state.user_details.get('enable_audio', False):
                audio_result = await self.speech_processor.text_to_native_speech(
                    english_text=response_text,
                    target_language=target_language
                )
                audio_response = audio_result.get('audio_data')
            
            # 6. Prepare and send response
            response = WebSocketResponse(
                type="response",
                content=response_text,
                original_content=ai_response["response"],
                language={
                    'code': target_language,
                    'name': LanguageMetadata.get_language_name(target_language)
                },
                audio=audio_response,
                metadata={
                    'confidence': speech_result.confidence,
                    'timestamp': datetime.utcnow().isoformat()
                }
            )
            
            await self._send_response(consultation_id, response)
            
            # 7. Update conversation context
            await self._update_conversation_context(
                consultation_id=consultation_id,
                user_message={
                    "text": speech_result.original_text,
                    "english_text": english_text,
                    "language": source_language
                },
                ai_response={
                    "text": response_text,
                    "english_text": ai_response["response"],
                    "language": target_language
                }
            )
            
        except Exception as e:
            logger.error(f"Chunk processing error: {str(e)}")
            raise

    async def _process_text_message(
        self,
        consultation_id: str,
        message: WebSocketMessage
    ):
        """Process text message following our flow"""
        try:
            state = self.active_connections[consultation_id]
            source_language = message.language or state.language_preferences['preferred']
            
            # 1. Get original text and validate
            original_text = message.content.strip()
            if not original_text:
                raise ValueError("Empty message content")
            
            # 2. Translation to English if needed
            english_text = original_text
            if source_language != "en":
                translation = await self.chat_service.translate_to_english(
                    text=original_text,
                    source_language=source_language
                )
                english_text = translation["text"]
            
            # 3. Process with AI
            ai_response = await self.chat_service.process_message(
                consultation_id=consultation_id,
                message=english_text,
                context=await self._get_conversation_context(consultation_id)
            )
            
            # 4. Translation of response if needed
            target_language = state.language_preferences['preferred']
            response_text = ai_response["response"]
            
            if target_language != "en":
                translated = await self.chat_service.translate_to_language(
                    text=response_text,
                    source_language="en",
                    target_language=target_language
                )
                response_text = translated["text"]
            
            # 5. Generate audio if enabled
            audio_response = None
            if state.user_details.get('enable_audio', False):
                audio_result = await self.speech_processor.text_to_native_speech(
                    english_text=response_text,
                    target_language=target_language
                )
                audio_response = audio_result.get('audio_data')
            
            # 6. Send response
            response = WebSocketResponse(
                type="response",
                content=response_text,
                original_content=ai_response["response"],
                language={
                    'code': target_language,
                    'name': LanguageMetadata.get_language_name(target_language)
                },
                audio=audio_response,
                metadata={
                    'timestamp': datetime.utcnow().isoformat(),
                    'translated': target_language != "en"
                }
            )
            
            await self._send_response(consultation_id, response)
            
            # 7. Update conversation context
            await self._update_conversation_context(
                consultation_id=consultation_id,
                user_message={
                    "text": original_text,
                    "english_text": english_text,
                    "language": source_language
                },
                ai_response={
                    "text": response_text,
                    "english_text": ai_response["response"],
                    "language": target_language
                }
            )
            
        except Exception as e:
            logger.error(f"Text processing error: {str(e)}")
            raise

    async def _update_conversation_context(
        self,
        consultation_id: str,
        user_message: Dict,
        ai_response: Dict
    ):
        """Update conversation context with optimized storage"""
        try:
            # Get database configuration
            if not hasattr(self, 'redis_client') or not self.redis_client:
                db_config = DatabaseConfig()
                await db_config.initialize()
                await db_config._initialized.wait()
                self.redis_client = await db_config.get_redis()

            # Get existing context or initialize new
            context = await self._get_conversation_context(consultation_id) or []
            timestamp = datetime.utcnow().isoformat()

            # Add user message
            context.append({
                "role": "user",
                "text": user_message["text"],
                "english_text": user_message["english_text"],
                "language": user_message["language"],
                "timestamp": timestamp,
                "metadata": {
                    "message_type": "user_input",
                    "session_id": consultation_id
                }
            })

            # Add assistant response
            context.append({
                "role": "assistant", 
                "text": ai_response["text"],
                "english_text": ai_response["english_text"],
                "language": ai_response["language"],
                "timestamp": timestamp,
                "metadata": {
                    "message_type": "ai_response",
                    "session_id": consultation_id
                }
            })

            # Maintain context window
            if len(context) > 20:
                context = context[-20:]

            # Cache with retry logic
            context_key = f"{self.redis_prefix}context:{consultation_id}"
            retry_count = 0
            max_retries = 3

            while retry_count < max_retries:
                try:
                    await self.redis_client.setex(
                        context_key,
                        self.cache_ttl,
                        json.dumps(context, ensure_ascii=False)
                    )
                    logger.info(f"Context updated successfully - Messages: {len(context)}")
                    break
                except Exception as redis_error:
                    retry_count += 1
                    if retry_count == max_retries:
                        raise redis_error
                    await asyncio.sleep(0.5 * retry_count)

            # Update MongoDB if available
            if hasattr(self, 'mongodb_client'):
                await self.mongodb_client.consultations.update_one(
                    {"consultation_id": consultation_id},
                    {"$set": {"context": context}},
                    upsert=True
                )

        except Exception as e:
            logger.error(
                f"Context update error for {consultation_id}: {str(e)}",
                extra={
                    "consultation_id": consultation_id,
                    "context_size": len(context) if 'context' in locals() else 0
                },
                exc_info=True
            )
            raise RuntimeError(f"Failed to update context: {str(e)}")


    async def _get_conversation_context(
        self,
        consultation_id: str
    ) -> List[Dict]:
        """Get conversation context with robust caching and validation"""
        try:
            if not self.redis_client:
                await self.initialize()
                
            context_key = f"{self.redis_prefix}context:{consultation_id}"
            cached_context = await self.redis_client.get(context_key)
            
            if cached_context:
                try:
                    context_data = json.loads(cached_context)
                    logger.info(f"Retrieved cached context for {consultation_id}")
                    return context_data
                except json.JSONDecodeError:
                    logger.warning(f"Invalid context format for {consultation_id}, creating new")
                    await self.redis_client.delete(context_key)
                    return []
            
            # Initialize new context
            new_context = []
            await self.redis_client.setex(
                context_key,
                self.cache_ttl,
                json.dumps(new_context)
            )
            logger.info(f"Created new context for {consultation_id}")
            return new_context
            
        except Exception as e:
            logger.error(
                f"Context retrieval error for {consultation_id}: {str(e)}",
                extra={"consultation_id": consultation_id}
            )
            return []

    async def _send_response(
        self,
        consultation_id: str,
        response: WebSocketResponse
    ):
        """Send response to WebSocket client with error handling"""
        try:
            state = self.active_connections[consultation_id]
            await state.websocket.send_json(response.dict(exclude_unset=True))
        except Exception as e:
            logger.error(f"Error sending response: {str(e)}")
            raise

    async def _send_welcome_message(
        self,
        consultation_id: str
    ):
        """Send localized welcome message with audio"""
        try:
            state = self.active_connections[consultation_id]
            target_language = state.language_preferences['preferred']
            
            # Generate welcome message in English
            welcome_text = "Welcome to your medical consultation. How can I help you today?"
            
            # Process output with translation and speech generation
            processed_output = await self.speech_processor.process_output(
                input_text=welcome_text,
                english_text=welcome_text,
                target_language=target_language,
                generate_speech=True  # Enable speech generation
            )
            
            welcome_text = processed_output.get("translated_text", welcome_text)
            audio_data = processed_output.get("audio_data")
            
            # Send welcome message with audio
            welcome = WebSocketResponse(
                type="welcome",
                content=welcome_text,
                language={
                    'code': target_language,
                    'name': LanguageMetadata.get_language_name(target_language)
                },
                audio=audio_data,  # Include audio data
                metadata={
                    'timestamp': datetime.utcnow().isoformat(),
                    'has_audio': bool(audio_data)
                }
            )
            
            await self._send_response(consultation_id, welcome)
            logger.info(f"Welcome message sent with audio in {target_language}")
            
        except Exception as e:
            logger.error(f"Error sending welcome message: {str(e)}")


    async def disconnect(self, consultation_id: str):
        """Handle WebSocket disconnection with cleanup"""
        try:
            if consultation_id in self.active_connections:
                state = self.active_connections[consultation_id]
                
                # Cleanup language groups
                lang = state.language_preferences['preferred']
                if lang in self.language_groups:
                    self.language_groups[lang].discard(consultation_id)
                
                # Cleanup Redis data
                await self._cleanup_session_data(consultation_id)
                
                # Remove connection
                del self.active_connections[consultation_id]
                
                logger.info(f"WebSocket disconnected: {consultation_id}")
                
        except Exception as e:
            logger.error(f"Disconnect error: {str(e)}")

    async def _cleanup_session_data(self, consultation_id: str):
        """Cleanup session data from Redis"""
        try:
            if self.redis_client:
                keys_to_delete = [
                    f"{self.redis_prefix}session:{consultation_id}",
                    f"{self.redis_prefix}context:{consultation_id}"
                ]
                
                for key in keys_to_delete:
                    await self.redis_client.delete(key)
                    
        except Exception as e:
            logger.error(f"Cleanup error: {str(e)}")


    # In websocket.py - modify existing _cache_session_data method
    async def _cache_session_data(self, session_id: str, state: ConnectionState):
        """Cache session data in Redis with proper error handling"""
        try:
            if not self.redis_client:
                await self.initialize()
                if not self.redis_client:
                    raise RuntimeError("Redis client unavailable - critical for session management")
                    
            cache_key = f"{self.redis_prefix}session:{session_id}"
            
            # Convert streaming state to dict and handle bytes buffer
            streaming_state = state.streaming_state.model_dump()
            # Remove or encode bytes buffer
            if 'buffer' in streaming_state:
                streaming_state['buffer'] = base64.b64encode(streaming_state['buffer']).decode() if streaming_state['buffer'] else ""
            
            if streaming_state.get('start_time'):
                streaming_state['start_time'] = streaming_state['start_time'].isoformat()
            
            session_data = {
                "language_preferences": state.language_preferences,
                "last_activity": state.last_activity.isoformat(),
                "message_count": state.message_count,
                "streaming_state": streaming_state,
                "user_details": state.user_details,
                "context_id": state.context_id
            }
            
            # Cache with proper error handling
            await self.redis_client.setex(
                cache_key,
                self.cache_ttl,
                json.dumps(session_data)
            )
            
            logger.debug(
                f"Session cached successfully: {session_id}",
                extra={"session_id": session_id}
            )
                
        except Exception as e:
            logger.error(
                f"Critical: Session cache error for {session_id}: {str(e)}",
                exc_info=True,
                extra={"session_id": session_id}
            )
            raise RuntimeError(f"Session caching failed: {str(e)}")


    async def cleanup_session(self, session_id: str):
        """Cleanup session data with proper validation"""
        try:
            if not self.redis_client:
                return
                
            pattern = f"{self.redis_prefix}*:{session_id}"
            deleted_count = 0
            
            async for key in self.redis_client.scan_iter(pattern):
                await self.redis_client.delete(key)
                deleted_count += 1
                
            logger.info(
                f"Session cleanup completed: {deleted_count} keys removed",
                extra={"session_id": session_id}
            )
                
        except Exception as e:
            logger.error(
                f"Session cleanup error for {session_id}: {str(e)}",
                exc_info=True,
                extra={"session_id": session_id}
            )
            
    async def cleanup(self):
        """Cleanup all WebSocket and Redis resources"""
        try:
            # 1. Clean up active WebSocket connections
            for session_id in list(self.active_connections.keys()):
                await self.disconnect(session_id)
            self.active_connections.clear()
            
            # 2. Clean up Redis session data
            if self.redis_client:
                try:
                    # Clean up all keys with our prefix
                    pattern = f"{self.redis_prefix}*"
                    async for key in self.redis_client.scan_iter(pattern):
                        await self.redis_client.delete(key)
                    logger.info("WebSocket Redis sessions cleaned up")
                except Exception as redis_error:
                    logger.error(f"Redis cleanup error: {str(redis_error)}")
            
            # 3. Clean up other resources
            self.language_groups.clear()
            await self.speech_processor.cleanup()
            await self.chat_service.cleanup()
            
            # 4. Reset state
            self.initialized = False
            logger.info("WebSocket manager cleaned up successfully")
            
        except Exception as e:
            logger.error(f"WebSocket cleanup error: {str(e)}")

        

# Global manager instance
manager = ConnectionManager()


@router.websocket("/ws/{consultation_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    consultation_id: str,
    language_preferences: Optional[Dict] = None
):
    """WebSocket endpoint with enhanced error handling"""
    try:
        # Initialize manager if needed
        if not manager.initialized:
            await manager.initialize()
        
        consultation_data = await consultations_collection.find_one(
            {"consultation_id": consultation_id}
        )
        
        if consultation_data:
            # Use stored language preferences from consultation
            stored_preferences = consultation_data.get("language_preferences", {})
            language_preferences = stored_preferences
        else:
            language_preferences = language_preferences or {'preferred': 'en', 'interface': 'en'}

        # Connect new client with consultation context
        try:
            await manager.connect(
                websocket=websocket,
                consultation_id=consultation_id,
                language_preferences=language_preferences
            )

            # Main message processing loop
            while True:
                try:
                    # Receive and process messages
                    data = await websocket.receive_text()
                    message = WebSocketMessage.parse_raw(data)

                    # Process message with error handling
                    await manager.process_message(consultation_id, message)

                except WebSocketDisconnect:
                    logger.info(f"WebSocket disconnected: {consultation_id}")
                    await manager.disconnect(consultation_id)
                    break

                except json.JSONDecodeError as je:
                    logger.error(f"Invalid message format: {str(je)}")
                    continue

                except Exception as message_error:
                    logger.error(f"Message processing error: {str(message_error)}")
                    # Send error message to client if possible
                    try:
                        await websocket.send_json({
                            "type": "error",
                            "content": "Message processing failed"
                        })
                    except:
                        pass

        except Exception as conn_error:
            logger.error(f"Connection error: {str(conn_error)}")
            await manager.disconnect(consultation_id)
            raise

    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        try:
            await websocket.close(code=1000)
        except:
            pass
    finally:
        # Ensure cleanup happens
        try:
            if consultation_id in manager.active_connections:
                await manager.disconnect(consultation_id)
        except Exception as cleanup_error:
            logger.error(f"Cleanup error: {str(cleanup_error)}")

# Initialize and cleanup functions
async def initialize_manager():
    """Initialize WebSocket manager"""
    await manager.initialize()

async def cleanup_manager():
    """Cleanup WebSocket manager"""
    await manager.cleanup()

@router.on_event("shutdown")
async def shutdown_event():
    """Handle application shutdown"""
    try:
        await cleanup_manager()
    except Exception as e:
        logger.error(f"Shutdown error: {str(e)}")
