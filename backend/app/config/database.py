# backend/app/config/database.py
from motor.motor_asyncio import AsyncIOMotorClient
from redis.asyncio import Redis as AsyncRedis
from typing import Optional, Dict
from dotenv import load_dotenv
import logging
import asyncio
import os

logger = logging.getLogger(__name__)
load_dotenv()

# Global instances for access across modules
mongodb_client: Optional[AsyncIOMotorClient] = None
redis_client: Optional[AsyncRedis] = None
consultations_collection = None
translations_cache = None

class DatabaseConfig:
    """Singleton database configuration with async initialization"""
    _instance = None
    _initialized = asyncio.Event()
    _lock = asyncio.Lock()

    def __new__(cls):
        if not cls._instance:
            cls._instance = super().__new__(cls)
            cls._instance.mongodb = None
            cls._instance.redis = None
            cls._instance.db = None
            cls._instance.consultations = None
            cls._instance.translations = None
        return cls._instance
    
    @classmethod
    async def get_redis(cls) -> AsyncRedis:
        """Get initialized Redis client with recovery"""
        if not cls._initialized.is_set():
            await cls.initialize()
        
        if not redis_client:
            raise RuntimeError("Redis client unavailable - critical for chat operations")
        
        try:
            # Verify connection is alive
            await redis_client.ping()
            return redis_client
        except Exception as e:
            logger.error(f"Redis connection error: {str(e)}")
            # Try to recover once
            await cls.initialize()
            if not redis_client:
                raise RuntimeError("Redis connection failed - chat operations unavailable")
            return redis_client

    @classmethod
    async def initialize(cls) -> None:
        """Initialize database connections with Redis as critical"""
        if cls._initialized.is_set():
            return

        async with cls._lock:
            if cls._initialized.is_set():
                return

            try:
                logger.info("Starting database initialization...")
                    
                # Initialize MongoDB first
                mongo_url = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
                cls._instance.mongodb = AsyncIOMotorClient(
                    mongo_url,
                    maxPoolSize=50,
                    minPoolSize=5
                )
                
                # Set up MongoDB collections
                db_name = os.getenv("DATABASE_NAME")
                cls._instance.db = cls._instance.mongodb[db_name]
                cls._instance.consultations = cls._instance.db.consultations
                cls._instance.translations = cls._instance.db.translations

                # Verify MongoDB immediately
                await cls._instance.mongodb.admin.command('ping')
                logger.info("MongoDB connection verified")

                # Set global MongoDB variables
                global mongodb_client, consultations_collection, translations_cache
                mongodb_client = cls._instance.mongodb
                consultations_collection = cls._instance.consultations
                translations_cache = cls._instance.translations

                # Initialize Redis
                # Redis initialization - now critical
                redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
                retry_count = 0
                max_retries = 3
                
                while retry_count < max_retries:
                    try:
                        cls._instance.redis = AsyncRedis.from_url(
                            redis_url,
                            max_connections=20,
                            decode_responses=True
                        )
                        
                        # Verify Redis connection
                        await cls._instance.redis.ping()
                        global redis_client
                        redis_client = cls._instance.redis
                        
                        logger.info("Redis connection established")
                        break
                        
                    except Exception as redis_error:
                        retry_count += 1
                        if retry_count >= max_retries:
                            raise RuntimeError(f"Redis initialization failed after {max_retries} attempts")
                        logger.warning(f"Redis connection attempt {retry_count} failed, retrying...")
                        await asyncio.sleep(1)
                
                if not cls._instance.redis or not redis_client:
                    raise RuntimeError("Redis client initialization failed - critical service unavailable")
                
                logger.info("Redis connection verified")  

                # Set up indexes after connections are verified
                await cls._setup_indexes()
                
                cls._initialized.set()
                logger.info("Database initialization completed successfully")

            except Exception as e:
                logger.error(f"Database initialization failed: {str(e)}")
                await cls.cleanup()
                raise RuntimeError(f"Database initialization failed: {str(e)}")

    @classmethod
    async def _setup_indexes(cls) -> None:
        """Set up database indexes with proper error handling"""
        try:
            # Get existing indexes
            existing_indexes = await cls._instance.consultations.list_indexes().to_list(None)
            existing_names = {idx.get('name') for idx in existing_indexes}

            # Create consultation_id index (without TTL)
            if "consultation_id_idx" not in existing_names:
                try:
                    await cls._instance.consultations.create_index(
                        [("consultation_id", 1)],
                        unique=True,
                        name="consultation_id_idx"
                    )
                    logger.info("Created index: consultation_id_idx")
                except Exception as e:
                    logger.warning(f"Index creation warning for consultation_id_idx: {str(e)}")

            # Create created_at index (with TTL)
            if "created_at_idx" not in existing_names:
                try:
                    await cls._instance.consultations.create_index(
                        [("created_at", 1)],
                        expireAfterSeconds=2592000,  # 30 days TTL
                        name="created_at_idx"
                    )
                    logger.info("Created index: created_at_idx")
                except Exception as e:
                    logger.warning(f"Index creation warning for created_at_idx: {str(e)}")

            # Translation cache index
            try:
                await cls._instance.translations.create_index(
                    [("text_hash", 1), ("source_lang", 1), ("target_lang", 1)],
                    unique=True,
                    name="translation_lookup_idx",
                    background=True
                )
                logger.info("Created index: translation_lookup_idx")
            except Exception as e:
                logger.warning(f"Index creation warning for translation_lookup_idx: {str(e)}")

            logger.info("Database indexes setup completed")
                
        except Exception as e:
            logger.error(f"Index setup error: {str(e)}")

    @classmethod
    async def verify_connections(cls) -> bool:
        """Verify all database connections are active"""
        try:
            if not cls._initialized.is_set():
                return False
                
            # Verify MongoDB
            await cls._instance.mongodb.admin.command('ping')
            
            # Verify Redis
            await cls._instance.redis.ping()
            
            return True
            
        except Exception as e:
            logger.error(f"Connection verification failed: {str(e)}")
            return False

    @classmethod
    def get_redis(cls) -> Optional[AsyncRedis]:
        """Get initialized Redis client"""
        return redis_client if cls._initialized.is_set() else None

    @classmethod
    def get_mongodb(cls) -> Optional[AsyncIOMotorClient]:
        """Get initialized MongoDB client"""
        return mongodb_client if cls._initialized.is_set() else None

    @classmethod
    async def cleanup(cls) -> None:
        """Cleanup database connections"""
        try:
            if cls._instance.mongodb:
                cls._instance.mongodb.close()
            if cls._instance.redis:
                await cls._instance.redis.close()
            cls._initialized.clear()
            
            # Clear global variables
            global mongodb_client, redis_client, consultations_collection, translations_cache
            mongodb_client = None
            redis_client = None
            consultations_collection = None
            translations_cache = None
            
            logger.info("Database connections cleaned up successfully")
            
        except Exception as e:
            logger.error(f"Cleanup error: {str(e)}")

# Initialize database configuration
db_config = DatabaseConfig()

async def initialize_db() -> None:
    """Initialize database for backward compatibility"""
    await db_config.initialize()