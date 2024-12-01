# backend/app/services/chat_service.py
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
import json
import logging
import asyncio
from app.utils.ai_config import GeminiConfig
from app.utils.symptom_analyzer import SymptomAnalyzer
from app.config.database import DatabaseConfig, redis_client, consultations_collection
from app.utils.speech_processor import SpeechProcessor
from app.config.language_metadata import LanguageMetadata
from app.utils.translation_cache import TranslationCache
import os

logger = logging.getLogger(__name__)

class ConversationContext(BaseModel):
    """Model for conversation context"""
    consultation_id: str
    messages: List[Dict] = []
    language_preferences: Dict
    medical_context: Dict = {}
    last_activity: datetime
    metadata: Dict = {}

class ChatMessage(BaseModel):
    """Model for chat messages"""
    content: str
    english_content: Optional[str] = None
    language_code: str
    message_type: str = "text"
    confidence: float = 1.0
    metadata: Dict = {}
    timestamp: datetime

class ProcessedResponse(BaseModel):
    """Model for processed AI responses"""
    original_text: str = Field(..., description="Response in English")
    translated_text: Optional[str] = Field(None, description="Translated response")
    language_code: str
    confidence: float
    medical_terms: List[str] = []
    emergency_level: str = "none"
    metadata: Dict = {}
    timestamp: datetime

class ChatService:
    """Handles chat processing following our flow:
    Message → (Native/English check) → English Translation → Gemini → Native Translation → Response
    """
    # Class-level constants for configuration
    CACHE_TTL = 3600  # 1 hour
    PREFIXES = {
        "context": "chat_context:",
        "session": "chat_session:"
    }
    max_context_messages = 10

    def __init__(self):
        self.initialized = False
        self.redis_client = None
        self._initialization_lock = asyncio.Lock()
        self.mongodb = None  # Add this line
        
        # Core services
        self.translation_cache = TranslationCache()
        self.ai_config = GeminiConfig()
        self.symptom_analyzer = None
        self.speech_processor = None
        
        # Resource management
        self.processing_semaphore = asyncio.Semaphore(10)
        
        # Initialize state
        self.initialized = False

    async def initialize(self):
        """Initialize chat service with proper locking"""
        async with self._initialization_lock:
            if self.initialized:
                return

            try:
                # Initialize database
                db_config = DatabaseConfig()
                await db_config.initialize()
                await db_config._initialized.wait()
                
                # Get database connections
                self.redis_client = await db_config.get_redis()
                self.mongodb = db_config.get_mongodb()
                
                if not self.mongodb:
                    raise RuntimeError("MongoDB client unavailable")
                
                # Get collection reference
                db = self.mongodb[os.getenv("DATABASE_NAME")]
                self.consultations_collection = db.consultations

                # Initialize core services
                await self.translation_cache.initialize()
                self.speech_processor = SpeechProcessor()
                await self.speech_processor.initialize()
                self.symptom_analyzer = SymptomAnalyzer()

                # Verify Redis
                await self._verify_redis()
                self.initialized = True
                logger.info("Chat service initialized successfully")

            except Exception as e:
                self.initialized = False
                logger.error(f"Chat service initialization failed: {str(e)}")
                raise

    async def _verify_redis(self):
        """Verify Redis connection with ping"""
        try:
            if not self.redis_client:
                raise RuntimeError("Redis client not available")
            await self.redis_client.ping()
            logger.info("Redis connection verified")
        except Exception as e:
            raise RuntimeError(f"Redis verification failed: {str(e)}")

