# backend/app/routes/consultation.py
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from app.models.consultation import (
    ConsultationCreate,
    ConsultationResponse,
    ConsultationUpdate,
    ConsultationSummary,
    MessageContent
)
from app.config.database import DatabaseConfig, consultations_collection, redis_client
from app.services.chat_service import ChatService
from app.utils.speech_processor import SpeechProcessor, ProcessedSpeech
from app.utils.response_validator import AIResponseValidator
from app.config.language_metadata import LanguageMetadata
from datetime import datetime
import logging
import uuid
import json
import asyncio
from typing import Optional, Dict, List
import os

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize services
chat_service = ChatService()
speech_processor = SpeechProcessor()
response_validator = AIResponseValidator()

# Resource management
consultation_semaphore = asyncio.Semaphore(20)
message_semaphore = asyncio.Semaphore(10)

class ConsultationManager:
    """Manages consultation sessions with Redis backing"""
    _instance = None
    _initialized = asyncio.Event()
    _initialization_lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConsultationManager, cls).__new__(cls)
            cls._instance.redis = None
            cls._instance.session_expiry = 3600  # 1 hour
            cls._instance.prefix = "consultation:"
        return cls._instance

    async def initialize(self):
        """Initialize Redis connection"""
        if self._initialized.is_set():
            return

        async with self._initialization_lock:
            if self._initialized.is_set():
                return

            try:
                # Get Redis client from DatabaseConfig
                db_config = DatabaseConfig()
                await db_config.initialize()
                await db_config._initialized.wait()
                
            
                
                # Get Redis client after database initialization
                self.redis = db_config.get_redis()
                if not self.redis:
                    raise RuntimeError("Redis client not available")
                
                # Test Redis connection
                await self.redis.ping()
                
                # Mark as initialized
                self._initialized.set()
                logger.info("ConsultationManager: Redis connection established")
                
            except Exception as e:
                logger.error(f"ConsultationManager initialization error: {str(e)}")
                self._initialized.clear()
                raise RuntimeError(f"Failed to initialize Redis connection: {str(e)}")

    async def create_session(self, consultation_id: str, user_details: Dict) -> Dict:
        """Create new consultation session"""
        if not self._initialized.is_set():
            await self.initialize()

        session = {
            "consultation_id": consultation_id,
            "user_details": user_details,
            "start_time": datetime.utcnow().isoformat(),
            "last_activity": datetime.utcnow().isoformat(),
            "language_preferences": user_details.get("language_preferences", {
                "preferred": "en",
                "interface": "en"
            }),
            "message_history": [],
            "medical_context": {},
            "flow_state": "ready"
        }
        
        try:
            await self.redis.setex(
                f"{self.prefix}{consultation_id}",
                self.session_expiry,
                json.dumps(session)
            )
            return session
        except Exception as e:
            logger.error(f"Redis storage error: {str(e)}")
            raise RuntimeError("Failed to store session in Redis")

    async def get_session(self, consultation_id: str) -> Optional[Dict]:
        """Get session from Redis"""
        if not self._initialized.is_set():
            await self.initialize()

        session_data = await self.redis.get(f"{self.prefix}{consultation_id}")
        if session_data:
            session = json.loads(session_data)
            await self.refresh_session(consultation_id)
            return session
        return None

    async def refresh_session(self, consultation_id: str):
        """Refresh session expiry"""
        await self.redis.expire(
            f"{self.prefix}{consultation_id}",
            self.session_expiry
        )

    async def update_session(self, consultation_id: str, updates: Dict) -> Dict:
        """Update session data"""
        if not self._initialized.is_set():
            await self.initialize()

        session = await self.get_session(consultation_id)
        if not session:
            raise ValueError("Session not found")
            
        session.update(updates)
        session["last_activity"] = datetime.utcnow().isoformat()
        
        await self.redis.setex(
            f"{self.prefix}{consultation_id}",
            self.session_expiry,
            json.dumps(session)
        )
        return session

    async def end_session(self, consultation_id: str):
        """End consultation session"""
        if not self._initialized.is_set():
            await self.initialize()

        session = await self.get_session(consultation_id)
        if session:
            await self._save_session_state(consultation_id, session)
            await self.redis.delete(f"{self.prefix}{consultation_id}")

    async def _save_session_state(self, consultation_id: str, session: Dict):
        """Save final session state to MongoDB"""
        try:
            await consultations_collection.update_one(
                {"consultation_id": consultation_id},
                {
                    "$set": {
                        "status": "completed",
                        "last_activity": datetime.utcnow(),
                        "chat_history": session["message_history"],
                        "medical_context": session["medical_context"],
                        "completed_at": datetime.utcnow()
                    }
                }
            )
        except Exception as e:
            logger.error(f"Error saving session state: {str(e)}")

