# backend/app/main.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.config.database import DatabaseConfig, mongodb_client
from app.config.database import redis_client
from app.routes import (
    consultation,
    summary,
    report,
    speech,
    websocket
)
from app.services.chat_service import ChatService
from contextlib import asynccontextmanager
from datetime import datetime
import logging
import json
import asyncio

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Store client sessions
    app.state.client_sessions = set()
    
    # Startup
    try:
        logger.info("Starting up the application...")
        
        # Initialize database connections
        db_config = DatabaseConfig()
        await db_config.initialize()
        await db_config._initialized.wait()
        logger.info("Database configuration initialized")

        # Get Redis client and verify it's ready
        redis = db_config.get_redis()
        if redis:
            await redis.ping()
            logger.info("Redis connection verified")
        else:
            raise RuntimeError("Redis client not properly initialized")  
        
        # Initialize chat service first (since other services depend on it)
        chat_service = ChatService()
        await chat_service.initialize()
        logger.info("Chat service initialized")
        
        # Initialize WebSocket manager
        await websocket.initialize_manager()
        logger.info("WebSocket manager initialized")
        
    except Exception as e:
        logger.error(f"Startup Error: {str(e)}")
        raise e
    
    yield
    
    # Shutdown
    try:
        logger.info("Shutting down the application...")
        
        # Close all client sessions
        if hasattr(app.state, 'client_sessions'):
            await asyncio.gather(*[
                session.close() 
                for session in app.state.client_sessions
            ], return_exceptions=True)
            logger.info("Client sessions closed")
        
        # Cleanup chat service
        if chat_service:
            await chat_service.cleanup()
            logger.info("Chat service cleaned up")
        
        # Cleanup database connections
        await DatabaseConfig.cleanup()
        logger.info("Database connections closed")
        
        # Clean up WebSocket connections
        await websocket.cleanup_manager()
        logger.info("WebSocket connections cleaned up")
        
    except Exception as e:
        logger.error(f"Shutdown Error: {str(e)}")

app = FastAPI(
    title="Multilingual Telemedicine API",
    description="AI-powered multilingual telemedicine consultation platform",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Language middleware
@app.middleware("http")
async def add_language_headers(request: Request, call_next):
    """Add language handling headers to requests."""
    try:
        response = await call_next(request)
        language = request.headers.get("Accept-Language", "en").split(",")[0]
        response.headers["Content-Language"] = language
        return response
    except Exception as e:
        logger.error(f"Language middleware error: {str(e)}")
        raise

# Router includes
app.include_router(
    consultation.router,
    prefix="/api/consultation",
    tags=["consultation"]
)

app.include_router(
    summary.router,
    prefix="/api/consultation",
    tags=["summary"]
)

app.include_router(
    summary.router,
    prefix="/api/diagnostic",
    tags=["diagnostic"]
)

app.include_router(
    report.router,
    prefix="/api/report",
    tags=["report"]
)

app.include_router(
    speech.router,
    prefix="/api/speech",
    tags=["speech"]
)

app.include_router(websocket.router)

@app.get("/health")
async def health_check():
    """Check the health status of the application."""
    try:
        health_status = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "services": {
                "mongodb": "disconnected",
                "redis": "disconnected"
            },
            "language_services": {
                "bhashini": "unknown",
                "translation_cache": "unknown"
            }
        }

        # Check MongoDB
        try:
            await mongodb_client.admin.command('ping')
            health_status["services"]["mongodb"] = "connected"
        except Exception as e:
            logger.error(f"MongoDB health check failed: {str(e)}")
            health_status["services"]["mongodb"] = f"error: {str(e)}"

        # Check Redis
        try:
            await redis_client.ping()
            health_status["services"]["redis"] = "connected"
        except Exception as e:
            logger.error(f"Redis health check failed: {str(e)}")
            health_status["services"]["redis"] = f"error: {str(e)}"

        # Check Bhashini Service
        try:
            bhashini_status = await speech.check_bhashini_status()
            health_status["language_services"]["bhashini"] = bhashini_status
        except Exception as e:
            logger.error(f"Bhashini service check failed: {str(e)}")
            health_status["language_services"]["bhashini"] = f"error: {str(e)}"

        # Overall status check
        all_healthy = all(
            status == "connected" for status in health_status["services"].values()
        ) and all(
            status not in ["error", "unknown"] 
            for status in health_status["language_services"].values()
        )

        return JSONResponse(
            status_code=200 if all_healthy else 503,
            content=health_status
        )

    except Exception as e:
        logger.error(f"Health check error: {str(e)}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for all unhandled exceptions."""
    logger.error(f"Unhandled exception: {str(exc)}")
    error_response = {
        "detail": str(exc),
        "status": "error",
        "timestamp": datetime.utcnow().isoformat()
    }
    
    # Add language-specific error messages if available
    if hasattr(request.state, "language"):
        try:
            speech_processor = speech.speech_processor
            translated_error = await speech_processor.bhashini_service.translate_text(
                text=str(exc),
                source_language="en",
                target_language=request.state.language
            )
            error_response["translated_detail"] = translated_error["text"]
        except Exception as translation_error:
            logger.error(f"Error translation failed: {str(translation_error)}")
            
    return JSONResponse(
        status_code=500,
        content=error_response
    )



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )