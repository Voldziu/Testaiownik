from fastapi import APIRouter
from . import quiz, documents, topics, collections, system

# Create main API router
api_router = APIRouter()

# Include system routes at root level
api_router.include_router(system.router, tags=["System"])

# Include feature routes with prefixes
api_router.include_router(quiz.router, prefix="/quiz", tags=["Quiz Management"])
api_router.include_router(documents.router, prefix="/documents", tags=["Documents"])
api_router.include_router(topics.router, prefix="/topics", tags=["Topics"])
api_router.include_router(
    collections.router, prefix="/collections", tags=["Collections"]
)

__all__ = ["api_router", "quiz", "documents", "topics", "collections", "system"]
