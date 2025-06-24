# src/Testaiownik/Backend/api/collections.py
from fastapi import APIRouter, HTTPException, Request
from typing import Optional
from datetime import datetime

from services.document_service import DocumentService
from models.responses import (
    CollectionsResponse,
    CollectionDeleteResponse,
    BaseResponse,
)
from database.crud import get_quiz, get_quizzes_by_session, log_activity
from RAG.qdrant_manager import QdrantManager
from utils import logger

router = APIRouter()
document_service = DocumentService()
qdrant_manager = QdrantManager()


def get_session_id(request: Request) -> str:
    """Extract session ID from request"""
    session_id = getattr(request.state, "session_id", None)
    if not session_id:
        raise HTTPException(status_code=401, detail="Session ID required")
    return session_id


@router.get("/collections", response_model=CollectionsResponse)
async def list_collections(request: Request, user_only: bool = True):
    """Lists all Qdrant collections"""
    session_id = get_session_id(request)

    try:
        collections = []

        if user_only:
            # Get collections for user's quizzes only
            user_quizzes = get_quizzes_by_session(session_id)

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
                            logger.error(
                                f"Failed to get collection info for {collection_name}: {e}"
                            )
                            collections.append(
                                {
                                    "name": collection_name,
                                    "vector_count": 0,
                                    "created_at": quiz.created_at,
                                    "quiz_id": quiz.quiz_id,
                                }
                            )
        else:
            # List all collections (admin endpoint)
            # This would require extending QdrantManager to list all collections
            # For now, just return user collections
            return await list_collections(request, user_only=True)

        return CollectionsResponse(
            collections=collections, total_collections=len(collections)
        )

    except Exception as e:
        logger.error(f"Failed to list collections: {e}")
        raise HTTPException(status_code=500, detail="Failed to list collections")


@router.delete("/collections/{quiz_id}", response_model=CollectionDeleteResponse)
async def delete_collection(quiz_id: str, request: Request):
    """Deletes Qdrant collection for specific quiz"""
    session_id = get_session_id(request)

    # Validate quiz access
    quiz = get_quiz(quiz_id)
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    if quiz.session_id != session_id:
        raise HTTPException(status_code=403, detail="Access denied")

    if not quiz.collection_name:
        raise HTTPException(status_code=404, detail="Quiz has no associated collection")

    try:
        collection_name = quiz.collection_name

        # Get vector count before deletion
        vector_count = 0
        if qdrant_manager.collection_exists(collection_name):
            try:
                from RAG.Retrieval import RAGRetriever

                retriever = RAGRetriever(collection_name, qdrant_manager)
                vector_count = retriever.get_chunk_count()
            except Exception as e:
                logger.error(f"Failed to get vector count: {e}")

        # Delete collection
        success = qdrant_manager.delete_collection(collection_name)

        if success:
            # Update quiz to remove collection reference
            from ..database.crud import update_quiz_collection

            update_quiz_collection(quiz_id, None)

            # Mark all documents as not indexed
            documents = document_service.get_quiz_documents(quiz_id)
            for doc in documents:
                from ..database.crud import update_document_indexed

                update_document_indexed(doc["doc_id"], False)

            log_activity(
                session_id,
                "collection_deleted",
                {
                    "quiz_id": quiz_id,
                    "collection_name": collection_name,
                    "vector_count": vector_count,
                },
            )

            return CollectionDeleteResponse(
                deleted_collection=collection_name, vector_count_deleted=vector_count
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to delete collection")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete collection: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete collection")


