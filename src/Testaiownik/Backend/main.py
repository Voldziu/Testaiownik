# src/Testaiownik/Backend/main.py
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
from datetime import datetime
import uuid

from .middleware.session import SessionMiddleware
from .api import quiz, documents, topics, collections
from .database.models import init_db
from utils import logger

app = FastAPI(
    title="TESTAIOWNIK API",
    description="AI-powered learning assistant for quiz generation from documents",
    version="1.0.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Session middleware
app.add_middleware(SessionMiddleware)

# Include routers
app.include_router(quiz.router, prefix="/api", tags=["Quiz Management"])
app.include_router(documents.router, prefix="/api", tags=["Documents"])
app.include_router(topics.router, prefix="/api", tags=["Topics"])
app.include_router(collections.router, prefix="/api", tags=["Collections"])


@app.on_event("startup")
async def startup_event():
    """Initialize database and services on startup"""
    logger.info("Starting TESTAIOWNIK FastAPI backend...")
    init_db()
    logger.info("Database initialized")


@app.get("/api/health")
async def health_check():
    """System health check and status"""
    try:
        # Test connections
        from RAG.qdrant_manager import QdrantManager
        from AzureModels.models import get_llm, get_embedding_model

        services_status = {}
        overall_status = "healthy"

        # Test Qdrant
        try:
            qdrant = QdrantManager()
            # Try a simple operation to verify connection
            test_collection = "health_check_test"
            if qdrant.collection_exists(test_collection):
                qdrant.delete_collection(test_collection)
            services_status["qdrant"] = "connected"
        except Exception as e:
            services_status["qdrant"] = f"error: {str(e)[:50]}"
            overall_status = "degraded"

        # Test Azure OpenAI LLM
        try:
            llm = get_llm()
            # Could add a simple test call here if needed
            services_status["azure_openai_llm"] = "connected"
        except Exception as e:
            services_status["azure_openai_llm"] = f"error: {str(e)[:50]}"
            overall_status = "degraded"

        # Test Azure OpenAI Embeddings
        try:
            embedding_model = get_embedding_model()
            # Test with a simple embedding
            test_embedding = embedding_model.embed_query("health check")
            if test_embedding and len(test_embedding) > 0:
                services_status["azure_openai_embeddings"] = "connected"
            else:
                services_status["azure_openai_embeddings"] = (
                    "error: empty embedding response"
                )
                overall_status = "degraded"
        except Exception as e:
            services_status["azure_openai_embeddings"] = f"error: {str(e)[:50]}"
            overall_status = "degraded"

        # Test Database
        try:
            from .database.crud import get_system_stats

            stats = get_system_stats()
            services_status["database"] = "connected"
        except Exception as e:
            services_status["database"] = f"error: {str(e)[:50]}"
            overall_status = "degraded"

        response_data = {
            "status": overall_status,
            "timestamp": datetime.now().isoformat(),
            "services": services_status,
            "version": "1.0.0",
        }

        # Return appropriate HTTP status
        if overall_status == "healthy":
            return response_data
        else:
            return JSONResponse(status_code=503, content=response_data)

    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
                "services": {},
            },
        )


@app.get("/api/stats")
async def get_stats(request: Request):
    """System usage statistics"""
    session_id = request.headers.get("X-Session-ID")

    from .database.crud import get_system_stats, get_session_stats

    system_stats = get_system_stats()
    user_stats = get_session_stats(session_id) if session_id else {}

    return {"system_stats": system_stats, "user_stats": user_stats}


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Custom HTTP exception handler"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "http_error",
            "message": exc.detail,
            "status_code": exc.status_code,
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """General exception handler"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "message": "An unexpected error occurred",
        },
    )


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, log_level="info")
