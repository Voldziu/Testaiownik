from fastapi import APIRouter, HTTPException, Request
from typing import Optional
from datetime import datetime

from ..services.document_service import DocumentService
from ..models.responses import (
    CollectionsResponse,
    CollectionDeleteResponse,
    BaseResponse,
)
from ..database.crud import get_quiz, get_quizzes_by_user, log_activity
from RAG.qdrant_manager import QdrantManager
from utils import logger

router = APIRouter()
document_service = DocumentService()
qdrant_manager = QdrantManager()


def get_user_id(request: Request) -> str:
    """Extract user ID from request"""
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID required")
    return user_id


def validate_quiz_access(quiz_id: str, user_id: str):
    """Validate that quiz belongs to user"""
    quiz = get_quiz(quiz_id)
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    if quiz.user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return quiz


@router.get("/collections", response_model=CollectionsResponse)
async def list_collections(request: Request, user_only: bool = True):
    """Lists all Qdrant collections"""
    user_id = get_user_id(request)

    try:
        collections = []

        if user_only:
            # Get collections for user's quizzes only
            user_quizzes = get_quizzes_by_user(user_id)

            for quiz in user_quizzes:
                if quiz.collection_name:
                    collection_name = quiz.collection_name

                    # Check if collection exists in Qdrant
                    if qdrant_manager.collection_exists(collection_name):
                        try:
                            # Get collection info
                            from RAG.Retrieval import RAGRetriever

                            retriever = RAGRetriever(collection_name, qdrant_manager)
                            vector_count = retriever.get_chunk_count()

                            collections.append(
                                {
                                    "name": collection_name,
                                    "vector_count": vector_count,
                                    "created_at": quiz.created_at,
                                    "quiz_id": quiz.quiz_id,
                                }
                            )
                        except Exception as e:
                            logger.warning(
                                f"Collection {collection_name} referenced but not accessible: {e}"
                            )
        else:
            # Admin endpoint - list all collections
            # Note: This should be protected with admin authentication in production
            all_collections = qdrant_manager.list_collections()

            for collection_name in all_collections:
                try:
                    from RAG.Retrieval import RAGRetriever

                    retriever = RAGRetriever(collection_name, qdrant_manager)
                    vector_count = retriever.get_chunk_count()

                    # Try to find associated quiz
                    quiz = None
                    # Would need to implement get_quiz_by_collection_name or similar
                    # For now, just list collection without quiz info

                    collections.append(
                        {
                            "name": collection_name,
                            "vector_count": vector_count,
                            "created_at": datetime.now(),  # Placeholder
                            "quiz_id": None,
                        }
                    )
                except Exception as e:
                    logger.warning(
                        f"Could not get info for collection {collection_name}: {e}"
                    )

        return CollectionsResponse(
            collections=collections,
            total_collections=len(collections),
        )

    except Exception as e:
        logger.error(f"Failed to list collections: {e}")
        raise HTTPException(status_code=500, detail="Failed to list collections")


@router.delete("/collections/{quiz_id}", response_model=CollectionDeleteResponse)
async def delete_collection(quiz_id: str, request: Request):
    """Deletes Qdrant collection for specific quiz"""
    user_id = get_user_id(request)
    quiz = validate_quiz_access(quiz_id, user_id)

    if not quiz.collection_name:
        raise HTTPException(status_code=404, detail="Quiz has no associated collection")

    try:
        collection_name = quiz.collection_name

        # Get vector count before deletion
        vector_count = 0
        if qdrant_manager.collection_exists(collection_name):
            from RAG.Retrieval import RAGRetriever

            retriever = RAGRetriever(collection_name, qdrant_manager)
            vector_count = retriever.get_chunk_count()

            # Delete the collection
            qdrant_manager.delete_collection(collection_name)

        # Update quiz to remove collection reference
        from ..database.crud import update_quiz_collection

        update_quiz_collection(quiz_id, None)

        # Log activity
        log_activity(
            user_id,
            "collection_deleted",
            {
                "quiz_id": quiz_id,
                "collection_name": collection_name,
                "vectors_deleted": vector_count,
            },
        )

        return CollectionDeleteResponse(
            success=True,
            deleted_collection=collection_name,
            vector_count_deleted=vector_count,
        )

    except Exception as e:
        logger.error(f"Failed to delete collection: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete collection")