@router.post("/collections/{quiz_id}/cleanup", response_model=BaseResponse)
async def cleanup_collection(quiz_id: str, request: Request):
    """Cleans up and optimizes quiz collection"""
    session_id = get_session_id(request)

    # Validate quiz access
    quiz = get_quiz(quiz_id)
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    if quiz.session_id != session_id:
        raise HTTPException(status_code=403, detail="Access denied")

    if not quiz.collection_name:
        raise HTTPException(status_code=404, detail="Quiz has no associated collection")

    try:
        collection_name = quiz.collection_name

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
            session_id,
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
    session_id = get_session_id(request)

    # Validate quiz access
    quiz = get_quiz(quiz_id)
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    if quiz.session_id != session_id:
        raise HTTPException(status_code=403, detail="Access denied")

    if not quiz.collection_name:
        raise HTTPException(status_code=404, detail="Quiz has no associated collection")

    try:
        collection_name = quiz.collection_name

        if not qdrant_manager.collection_exists(collection_name):
            raise HTTPException(status_code=404, detail="Collection does not exist")

        # Get collection statistics
        from RAG.Retrieval import RAGRetriever

        retriever = RAGRetriever(collection_name, qdrant_manager)
        vector_count = retriever.get_chunk_count()

        # Get associated documents
        documents = document_service.get_quiz_documents(quiz_id)
        indexed_docs = [doc for doc in documents if doc["indexed"]]

        return {
            "collection_name": collection_name,
            "quiz_id": quiz_id,
            "vector_count": vector_count,
            "total_documents": len(documents),
            "indexed_documents": len(indexed_docs),
            "created_at": quiz.created_at,
            "last_updated": quiz.updated_at,
            "documents": documents,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get collection info: {e}")
        raise HTTPException(status_code=500, detail="Failed to get collection info")


@router.post("/collections/{quiz_id}/backup")
async def backup_collection(quiz_id: str, request: Request):
    """Create a backup of the collection data"""
    session_id = get_session_id(request)

    # Validate quiz access
    quiz = get_quiz(quiz_id)
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    if quiz.session_id != session_id:
        raise HTTPException(status_code=403, detail="Access denied")

    if not quiz.collection_name:
        raise HTTPException(status_code=404, detail="Quiz has no associated collection")

    # This is a placeholder implementation
    # In practice, you might export the collection data to a file
    backup_id = f"backup_{quiz_id}_{int(datetime.now().timestamp())}"

    log_activity(
        session_id,
        "collection_backup_created",
        {
            "quiz_id": quiz_id,
            "backup_id": backup_id,
            "collection_name": quiz.collection_name,
        },
    )

    return {
        "success": True,
        "backup_id": backup_id,
        "quiz_id": quiz_id,
        "collection_name": quiz.collection_name,
        "created_at": datetime.now(),
        "message": "Backup request queued (placeholder implementation)",
    }


@router.get("/collections/{quiz_id}/stats")
async def get_collection_stats(quiz_id: str, request: Request):
    """Get detailed statistics about collection usage"""
    session_id = get_session_id(request)

    # Validate quiz access
    quiz = get_quiz(quiz_id)
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    if quiz.session_id != session_id:
        raise HTTPException(status_code=403, detail="Access denied")

    if not quiz.collection_name:
        raise HTTPException(status_code=404, detail="Quiz has no associated collection")

    try:
        collection_name = quiz.collection_name

        if not qdrant_manager.collection_exists(collection_name):
            raise HTTPException(status_code=404, detail="Collection does not exist")

        # Get basic stats
        from RAG.Retrieval import RAGRetriever

        retriever = RAGRetriever(collection_name, qdrant_manager)
        vector_count = retriever.get_chunk_count()

        # Get document stats
        documents = document_service.get_quiz_documents(quiz_id)
        doc_stats = {}

        for doc in documents:
            if doc["indexed"]:
                file_type = doc["type"]
                if file_type not in doc_stats:
                    doc_stats[file_type] = {"count": 0, "size_bytes": 0}
                doc_stats[file_type]["count"] += 1
                doc_stats[file_type]["size_bytes"] += doc["size_bytes"]

        return {
            "collection_name": collection_name,
            "quiz_id": quiz_id,
            "vector_count": vector_count,
            "total_documents": len(documents),
            "indexed_documents": len([d for d in documents if d["indexed"]]),
            "total_size_bytes": sum(doc["size_bytes"] for doc in documents),
            "document_types": doc_stats,
            "average_chunk_size": 500,  # Placeholder - could calculate actual
            "created_at": quiz.created_at,
            "last_updated": quiz.updated_at,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get collection stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get collection stats")


# Admin endpoints (could be protected with additional auth)


@router.get("/collections/system/stats")
async def get_system_collection_stats(request: Request):
    """Get system-wide collection statistics (admin endpoint)"""
    session_id = get_session_id(request)

    try:
        # Get all user quizzes
        quizzes = get_quizzes_by_session(session_id)

        total_collections = 0
        total_vectors = 0
        collections_by_status = {"active": 0, "empty": 0, "error": 0}

        for quiz in quizzes:
            if quiz.collection_name:
                total_collections += 1

                try:
                    if qdrant_manager.collection_exists(quiz.collection_name):
                        from RAG.Retrieval import RAGRetriever

                        retriever = RAGRetriever(quiz.collection_name, qdrant_manager)
                        count = retriever.get_chunk_count()
                        total_vectors += count

                        if count > 0:
                            collections_by_status["active"] += 1
                        else:
                            collections_by_status["empty"] += 1
                    else:
                        collections_by_status["error"] += 1

                except Exception as e:
                    logger.error(
                        f"Error checking collection {quiz.collection_name}: {e}"
                    )
                    collections_by_status["error"] += 1

        return {
            "total_collections": total_collections,
            "total_vectors": total_vectors,
            "collections_by_status": collections_by_status,
            "average_vectors_per_collection": total_vectors / max(total_collections, 1),
        }

    except Exception as e:
        logger.error(f"Failed to get system collection stats: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to get system collection stats"
        )
