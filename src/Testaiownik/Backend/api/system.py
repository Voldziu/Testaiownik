# src/Backend/api/system.py
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session
from datetime import datetime

from ..database.sql_database_connector import get_db
from ..database.crud import (
    get_system_stats,
    get_user_stats,
    get_user,
    get_quizzes_by_user,
    log_activity,
    get_quiz,
)

router = APIRouter()


def get_user_id(request: Request) -> str:
    """Extract user ID from request"""
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID required")
    return user_id


def validate_quiz_access(quiz_id: str, user_id: str, db: Session = Depends(get_db)):
    """Validate that quiz belongs to user"""
    quiz = get_quiz(db, quiz_id)
    db.refresh(quiz)
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    if quiz.user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return quiz


@router.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "TESTAIOWNIK API",
        "version": "1.0.0",
        "status": "running",
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """System health check"""
    try:
        services = {}
        overall_status = "healthy"

        # Check Qdrant
        try:
            from RAG.qdrant_manager import QdrantManager

            qdrant_manager = QdrantManager()
            qdrant_manager.collection_exists("test_collection")
            services["qdrant"] = "connected"
        except Exception:
            services["qdrant"] = "disconnected"
            overall_status = "degraded"

        # Check Azure OpenAI
        try:
            from AzureModels import get_llm

            llm = get_llm()
            services["azure_openai"] = "connected"
        except Exception:
            services["azure_openai"] = "disconnected"
            overall_status = "degraded"

        # Check Database
        try:
            db.execute(text("SELECT 1"))
            services["database"] = "connected"
        except Exception:
            services["database"] = "disconnected"
            overall_status = "unhealthy"

        response_data = {
            "status": overall_status,
            "timestamp": datetime.now().isoformat(),
            "services": services,
            "version": "1.0.0",
        }

        status_code = 200 if overall_status == "healthy" else 503
        return JSONResponse(status_code=status_code, content=response_data)

    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
                "services": {},
            },
        )


@router.get("/stats")
async def get_stats(request: Request, db: Session = Depends(get_db)):
    """System usage statistics"""
    user_id = get_user_id(request)

    system_stats = get_system_stats(db)
    user_stats = get_user_stats(db, user_id)

    return {"system_stats": system_stats, "user_stats": user_stats}


@router.post("/backup/user")
async def backup_user_data(request: Request, db: Session = Depends(get_db)):
    """Creates backup of user data"""
    user_id = get_user_id(request)

    try:
        user = get_user(db, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        quizzes = get_quizzes_by_user(db, user_id)
        total_quizzes = len(quizzes)
        total_documents = sum(len(quiz.documents) for quiz in quizzes)
        estimated_size = (total_quizzes * 1000) + (total_documents * 50000)

        backup_id = f"backup_{user_id}_{int(datetime.now().timestamp())}"

        log_activity(
            db,
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
        raise HTTPException(status_code=500, detail="Failed to create backup")