@router.post("/collections/{quiz_id}/cleanup", response_model=BaseResponse)
async def cleanup_collection(quiz_id: str, request: Request):
    """Cleanup and optimize quiz collection"""
    user_id = get_user_id(request)
    quiz = validate_quiz_access(quiz_id, user_id)

    if not quiz.collection_name:
        raise HTTPException(status_code=404, detail="Quiz has no associated collection")

    try:
        collection_name = quiz.collection_name

        # Check if collection exists
        if not qdrant_manager.collection_exists(collection_name):
            raise HTTPException(status_code=404, detail="Collection does not exist")

        # Get counts before optimization
        from RAG.Retrieval import RAGRetriever

        retriever = RAGRetriever(collection_name, qdrant_manager)
        vectors_before = retriever.get_chunk_count()

        # Perform cleanup operations
        import time

        start_time = time.time()

        # For now, just report current state
        # In a real implementation, you might:
        # - Remove duplicate vectors
        # - Optimize vector storage
        # - Rebuild indexes

        optimization_time = time.time() - start_time
        vectors_after = vectors_before  # No actual optimization performed

        log_activity(
            user_id,
            "collection_optimized",
            {
                "quiz_id": quiz_id,
                "collection_name": collection_name,
                "vectors_before": vectors_before,
                "vectors_after": vectors_after,
                "optimization_time": optimization_time,
            },
        )

        return BaseResponse(
            success=True,
            collection_name=collection_name,
            vectors_before=vectors_before,
            vectors_after=vectors_after,
            optimization_time_seconds=round(optimization_time, 2),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cleanup collection: {e}")
        raise HTTPException(status_code=500, detail="Failed to cleanup collection")


@router.get("/collections/{quiz_id}/info")
async def get_collection_info(quiz_id: str, request: Request):
    """Get detailed information about a quiz collection"""
    user_id = get_user_id(request)

    # Validate quiz access
    quiz = validate_quiz_access(quiz_id, user_id)

    if not quiz.collection_name:
        raise HTTPException(status_code=404, detail="Quiz has no associated collection")

    try:
        collection_name = quiz.collection_name

        # Check if collection exists
        if not qdrant_manager.collection_exists(collection_name):
            raise HTTPException(status_code=404, detail="Collection does not exist")

        # Get collection statistics
        from RAG.Retrieval import RAGRetriever

        retriever = RAGRetriever(collection_name, qdrant_manager)
        vector_count = retriever.get_chunk_count()

        # Get sample points for analysis
        sample_points = []
        try:
            # Get a few sample vectors to analyze
            points = qdrant_manager.client.scroll(
                collection_name=collection_name, limit=5, with_payload=True
            )

            for point in points[0]:
                sample_points.append(
                    {
                        "id": str(point.id),
                        "payload_keys": (
                            list(point.payload.keys()) if point.payload else []
                        ),
                        "vector_size": (
                            len(point.vector)
                            if hasattr(point, "vector") and point.vector
                            else 0
                        ),
                    }
                )
        except Exception as e:
            logger.warning(f"Could not get sample points: {e}")

        return {
            "collection_name": collection_name,
            "quiz_id": quiz_id,
            "vector_count": vector_count,
            "created_at": quiz.created_at.isoformat(),
            "sample_points": sample_points,
            "status": "healthy" if vector_count > 0 else "empty",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get collection info: {e}")
        raise HTTPException(status_code=500, detail="Failed to get collection info")
