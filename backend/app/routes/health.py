# backend/app/routes/health.py
from fastapi import APIRouter, HTTPException
from app.config.database import redis_client, mongodb_client
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/health")
async def health_check():
    """Check health status of all services"""
    status = {
        "status": "healthy",
        "services": {
            "redis": {"status": "unknown"},
            "mongodb": {"status": "unknown"}
        }
    }
    
    try:
        # Check Redis
        if redis_client:
            try:
                await redis_client.ping()
                status["services"]["redis"] = {
                    "status": "healthy",
                    "details": "Connection successful"
                }
            except Exception as e:
                status["services"]["redis"] = {
                    "status": "unhealthy",
                    "error": str(e)
                }
                logger.error(f"Redis health check failed: {str(e)}")
                status["status"] = "degraded"
        else:
            status["services"]["redis"] = {
                "status": "unhealthy",
                "error": "Redis client not initialized"
            }
            status["status"] = "degraded"

        # Check MongoDB
        try:
            await mongodb_client.admin.command('ping')
            status["services"]["mongodb"] = {
                "status": "healthy",
                "details": "Connection successful"
            }
        except Exception as e:
            status["services"]["mongodb"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            status["status"] = "degraded"
            logger.error(f"MongoDB health check failed: {str(e)}")

        return status
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        status["status"] = "unhealthy"
        return status