# src/Testaiownik/Backend/api/collections.py
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
            # List all collections (admin feature)
            try:
                # Get all collections from Qdrant
                all_collections = qdrant_manager.client.get_collections()

                for collection_info in all_collections.collections:
                    collection_name = collection_info.name

                    try:
                        from RAG.Retrieval import RAGRetriever

                        retriever = RAGRetriever(collection_name, qdrant_manager)
                        vector_count = retriever.get_chunk_count()

                        # Try to find associated quiz
                        quiz_id = None
                        if collection_name.startswith("quiz_"):
                            potential_quiz_id = collection_name.replace("quiz_", "")
                            quiz = get_quiz(potential_quiz_id)
                            if quiz:
                                quiz_id = quiz.quiz_id

                        collections.append(
                            {
                                "name": collection_name,
                                "vector_count": vector_count,
                                "created_at": datetime.now(),  # Placeholder
                                "quiz_id": quiz_id,
                            }
                        )
                    except Exception as e:
                        logger.warning(
                            f"Could not get info for collection {collection_name}: {e}"
                        )
            except Exception as e:
                logger.error(f"Failed to list all collections: {e}")

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
        from ..database.crud import update_quiz_collection, update_quiz_status

        update_quiz_collection(quiz_id, None)
        update_quiz_status(
            quiz_id, "documents_uploaded"
        )  # Reset to pre-indexing status

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
        # - Compact collection

        optimization_time = time.time() - start_time
        vectors_after = vectors_before  # No actual optimization performed yet

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
            scroll_result = qdrant_manager.client.scroll(
                collection_name=collection_name, limit=5, with_payload=True
            )
            points = scroll_result[0]

            for point in points:
                sample_points.append(
                    {
                        "id": str(point.id),
                        "payload_keys": (
                            list(point.payload.keys()) if point.payload else []
                        ),
                        "text_preview": (
                            point.payload.get("text", "")[:100] + "..."
                            if point.payload and point.payload.get("text")
                            else ""
                        ),
                        "source": (
                            point.payload.get("source", "") if point.payload else ""
                        ),
                    }
                )
        except Exception as e:
            logger.warning(f"Could not get sample points: {e}")

        # Get collection configuration
        try:
            collection_info = qdrant_manager.client.get_collection(collection_name)
            config_info = {
                "vector_size": collection_info.config.params.vectors.size,
                "distance_metric": collection_info.config.params.vectors.distance.name,
            }
        except Exception as e:
            logger.warning(f"Could not get collection config: {e}")
            config_info = {}

        return {
            "collection_name": collection_name,
            "quiz_id": quiz_id,
            "vector_count": vector_count,
            "created_at": quiz.created_at.isoformat(),
            "config": config_info,
            "sample_points": sample_points,
            "status": "healthy" if vector_count > 0 else "empty",
            "quiz_status": quiz.status,
            "documents_count": len(quiz.documents) if quiz.documents else 0,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get collection info: {e}")
        raise HTTPException(status_code=500, detail="Failed to get collection info")


@router.post("/collections/{quiz_id}/reindex")
async def reindex_collection(quiz_id: str, request: Request):
    """Rebuild collection from quiz documents"""
    user_id = get_user_id(request)
    quiz = validate_quiz_access(quiz_id, user_id)

    try:
        # Delete existing collection if it exists
        if quiz.collection_name and qdrant_manager.collection_exists(
            quiz.collection_name
        ):
            qdrant_manager.delete_collection(quiz.collection_name)

        # Reset quiz status
        from ..database.crud import update_quiz_collection, update_quiz_status

        update_quiz_collection(quiz_id, None)
        update_quiz_status(quiz_id, "documents_uploaded")

        # Mark all documents as not indexed
        from ..database.crud import get_documents_by_quiz, update_document_indexed

        documents = get_documents_by_quiz(quiz_id)
        for doc in documents:
            update_document_indexed(doc.doc_id, False)

        # Trigger reindexing
        indexing_result = await document_service.index_quiz_documents(quiz_id)

        log_activity(
            user_id,
            "collection_reindexed",
            {
                "quiz_id": quiz_id,
                "new_collection": indexing_result["collection_name"],
                "chunks_indexed": indexing_result["total_chunks"],
            },
        )

        return {
            "success": True,
            "message": "Collection reindexed successfully",
            "new_collection_name": indexing_result["collection_name"],
            "total_chunks": indexing_result["total_chunks"],
            "indexing_time_seconds": indexing_result["indexing_time_seconds"],
        }

    except Exception as e:
        logger.error(f"Failed to reindex collection: {e}")
        raise HTTPException(status_code=500, detail="Failed to reindex collection")


@router.get("/collections/stats")
async def get_collections_stats(request: Request):
    """Get system-wide collection statistics"""
    user_id = get_user_id(request)

    try:
        # Get user's collections
        user_collections = []
        user_quizzes = get_quizzes_by_user(user_id)

        total_vectors = 0
        total_collections = 0

        for quiz in user_quizzes:
            if quiz.collection_name and qdrant_manager.collection_exists(
                quiz.collection_name
            ):
                try:
                    from RAG.Retrieval import RAGRetriever

                    retriever = RAGRetriever(quiz.collection_name, qdrant_manager)
                    vector_count = retriever.get_chunk_count()

                    total_vectors += vector_count
                    total_collections += 1

                    user_collections.append(
                        {
                            "quiz_id": quiz.quiz_id,
                            "collection_name": quiz.collection_name,
                            "vector_count": vector_count,
                            "quiz_status": quiz.status,
                        }
                    )
                except Exception as e:
                    logger.warning(
                        f"Could not get stats for collection {quiz.collection_name}: {e}"
                    )

        return {
            "user_collections": user_collections,
            "total_user_collections": total_collections,
            "total_user_vectors": total_vectors,
            "average_vectors_per_collection": (
                total_vectors / total_collections if total_collections > 0 else 0
            ),
        }

    except Exception as e:
        logger.error(f"Failed to get collection stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get collection stats")