# Initialize manager
consultation_manager = ConsultationManager()

@router.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    try:
        await consultation_manager.initialize()
        await chat_service.initialize()
        await speech_processor.initialize()
        logger.info("All services initialized successfully")
    except Exception as e:
        logger.error(f"Service initialization error: {str(e)}")
        raise

@router.post("/start", response_model=ConsultationResponse)
async def start_consultation(
    user_data: ConsultationCreate,
    background_tasks: BackgroundTasks
):
    # Initialize database and consultation manager
    db_config = DatabaseConfig()
    await db_config.initialize()
    await db_config._initialized.wait()

    # Get MongoDB and Redis clients
    mongodb = db_config.get_mongodb()
    redis = db_config.get_redis()
    logger.info("Database connections established")

    # Verify services are available
    if not mongodb or not redis:
        logger.error("Database services unavailable")
        raise HTTPException(
            status_code=503,
            detail="Database services unavailable. Please try again in a few moments."
        )

    # Get fresh collection reference
    db = mongodb[os.getenv("DATABASE_NAME", "arogo_bhasini2")]
    consultations = db.consultations

    # Verify Redis is available
    redis = db_config.get_redis()
    if not redis:
        raise HTTPException(
            status_code=503,
            detail="Service temporarily unavailable. Please try again in a few moments."
        )
    
    # Initialize consultation manager
    await consultation_manager.initialize()
    
    """Start a new consultation session."""
    async with consultation_semaphore:
        try:
            logger.info("Starting new consultation")

            # Generate consultation ID
            consultation_id = str(uuid.uuid4())
            
            # Validate language support
            preferred_lang = user_data.language_preferences.preferred
            interface_lang = user_data.language_preferences.interface
            
            if not all(LanguageMetadata.is_language_supported(lang) 
                      for lang in [preferred_lang, interface_lang]):
                raise ValueError("Unsupported language configuration")
            
            # Create consultation data
            consultation_data = {
                "consultation_id": consultation_id,
                "user_details": {
                    "first_name": user_data.first_name,  # Explicitly include first_name
                    "last_name": user_data.last_name,
                    **user_data.dict(exclude={'first_name', 'last_name'})
                },
                "status": "active",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "language_preferences": {
                    "preferred": user_data.language_preferences.preferred,
                    "interface": user_data.language_preferences.interface,
                    "auto_detect": True
                }
            }

            # Use the fresh collection reference
            await consultations.insert_one(consultation_data)
            
            # Create session with logging
            session = await consultation_manager.create_session(consultation_id, user_data.dict())
            logger.info(f"Session created: {session}")
            
            # Initialize services in background
            background_tasks.add_task(
                initialize_consultation_resources,
                consultation_id,
                user_data.dict()
            )
            
            return ConsultationResponse(
                consultation_id=consultation_id,
                user_details=user_data.dict(),
                status="active",
                language_preferences=session["language_preferences"],
                messages=[],
                created_at=consultation_data["created_at"],
                updated_at=consultation_data["updated_at"],
                last_activity=consultation_data["updated_at"]
            )
            
        except ValueError as ve:
            logger.error(f"Validation error: {str(ve)}")
            raise HTTPException(status_code=422, detail=str(ve))
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
        