# Context management methods
    async def _get_or_create_context(
        self,
        consultation_id: str,
        source_language: str,
        context: Optional[Dict] = None
    ) -> ConversationContext:
        """Get or create conversation context with minimal language handling.
        Focuses on maintaining conversation history and medical context
        since language handling is primarily done in speech processor."""
        
        if not self.redis_client:
            await self.initialize()
            if not self.redis_client:
                raise RuntimeError("Redis unavailable - Cannot proceed without Redis connection")

        try:
            # Try to get existing context
            cached = await self._get_cached_context(consultation_id)
            if cached:
                # Only update last activity
                cached.last_activity = datetime.utcnow()
                await self._cache_context(consultation_id, cached)
                logger.info(f"Retrieved existing context for consultation: {consultation_id}")
                return cached

            # Create new context with minimal configuration
            new_context = ConversationContext(
                consultation_id=consultation_id,
                language_preferences={"source_language": source_language},  # Minimal language info
                messages=[],
                medical_context={
                    "symptoms": [],
                    "risk_level": "unknown",
                    "recommendations": {},
                    "last_updated": datetime.utcnow().isoformat()
                },
                last_activity=datetime.utcnow(),
                metadata={
                    "created_at": datetime.utcnow().isoformat(),
                    "session_type": "medical_consultation"
                }
            )
            
            await self._cache_context(consultation_id, new_context)
            logger.info(f"Created new context for consultation: {consultation_id}")
            return new_context

        except Exception as e:
            logger.error(f"Context handling error: {str(e)}", exc_info=True)
            raise RuntimeError(f"Failed to manage context: {str(e)}")

    async def _cache_context(self, consultation_id: str, context: ConversationContext):
        """Cache context with enhanced error handling and validation"""
        if not self.redis_client:
            raise RuntimeError("Redis client unavailable - Cannot cache context")

        try:
            # Validate context before caching
            if not isinstance(context, ConversationContext):
                raise ValueError("Invalid context object")
            
            # Prepare context for serialization with validation
            context_data = context.dict(exclude={'websocket'})
            
            # Update timestamps
            current_time = datetime.utcnow()
            context_data.update({
                "last_activity": current_time.isoformat(),
                "metadata": {
                    **context_data.get("metadata", {}),
                    "last_cached": current_time.isoformat(),
                    "cache_version": "2.0"
                }
            })
            
            # Serialize with enhanced error handling
            try:
                serialized = json.dumps(
                    context_data,
                    default=lambda x: x.isoformat() if isinstance(x, datetime) else str(x)
                )
            except (TypeError, ValueError) as e:
                raise RuntimeError(f"Context serialization failed: {str(e)}")
            
            # Cache with TTL and retry logic
            cache_key = f"{self.PREFIXES['context']}{consultation_id}"
            retry_count = 0
            max_retries = 3
            
            while retry_count < max_retries:
                try:
                    await self.redis_client.setex(
                        cache_key,
                        self.CACHE_TTL,
                        serialized
                    )
                    logger.info(
                        f"Context cached successfully - "
                        f"consultation: {consultation_id}, "
                        f"size: {len(serialized)} bytes"
                    )
                    return
                except Exception as e:
                    retry_count += 1
                    if retry_count == max_retries:
                        raise RuntimeError(f"Redis caching failed after {max_retries} attempts")
                    await asyncio.sleep(0.5 * retry_count)
            
        except Exception as e:
            logger.error(
                f"Critical cache error for {consultation_id}: {str(e)}", 
                exc_info=True
            )
            raise RuntimeError(f"Cache operation failed: {str(e)}")

    async def _get_cached_context(self, consultation_id: str) -> Optional[ConversationContext]:
        """Get cached context with enhanced validation and error handling"""
        if not self.redis_client:
            raise RuntimeError("Redis client unavailable - Cannot retrieve context")

        try:
            cache_key = f"{self.PREFIXES['context']}{consultation_id}"
            data = await self.redis_client.get(cache_key)
            
            if data:
                try:
                    # Parse and validate context data
                    context_data = json.loads(data)
                    
                    # Validate required fields
                    required_fields = {'consultation_id', 'language_preferences', 'medical_context'}
                    if not all(field in context_data for field in required_fields):
                        raise ValueError("Cached context missing required fields")
                    
                    # Create context object with validation
                    context = ConversationContext(**context_data)
                    
                    # Update last activity
                    context.last_activity = datetime.utcnow()
                    
                    logger.info(
                        f"Retrieved valid cached context - "
                        f"consultation: {consultation_id}, "
                        f"language: {context.language_preferences.get('preferred', 'unknown')}"
                    )
                    return context
                    
                except (json.JSONDecodeError, ValueError) as e:
                    logger.error(f"Invalid cached context format: {str(e)}")
                    # Delete invalid cache entry
                    await self.redis_client.delete(cache_key)
                    return None
                    
            logger.info(f"No cached context found for consultation: {consultation_id}")
            return None
                
        except Exception as e:
            logger.error(
                f"Cache retrieval error for {consultation_id}: {str(e)}", 
                exc_info=True
            )
            raise RuntimeError(f"Context retrieval failed: {str(e)}")

    async def _validate_and_cache_context(self, consultation_id: str, context: ConversationContext):
        """Validate and cache context with enhanced error handling"""
        try:
            # Validate context structure
            if not hasattr(context, 'language_preferences') or not context.language_preferences:
                raise ValueError("Invalid context: missing language preferences")
                
            if not hasattr(context, 'medical_context') or not context.medical_context:
                raise ValueError("Invalid context: missing medical context")
                
            # Cache context
            await self._cache_context(consultation_id, context)
            
        except Exception as e:
            logger.error(f"Context validation failed: {str(e)}")
            raise RuntimeError(f"Cannot cache invalid context: {str(e)}")
    
    async def initialize_conversation(
        self,
        consultation_id: str,
        user_details: Dict
    ) -> None:
        """Initialize a new conversation with user context"""
        if not self.initialized:
            await self.initialize()

        try:
            # Create initial conversation context
            conversation_context = ConversationContext(
                consultation_id=consultation_id,
                language_preferences={
                    "preferred": user_details.get("preferred_language", "en"),
                    "interface": user_details.get("interface_language", "en")
                },
                medical_context={
                    "user_details": {
                        "age": user_details.get("age"),
                        "gender": user_details.get("gender"),
                        "vitals": user_details.get("vitals", {})
                    },
                    "symptoms": [],
                    "risk_level": "unknown"
                },
                last_activity=datetime.utcnow(),
                metadata={
                    "created_at": datetime.utcnow().isoformat(),
                    "device_info": user_details.get("device_info", {})
                }
            )
            
            # Cache the initial context
            await self._cache_context(consultation_id, conversation_context)
            logger.info(f"Conversation initialized for consultation: {consultation_id}")
            
        except Exception as e:
            logger.error(f"Conversation initialization error: {str(e)}")
            raise


    async def process_message(
        self,
        consultation_id: str,
        message: str,
        source_language: str,
        context: Optional[Dict] = None
    ) -> ProcessedResponse:
        """Process message with streamlined flow - language handling delegated to speech processor"""
        if not self.initialized:
            await self.initialize()
        
        async with self.processing_semaphore:
            try:
                logger.info(f"""
    === Starting Message Processing ===
    Consultation ID: {consultation_id}
    Source Language: {source_language}
    Message Length: {len(message)} chars
    Timestamp: {datetime.utcnow().isoformat()}
                """)
                
                # 1. Get minimal context
                conversation_context = await self._get_or_create_context(
                    consultation_id,
                    source_language,
                    context
                )
                
                logger.info(f"""
    === Context Information ===
    Preferred Language: {conversation_context.language_preferences.get('preferred')}
    Interface Language: {conversation_context.language_preferences.get('interface')}
    Message Count: {len(conversation_context.messages)}
                """)
                
                # 2. Get English content using speech processor
                logger.info(f"Processing input text in {source_language}")
                processed_input = await self.speech_processor.process_input(
                    content=message,
                    source_language=source_language
                )
                
                english_text = processed_input.english_text or message
                logger.info(f"""
    === Input Processing Results ===
    Original Text: {message[:100]}...
    English Text: {english_text[:100]}...
    Translation Required: {source_language != 'en'}
    Confidence: {processed_input.confidence}
                """)
                
                # 3. Generate AI response in English
                logger.info("Generating AI response in English")
                ai_response = await self._generate_ai_response(
                    english_text,
                    conversation_context
                )
                logger.info(f"""
    === AI Response Generated ===
    Response Length: {len(ai_response)} chars
    Preview: {ai_response[:100]}...
                """)

                # 4. Process medical content
                medical_analysis = await self._analyze_medical_content(
                    ai_response,
                    conversation_context
                )
                logger.info(f"""
    === Medical Analysis Results ===
    Emergency Level: {medical_analysis.get('emergency_level', 'none')}
    Symptoms Detected: {len(medical_analysis.get('symptoms', []))}
                """)
                
                # 5. Process output with translation and TTS
                logger.info(f"""
    === Starting Output Processing ===
    Target Language: {source_language}
    Translation Required: {source_language != 'en'}
    Original Response: {ai_response[:100]}...
                """)

                if source_language != "en":
                    logger.info("Executing non-English response flow")
                    # First translate AI response
                    translation_result = await self.speech_processor.process_output(
                        input_text=ai_response,
                        english_text=ai_response,
                        target_language=source_language,
                        generate_speech=False
                    )
                    translated_text = translation_result.get("translated_text")
                    logger.info(f"""
    === Translation Results ===
    Target Language: {source_language}
    Translation Length: {len(translated_text) if translated_text else 0} chars
    Preview: {translated_text[:100] if translated_text else 'No translation'}...
                    """)

                    # Then generate TTS in target language
                    processed_response = await self.speech_processor.process_output(
                        input_text=translated_text,
                        english_text=ai_response,
                        target_language=source_language,
                        generate_speech=True
                    )
                else:
                    logger.info("Executing English-only response flow")
                    processed_response = await self.speech_processor.process_output(
                        input_text=ai_response,
                        english_text=ai_response,
                        target_language="en",
                        generate_speech=True
                    )
                    translated_text = processed_response.get("translated_text", ai_response)

                audio_data = processed_response.get("audio_data")
                confidence = processed_response.get("confidence", 1.0)
                
                logger.info(f"""
    === Speech Processing Results ===
    Audio Generated: {bool(audio_data)}
    Audio Size: {len(audio_data) if audio_data else 0} bytes
    Confidence: {confidence}
                """)
                
                # 6. Update conversation context
                await self._update_conversation_context(
                    conversation_context,
                    ChatMessage(
                        content=message,
                        english_content=english_text,
                        language_code=source_language,
                        timestamp=datetime.utcnow()
                    ),
                    ai_response,
                    translated_text,
                    medical_analysis
                )

                # 7. Create final response with enhanced metadata
                response = ProcessedResponse(
                    original_text=ai_response,
                    translated_text=translated_text,
                    language_code=source_language,
                    confidence=confidence,
                    medical_terms=medical_analysis.get("medical_terms", []),
                    emergency_level=medical_analysis.get("emergency_level", "none"),
                    metadata={
                        "consultation_id": consultation_id,
                        "medical_analysis": medical_analysis,
                        "source_language": source_language,
                        "timestamp": datetime.utcnow().isoformat(),
                        "tts_data": audio_data,
                        "processing_path": "translation" if source_language != "en" else "direct",
                        "response_metrics": {
                            "input_length": len(message),
                            "output_length": len(translated_text),
                            "processing_confidence": confidence,
                            "translation_status": {
                                "status": "completed" if source_language != "en" else "not_needed",
                                "confidence": confidence,
                                "preserved_terms": processed_response.get("metadata", {}).get("translation_status", {}).get("preserved_terms", [])
                            }
                        },
                        "language_info": {
                            "code": source_language,
                            "name": LanguageMetadata.get_language_name(source_language),
                            "script": LanguageMetadata.get_language_metadata(source_language).get("script")
                        }
                    },
                    timestamp=datetime.utcnow()
                )
                
                logger.info(f"""
    === Processing Complete ===
    Consultation ID: {consultation_id}
    Final Response Length: {len(translated_text)} chars
    Processing Path: {response.metadata['processing_path']}
    Translation Status: {response.metadata['response_metrics']['translation_status']['status']}
                """)
                
                return response

            except Exception as e:
                logger.error(f"""
    === Critical Processing Error ===
    Consultation ID: {consultation_id}
    Error: {str(e)}
    Source Language: {source_language}
    Processing Stage: {locals().get('current_stage', 'unknown')}
                """, exc_info=True)
                raise RuntimeError(f"Message processing failed: {str(e)}")



    async def _generate_ai_response(
        self,
        message: str,
        context: ConversationContext
    ) -> str:
        """Generate AI response using Gemini with controlled conversation flow"""
        try:
            # Get user details and context
            medical_context = context.medical_context
            user_details = medical_context.get('user_details', {})  # Changed from medical_context
            first_name = user_details.get('first_name', 'Patient')  # Default to 'Patient' if name not found
            medical_context = context.medical_context
            symptoms = medical_context.get('symptoms', [])

            # Track conversation state
            question_count = sum(1 for msg in context.messages if msg.get('type') == 'assistant' and '?' in msg.get('content', ''))
            is_first_message = len(context.messages) <= 1
            is_assessment_phase = question_count >= 5 or medical_context.get('emergency_level') == 'high'

            # Format conversation history
            conversation_history = self._format_conversation_history(context)

            # Build dynamic prompt based on conversation phase
            if is_first_message:
                prompt_template = f"""
                You are a friendly medical AI assistant.
                
                TASK:
                1. Greet {first_name} warmly
                2. Ask ONE specific question about their main symptom
                
                Current Symptoms: {message}
                
                FORMAT:
                Greeting and single question only
                Example: "Hello {first_name} To better understand your condition, could you tell me..."
                
                RULES:
                - Warm, professional greeting using patient's name
                - ONE focused question
                - No medical advice yet
                - Response under 50 words
                """
            elif is_assessment_phase:
                prompt_template = f"""
                Medical Assessment Phase
                
                Patient: {first_name}
                Symptoms Identified: {json.dumps(symptoms)}
                Conversation History: {conversation_history}
                
                TASK:
                Provide a clear assessment including:
                1. Symptom summary
                2. Possible conditions
                3. Recommended next steps
                4. Urgency level
                
                FORMAT:
                Clear sections without brackets
                Professional but accessible language
                
                RULES:
                - Structured assessment
                - Clear recommendations
                - Include urgency level
                - No technical jargon
                """
            else:
                prompt_template = f"""
                Medical Consultation Progress
                
                Patient: {first_name}
                Questions Asked: {question_count}/5
                Current Symptoms: {json.dumps(symptoms)}
                Last Response: {message}
                
                TASK:
                Ask ONE strategic follow-up question about:
                - Symptom details
                - Timeline
                - Related conditions
                - Impact on daily life
                
                FORMAT:
                Direct question without brackets
                
                RULES:
                - Single focused question
                - Build on previous answers
                - No medical advice yet
                - Clear, simple language
                """

            # Generate response
            response = self.ai_config.model.generate_content(prompt_template)
            cleaned_response = response.text.strip().strip('[]')

            # Log response details
            logger.info(f"AI Response Generated:")
            logger.info(f"Phase: {'Assessment' if is_assessment_phase else 'Question'}")
            logger.info(f"Question Count: {question_count}")
            logger.info(f"Response: {cleaned_response}")

            return cleaned_response

        except Exception as e:
            logger.error(f"Error generating AI response: {str(e)}")
            raise

    async def _analyze_medical_content(
        self,
        response: str,
        context: ConversationContext
    ) -> Dict:
        """Analyze medical content in response"""
        try:
            # Get medical analysis
            analysis = await self.symptom_analyzer.analyze_conversation(
                context.messages + [{"content": response}]
            )

            # Get recommendations if needed
            if analysis.get("symptoms"):
                recommendations = await self.symptom_analyzer.get_treatment_recommendations(
                    analysis["symptoms"]
                )
                analysis["recommendations"] = recommendations

            return analysis

        except Exception as e:
            logger.error(f"Error analyzing medical content: {str(e)}")
            raise

    def _format_medical_context(self, context: ConversationContext) -> str:
        """Format medical context for AI prompt"""
        return json.dumps({
            "medical_history": context.medical_context.get("medical_history", {}),
            "identified_symptoms": context.medical_context.get("symptoms", []),
            "risk_level": context.medical_context.get("risk_level", "unknown"),
            "previous_recommendations": context.medical_context.get("recommendations", {})
        }, indent=2)

    def _format_conversation_history(self, context: ConversationContext) -> str:
        """Format recent conversation history"""
        recent_messages = context.messages[-self.max_context_messages:]
        formatted = []
        
        for msg in recent_messages:
            role = "Patient" if msg.get("type") == "user" else "Assistant"
            content = msg.get("english_content") or msg.get("content")
            formatted.append(f"{role}: {content}")
        
        return "\n".join(formatted)


    async def _update_conversation_context(
        self,
        context: ConversationContext,
        user_message: ChatMessage,
        ai_response: str,
        translated_response: Optional[str],
        medical_analysis: Dict
    ):
        """Update conversation context"""
        try:
            # Add messages to history
            context.messages.append({
                "type": "user",
                "content": user_message.content,
                "english_content": user_message.english_content,
                "timestamp": user_message.timestamp.isoformat()
            })

            context.messages.append({
                "type": "assistant",
                "content": translated_response or ai_response,
                "english_content": ai_response,
                "timestamp": datetime.utcnow().isoformat()
            })

            # Update medical context
            if medical_analysis:
                context.medical_context.update({
                    "symptoms": medical_analysis.get("symptoms", []),
                    "risk_level": medical_analysis.get("risk_level", "unknown"),
                    "recommendations": medical_analysis.get("recommendations", {})
                })

            # Trim message history if needed
            if len(context.messages) > self.max_context_messages * 2:
                context.messages = context.messages[-self.max_context_messages*2:]

            # Update last activity
            context.last_activity = datetime.utcnow()

            # Store updated context
            await self._cache_context(context.consultation_id, context)
            
            # Update database
            await self._update_database_context(context)

        except Exception as e:
            logger.error(f"Error updating context: {str(e)}")
            raise

    async def _update_database_context(self, context: ConversationContext):
        try:
            if self.consultations_collection is None:
                return
                
            await self.consultations_collection.update_one(
                {"consultation_id": context.consultation_id},
                {
                    "$set": {
                        "chat_history": context.messages,
                        "medical_context": context.medical_context,
                        "language_preferences": {
                            "preferred": context.language_preferences.get("preferred", "en"),
                            "interface": context.language_preferences.get("interface", "en")
                        },
                        "updated_at": datetime.utcnow()
                    }
                },
                upsert=True
            )
            logger.info(f"Database context updated for {context.consultation_id}")
        except Exception as e:
            logger.error(f"Database update error: {str(e)}")


    async def cleanup(self):
        """Cleanup chat service resources including Redis"""
        try:
            # 1. Clean up Redis context data
            if self.redis_client:
                try:
                    # Clean up context data
                    context_pattern = f"{self.context_prefix}*"
                    async for key in self.redis_client.scan_iter(context_pattern):
                        await self.redis_client.delete(key)
                        
                    # Clean up session data
                    session_pattern = f"{self.session_prefix}*"
                    async for key in self.redis_client.scan_iter(session_pattern):
                        await self.redis_client.delete(key)
                    
                    logger.info("Chat service Redis data cleaned up")
                except Exception as redis_error:
                    logger.error(f"Redis cleanup error: {str(redis_error)}")
            
            # 2. Clean up translation cache
            if self.translation_cache:
                await self.translation_cache.cleanup()
            
            # 3. Clean up speech processor
            if self.speech_processor:
                await self.speech_processor.cleanup()
            
            # 4. Reset state
            self.initialized = False
            self.redis_client = None  # Clear Redis client reference
            logger.info("Chat service cleaned up successfully")
            
        except Exception as e:
            logger.error(f"Chat service cleanup error: {str(e)}")