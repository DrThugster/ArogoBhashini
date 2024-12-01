# backend/app/utils/translation_cache.py
from typing import Optional, Dict, List, Union
from datetime import datetime, timedelta
from app.config.database import translations_cache, redis_client, DatabaseConfig
from app.config.language_metadata import LanguageMetadata
import hashlib
import json
import logging
import asyncio
from pydantic import BaseModel, Field
from collections import defaultdict
import os

logger = logging.getLogger(__name__)

class CachedTranslation(BaseModel):
    """Model for cached translations"""
    source_text: str = Field(..., description="Original text")
    translated_text: str = Field(..., description="Translated text")
    source_language: str = Field(..., description="Source language code")
    target_language: str = Field(..., description="Target language code")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Translation confidence")
    medical_terms: List[str] = Field(default_factory=list, description="Medical terms in text")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    access_count: int = Field(default=0, description="Number of times accessed")
    metadata: Dict = Field(default_factory=dict)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class CacheStats(BaseModel):
    """Model for cache statistics"""
    hits: int = 0
    misses: int = 0
    avg_response_time: float = 0.0
    total_entries: int = 0
    memory_usage: int = 0

class TranslationCache:
    def __init__(self):
        # Cache configuration
        self.redis_client = None
        self._initialized = False
        self._initialization_lock = asyncio.Lock()
        self.cache_duration = timedelta(days=7)
        self.redis_prefix = "translation:"
        self.min_confidence_threshold = 0.8
        self.max_text_length = 1000
        
        # Performance settings
        self.batch_size = 50
        self.max_retries = 3
        self.retry_delay = 0.1
        self.pool_semaphore = asyncio.Semaphore(10)
        
        # Statistics
        self.stats = defaultdict(int)
        self.last_cleanup = datetime.utcnow()
        self.cleanup_interval = timedelta(hours=24)

        # Database settings
        self.mongodb = None
        self.translations_collection = None
        self.db_name = os.getenv("DATABASE_NAME", "arogo_bhasini2")

    async def initialize(self):
        """Initialize Redis and MongoDB connections"""
        async with self._initialization_lock:
            if self._initialized:
                return

            try:
                # Initialize database config
                db_config = DatabaseConfig()
                await db_config.initialize()
                await db_config._initialized.wait()
                
                # Get Redis client
                self.redis_client = await db_config.get_redis()
                if not self.redis_client:
                    raise RuntimeError("Redis client initialization failed")
                
                # Get MongoDB client and collection
                self.mongodb = db_config.get_mongodb()
                if not self.mongodb:
                    raise RuntimeError("MongoDB client initialization failed")
                
                # Initialize MongoDB collection
                db = self.mongodb[self.db_name]
                self.translations_collection = db.translations_cache
                
                # Test connections
                await self.redis_client.ping()
                test_doc = await self.translations_collection.find_one()
                
                # Cache settings
                self.cache_ttl = 3600  # 1 hour
                self.max_cache_size = 10000
                self.min_confidence = 0.8
                
                self._initialized = True
                logger.info("TranslationCache initialized successfully")
                
            except Exception as e:
                self._initialized = False
                logger.error(f"TranslationCache initialization failed: {str(e)}")
                await self._cleanup_failed_init()
                raise RuntimeError(f"Cache initialization failed: {str(e)}")

    async def _cleanup_failed_init(self):
        """Cleanup resources after failed initialization"""
        try:
            if self.redis_client:
                await self.redis_client.close()
            self.redis_client = None
            self.mongodb = None
            self.translations_collection = None
            logger.info("Cleaned up resources after failed initialization")
        except Exception as e:
            logger.error(f"Cleanup error: {str(e)}")



    async def _ensure_initialized(self):
        """Ensure Redis connection is initialized"""
        if not self._initialized:
            await self.initialize()
        if not self.redis_client:
            raise RuntimeError("Redis client not available")


    async def get_cached_translation(
        self,
        text: str,
        source_lang: str,
        target_lang: str
    ) -> Optional[CachedTranslation]:
        """Get translation from cache with optimized lookup"""

        await self._ensure_initialized()

        try:
            if len(text) > self.max_text_length:
                return None

            start_time = datetime.utcnow()
            cache_key = self._generate_cache_key(text, source_lang, target_lang)

            # Try Redis first
            async with self.pool_semaphore:
                cached_data = await self.redis_client.get(cache_key)

            if cached_data:
                self.stats["hits"] += 1
                cached = json.loads(cached_data)
                translation = CachedTranslation(**cached)
                await self._update_access_stats(translation, cache_key)
                return translation

            # Try MongoDB if not in Redis
            mongo_result = await self._get_from_mongodb(text, source_lang, target_lang)
            if mongo_result:
                self.stats["hits"] += 1
                translation = CachedTranslation(**mongo_result)
                await self._cache_in_redis(cache_key, translation)
                return translation

            self.stats["misses"] += 1
            self._update_response_time(start_time)
            return None

        except Exception as e:
            logger.error(f"Cache retrieval error: {str(e)}")
            return None

    async def cache_translation(
        self,
        text: str,
        translated_text: str,
        source_lang: str,
        target_lang: str,
        confidence: float,
        medical_terms: Optional[List[str]] = None,
        metadata: Optional[Dict] = None
    ) -> bool:
        """Cache translation with validation and optimization"""
        try:
            if not self._should_cache(text, confidence):
                return False

            cache_entry = CachedTranslation(
                source_text=text,
                translated_text=translated_text,
                source_language=source_lang,
                target_language=target_lang,
                confidence=confidence,
                medical_terms=medical_terms or [],
                metadata=metadata or {}
            )

            # Cache in both Redis and MongoDB
            async with self.pool_semaphore:
                success = await self._store_translation(cache_entry)

            # Periodic cleanup check
            await self._check_cleanup()

            return success

        except Exception as e:
            logger.error(f"Cache storage error: {str(e)}")
            return False

    async def cache_translations_batch(
        self,
        translations: List[Dict]
    ) -> Dict[str, bool]:
        """Batch process multiple translations"""
        results = {}
        async with self.pool_semaphore:
            async with self.redis_client.pipeline() as pipe:
                for trans in translations:
                    try:
                        cache_entry = CachedTranslation(**trans)
                        cache_key = self._generate_cache_key(
                            cache_entry.source_text,
                            cache_entry.source_language,
                            cache_entry.target_language
                        )
                        # Add to pipeline
                        await pipe.setex(
                            cache_key,
                            int(self.cache_duration.total_seconds()),
                            cache_entry.json()
                        )
                        results[cache_key] = True
                    except Exception as e:
                        logger.error(f"Error caching translation: {str(e)}")
                        results[cache_key] = False
                
                # Execute pipeline
                await pipe.execute()

        return results

    async def invalidate_cache(
        self,
        source_lang: Optional[str] = None,
        target_lang: Optional[str] = None
    ):
        """Invalidate cache entries with pattern matching"""
        try:
            # Build MongoDB query
            query = {
                "created_at": {"$lt": datetime.utcnow() - self.cache_duration}
            }
            if source_lang:
                query["source_language"] = source_lang
            if target_lang:
                query["target_language"] = target_lang

            # Remove from MongoDB
            result = await translations_cache.delete_many(query)
            logger.info(f"Removed {result.deleted_count} expired translations from MongoDB")

            # Clear Redis patterns
            pattern = self._get_redis_pattern(source_lang, target_lang)
            async for key in self.redis_client.scan_iter(pattern):
                await self.redis_client.delete(key)

        except Exception as e:
            logger.error(f"Cache invalidation error: {str(e)}")

    async def get_cache_stats(self) -> Dict:
        """Get comprehensive cache statistics"""
        try:
            stats = CacheStats(
                hits=self.stats["hits"],
                misses=self.stats["misses"],
                avg_response_time=self.stats["avg_response_time"],
                total_entries=await translations_cache.count_documents({}),
                memory_usage=await self._get_memory_usage()
            )

            language_stats = {}
            for lang in LanguageMetadata.get_supported_languages():
                language_stats[lang] = await self._get_language_stats(lang)

            return {
                "general": stats.dict(),
                "languages": language_stats,
                "pool_utilization": await self._get_pool_utilization()
            }

        except Exception as e:
            logger.error(f"Error getting cache stats: {str(e)}")
            return {}

    async def optimize_cache(self):
        """Optimize cache storage and performance"""
        try:
            # Remove expired entries
            await self.invalidate_cache()

            # Get current stats
            stats = await self.get_cache_stats()

            # Identify and handle frequent translations
            frequent_translations = await self._get_frequent_translations()
            await self._optimize_frequent_translations(frequent_translations)

            return stats

        except Exception as e:
            logger.error(f"Cache optimization error: {str(e)}")

    def _generate_cache_key(self, text: str, source_lang: str, target_lang: str) -> str:
        """Generate unique and consistent cache key"""
        text_hash = hashlib.md5(text.encode()).hexdigest()
        return f"{self.redis_prefix}{source_lang}:{target_lang}:{text_hash}"

    def _should_cache(self, text: str, confidence: float) -> bool:
        """Determine if translation should be cached"""
        return (
            len(text) <= self.max_text_length and 
            confidence >= self.min_confidence_threshold
        )

    async def _store_translation(self, translation: CachedTranslation) -> bool:
        """Store translation in both Redis and MongoDB"""
        try:
            await self._ensure_initialized()  

            cache_key = self._generate_cache_key(
                translation.source_text,
                translation.source_language,
                translation.target_language
            )

            # Store in Redis
            await self.redis_client.setex(
                cache_key,
                int(self.cache_duration.total_seconds()),
                translation.json()
            )

            # Store in MongoDB
            await self.translations_collection.update_one(
                {
                    "source_text": translation.source_text,
                    "source_language": translation.source_language,
                    "target_language": translation.target_language
                },
                {"$set": translation.dict()},
                upsert=True
            )

            return True

        except Exception as e:
            logger.error(f"Error storing translation: {str(e)}")
            return False

    async def _update_access_stats(
        self,
        translation: CachedTranslation,
        cache_key: str
    ):
        """Update access statistics"""
        try:
            translation.access_count += 1
            await self.translations_collection.update_one(
                {
                    "source_text": translation.source_text,
                    "source_language": translation.source_language,
                    "target_language": translation.target_language
                },
                {"$inc": {"access_count": 1}}
            )
        except Exception as e:
            logger.error(f"Error updating access stats: {str(e)}")

    async def _get_from_mongodb(
        self,
        text: str,
        source_lang: str,
        target_lang: str
    ) -> Optional[Dict]:
        """Get translation from MongoDB with retry logic"""
        for retry in range(self.max_retries):
            try:
                return await translations_cache.find_one({
                    "source_text": text,
                    "source_language": source_lang,
                    "target_language": target_lang,
                    "created_at": {"$gte": datetime.utcnow() - self.cache_duration}
                })
            except Exception as e:
                if retry == self.max_retries - 1:
                    raise
                await asyncio.sleep(self.retry_delay * (retry + 1))

    async def _check_cleanup(self):
        """Check if cleanup is needed"""
        if datetime.utcnow() - self.last_cleanup > self.cleanup_interval:
            asyncio.create_task(self.optimize_cache())
            self.last_cleanup = datetime.utcnow()

    def _update_response_time(self, start_time: datetime):
        """Update average response time"""
        duration = (datetime.utcnow() - start_time).total_seconds()
        self.stats["avg_response_time"] = (
            (self.stats["avg_response_time"] * (self.stats["hits"] + self.stats["misses"]) + duration) /
            (self.stats["hits"] + self.stats["misses"] + 1)
        )

    async def _get_memory_usage(self) -> int:
        """Get Redis memory usage"""
        try:
            pattern = f"{self.redis_prefix}*"
            memory = 0
            async for key in self.redis_client.scan_iter(pattern):
                memory += await self.redis_client.memory_usage(key) or 0
            return memory
        except Exception as e:
            logger.error(f"Error getting memory usage: {str(e)}")
            return 0

    async def _get_pool_utilization(self) -> Dict:
        """Get connection pool utilization"""
        try:
            return {
                "active_connections": len(self.pool_semaphore._waiters) + self.pool_semaphore._value,
                "available_connections": self.pool_semaphore._value
            }
        except Exception as e:
            logger.error(f"Error getting pool utilization: {str(e)}")
            return {}

    def _get_redis_pattern(
        self,
        source_lang: Optional[str],
        target_lang: Optional[str]
    ) -> str:
        """Get Redis pattern for language pair"""
        if source_lang and target_lang:
            return f"{self.redis_prefix}{source_lang}:{target_lang}:*"
        elif source_lang:
            return f"{self.redis_prefix}{source_lang}:*"
        elif target_lang:
            return f"{self.redis_prefix}*:{target_lang}:*"
        return f"{self.redis_prefix}*"