@router.get("/status/{consultation_id}")
async def get_consultation_status(consultation_id: str):
    try:
        # Initialize database and get collections
        db_config = DatabaseConfig()
        await db_config.initialize()
        await db_config._initialized.wait()
        
        # Get MongoDB client
        mongodb = db_config.get_mongodb()
        if not mongodb:
            raise HTTPException(
                status_code=503,
                detail="Database service unavailable"
            )
            
        # Get fresh collection reference
        db = mongodb[os.getenv("DATABASE_NAME", "arogo_bhasini2")]
        consultations = db.consultations
        
        # Get consultation status
        consultation = await consultations.find_one(
            {"consultation_id": consultation_id}
        )
        
        if not consultation:
            raise HTTPException(status_code=404, detail="Consultation not found")
        
        # Update last activity
        await consultations.update_one(
            {"consultation_id": consultation_id},
            {"$set": {"last_activity": datetime.utcnow()}}
        )
            
        return {
            "status": consultation["status"],
            "user_details": consultation["user_details"],
            "language_preferences": consultation["language_preferences"],
            "created_at": consultation["created_at"],
            "last_activity": consultation.get("last_activity", consultation["created_at"])
        }
    except Exception as e:
        logger.error(f"Error getting consultation status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))



@router.post("/message/{consultation_id}")
async def handle_message(
    consultation_id: str,
    message: Dict,
    background_tasks: BackgroundTasks
):
    """Handle incoming messages following our flow:
    User Speech → Transcription (Native) → English Translation → Gemini → Translation to Native → Response
    """
    async with message_semaphore:
        try:
            session = await consultation_manager.get_session(consultation_id)
            if not session:
                raise HTTPException(status_code=404, detail="Consultation not found")

            # Get language preferences
            language_prefs = session["language_preferences"]
            source_language = message.get("language", language_prefs["preferred"])
            
            # Process based on message type
            if message.get("type") == "audio":
                # 1. Speech to Text (Native)
                speech_result = await speech_processor.process_speech(
                    audio_data=message["content"],
                    source_language=source_language
                )
                original_text = speech_result.original_text
                english_text = speech_result.english_text
            else:
                # Text message
                original_text = message["content"]
                if source_language != "en":
                    # 2. Translate to English
                    translation = await chat_service.translate_to_english(
                        text=original_text,
                        source_language=source_language
                    )
                    english_text = translation["text"]
                else:
                    english_text = original_text

            # 3. Process with Gemini
            ai_response = await chat_service.process_message(
                consultation_id=consultation_id,
                message=english_text,
                context=session["message_history"]
            )

            # 4. Translate response to native language if needed
            final_response = ai_response.copy()
            if language_prefs["preferred"] != "en":
                translated = await chat_service.translate_to_language(
                    text=ai_response["response"],
                    source_language="en",
                    target_language=language_prefs["preferred"]
                )
                final_response["response"] = translated["text"]

            # Update session history
            await update_message_history(
                session,
                consultation_id,
                original_text,
                english_text,
                final_response,
                source_language,
                message.get("type", "text")
            )

            # Background tasks
            background_tasks.add_task(
                update_consultation_data,
                consultation_id,
                session
            )

            return final_response

        except Exception as e:
            logger.error(f"Error handling message: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

async def update_message_history(
    session: Dict,
    consultation_id: str,
    original_text: str,
    english_text: str,
    response: Dict,
    source_language: str,
    message_type: str
):
    """Update message history with full conversation flow"""
    history_entry = {
        "user_message": {
            "type": message_type,
            "original_text": original_text,
            "english_text": english_text,
            "language": source_language,
            "timestamp": datetime.utcnow().isoformat()
        },
        "system_response": {
            "original_text": response.get("english_response", response["response"]),
            "translated_text": response["response"],
            "language": session["language_preferences"]["preferred"],
            "timestamp": datetime.utcnow().isoformat()
        }
    }
    
    session["message_history"].append(history_entry)
    await consultation_manager.update_session(consultation_id, session)

async def initialize_consultation_resources(
    consultation_id: str,
    user_details: Dict
):
    """Initialize consultation resources"""
    try:
        await chat_service.initialize_conversation(
            consultation_id,
            user_details
        )
        await speech_processor.initialize()
        logger.info(f"Resources initialized for consultation: {consultation_id}")
    except Exception as e:
        logger.error(f"Resource initialization error: {str(e)}")

async def update_consultation_data(
    consultation_id: str,
    session: Dict
):
    """Update consultation data in MongoDB"""
    try:
        await consultations_collection.update_one(
            {"consultation_id": consultation_id},
            {
                "$set": {
                    "updated_at": datetime.utcnow(),
                    "last_activity": datetime.utcnow(),
                    "chat_history": session["message_history"],
                    "medical_context": session["medical_context"]
                }
            }
        )
    except Exception as e:
        logger.error(f"Error updating consultation data: {str(e)}")

@router.on_event("shutdown")
async def cleanup_sessions():
    """Cleanup active sessions on shutdown"""
    try:
        session_keys = await consultation_manager.redis.keys(f"{consultation_manager.prefix}*")
        for key in session_keys:
            consultation_id = key.split(":")[-1]
            await consultation_manager.end_session(consultation_id)
    except Exception as e:
        logger.error(f"Session cleanup error: {str(e)}")