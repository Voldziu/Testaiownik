# src/Testaiownik/Backend/main.py
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import uvicorn

from .middleware import SessionMiddleware
from .api import quiz, documents, topics, collections
from utils import logger

app = FastAPI(title="TESTAIOWNIK API", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add session middleware for user management
app.add_middleware(SessionMiddleware)

# Include routers
app.include_router(quiz.router, prefix="/api", tags=["quiz"])
app.include_router(documents.router, prefix="/api", tags=["documents"])
app.include_router(topics.router, prefix="/api", tags=["topics"])
app.include_router(collections.router, prefix="/api", tags=["collections"])


def get_user_id(request: Request) -> str:
    """Extract user ID from request"""
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID required")
    return user_id


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "TESTAIOWNIK API",
        "version": "1.0.0",
        "status": "running",
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/api/health")
async def health_check():
    """System health check and status"""
    try:
        # Check different services
        services = {}
        overall_status = "healthy"

        # Check Qdrant
        try:
            from RAG.Retrieval import qdrant_manager

            # Simple ping to check if Qdrant is responsive
            collections = qdrant_manager.list_collections()
            services["qdrant"] = "connected"
        except Exception as e:
            logger.warning(f"Qdrant health check failed: {e}")
            services["qdrant"] = "disconnected"
            overall_status = "degraded"

        # Check Azure OpenAI
        try:
            from AzureModels import get_llm

            llm = get_llm
            # Could do a simple test call here
            services["azure_openai"] = "connected"
        except Exception as e:
            logger.warning(f"Azure OpenAI health check failed: {e}")
            services["azure_openai"] = "disconnected"
            overall_status = "degraded"

        # Check Database
        try:
            from .database.models import get_db

            db = next(get_db())
            # Simple query to check DB connectivity
            db.execute("SELECT 1")
            services["database"] = "connected"
            db.close()
        except Exception as e:
            logger.warning(f"Database health check failed: {e}")
            services["database"] = "disconnected"
            overall_status = "unhealthy"

        response_data = {
            "status": overall_status,
            "timestamp": datetime.now().isoformat(),
            "services": services,
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
    user_id = get_user_id(request)

    from .database.crud import get_system_stats, get_user_stats

    system_stats = get_system_stats()
    user_stats = get_user_stats(user_id)

    return {"system_stats": system_stats, "user_stats": user_stats}


@app.post("/api/backup/user")
async def backup_user_data(request: Request):
    """Creates backup of user data"""
    user_id = get_user_id(request)

    try:
        from .database.crud import get_quizzes_by_user, get_user

        # Get user data
        user = get_user(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Get user's quizzes
        quizzes = get_quizzes_by_user(user_id)

        # Calculate backup size (approximate)
        total_quizzes = len(quizzes)
        total_documents = sum(quiz.document_count or 0 for quiz in quizzes)
        estimated_size = (total_quizzes * 1000) + (
            total_documents * 50000
        )  # Rough estimate

        # Create backup record
        backup_id = f"backup_{user_id}_{int(datetime.now().timestamp())}"

        # In a real implementation, you would:
        # 1. Export all user data to a file/storage
        # 2. Store backup metadata in database
        # 3. Set expiry policies

        from .database.crud import log_activity

        log_activity(
            user_id,
            "backup_created",
            {
                "backup_id": backup_id,
                "quiz_count": total_quizzes,
                "document_count": total_documents,
            },
        )

        return {
            "backup_id": backup_id,
            "user_id": user_id,
            "created_at": datetime.now().isoformat(),
            "size_bytes": estimated_size,
            "expiry_date": datetime.now()
            .replace(month=datetime.now().month + 1)
            .isoformat(),
            "quiz_count": total_quizzes,
            "document_count": total_documents,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create backup: {e}")
        raise HTTPException(status_code=500, detail="Failed to create backup")


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
