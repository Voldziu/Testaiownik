from fastapi import APIRouter
from . import quiz, documents, topics, collections

# Create main API router
api_router = APIRouter()

# Include all route modules
api_router.include_router(quiz.router, prefix="/quiz", tags=["Quiz Management"])
api_router.include_router(documents.router, prefix="/documents", tags=["Documents"])
api_router.include_router(topics.router, prefix="/topics", tags=["Topics"])
api_router.include_router(
    collections.router, prefix="/collections", tags=["Collections"]
)

__all__ = ["api_router", "quiz", "documents", "topics", "collections"]
