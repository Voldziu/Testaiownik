# src/Testaiownik/Backend/api/documents.py
from fastapi import APIRouter, HTTPException, Request, UploadFile, File
from typing import List
from datetime import datetime

from ..services.document_service import DocumentService
from ..models.requests import IndexDocumentsRequest
from ..models.responses import (
    DocumentUploadResponse,
    DocumentListResponse,
    DocumentStatusResponse,
    DocumentDeleteResponse,
    DocumentIndexResponse,
    SearchResponse,
    SearchResultItem,
    DocumentItem,
)
from ..database.crud import get_quiz, log_activity
from utils import logger

router = APIRouter()
document_service = DocumentService()


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


@router.post("/documents/{quiz_id}/upload", response_model=DocumentUploadResponse)
async def upload_documents(
    quiz_id: str, request: Request, files: List[UploadFile] = File(...)
):
    """Uploads files (PDF/DOCX/TXT/PPTX) to specific quiz"""
    session_id = get_session_id(request)
    validate_quiz_access(quiz_id, session_id)

    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    # Validate file types
    allowed_extensions = {"pdf", "docx", "txt", "pptx"}
    for file in files:
        if not file.filename:
            raise HTTPException(status_code=400, detail="Invalid filename")

        extension = file.filename.split(".")[-1].lower()
        if extension not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {extension}. Allowed: {', '.join(allowed_extensions)}",
            )

    try:
        uploaded_files = await document_service.upload_documents(
            quiz_id, session_id, files
        )

        return DocumentUploadResponse(
            uploaded_files=[DocumentItem(**file_data) for file_data in uploaded_files],
            quiz_id=quiz_id,
        )

    except Exception as e:
        logger.error(f"Failed to upload documents: {e}")
        raise HTTPException(status_code=500, detail="Failed to upload documents")


@router.get("/documents/{quiz_id}/list", response_model=DocumentListResponse)
async def list_documents(quiz_id: str, request: Request):
    """Lists all documents uploaded to specific quiz"""
    session_id = get_session_id(request)
    validate_quiz_access(quiz_id, session_id)

    try:
        documents = document_service.get_quiz_documents(quiz_id)

        return DocumentListResponse(
            documents=[DocumentItem(**doc) for doc in documents],
            quiz_id=quiz_id,
            total_documents=len(documents),
        )

    except Exception as e:
        logger.error(f"Failed to list documents: {e}")
        raise HTTPException(status_code=500, detail="Failed to list documents")


@router.get("/documents/{quiz_id}/status", response_model=DocumentStatusResponse)
async def get_indexing_status(quiz_id: str, request: Request):
    """Checks indexing status for all quiz documents"""
    session_id = get_session_id(request)
    validate_quiz_access(quiz_id, session_id)

    try:
        status_data = document_service.get_indexing_status(quiz_id)
        return DocumentStatusResponse(**status_data)

    except Exception as e:
        logger.error(f"Failed to get indexing status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get indexing status")


@router.delete("/documents/{quiz_id}/{doc_id}", response_model=DocumentDeleteResponse)
async def delete_document(quiz_id: str, doc_id: str, request: Request):
    """Removes specific document from quiz"""
    session_id = get_session_id(request)
    validate_quiz_access(quiz_id, session_id)

    try:
        result = document_service.delete_quiz_document(quiz_id, doc_id, session_id)
        return DocumentDeleteResponse(**result)

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to delete document: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete document")


@router.post("/documents/{quiz_id}/index", response_model=DocumentIndexResponse)
async def index_documents(
    quiz_id: str, request: Request, index_request: IndexDocumentsRequest = None
):
    """Indexes all quiz documents to Qdrant collection"""
    session_id = get_session_id(request)
    validate_quiz_access(quiz_id, session_id)

    # Default values if no request body
    chunk_size = index_request.chunk_size if index_request else 500
    batch_size = index_request.batch_size if index_request else 50

    try:
        result = await document_service.index_documents(
            quiz_id=quiz_id,
            session_id=session_id,
            chunk_size=chunk_size,
            batch_size=batch_size,
        )

        return DocumentIndexResponse(**result)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to index documents: {e}")
        raise HTTPException(status_code=500, detail="Failed to index documents")


# Search endpoint
@router.get("/search/documents", response_model=SearchResponse)
async def search_documents(
    request: Request, q: str, quiz_id: str = None, limit: int = 10
):
    """Searches through indexed documents using vector similarity"""
    session_id = get_session_id(request)

    if not q.strip():
        raise HTTPException(status_code=400, detail="Search query cannot be empty")

    if limit <= 0 or limit > 100:
        raise HTTPException(status_code=400, detail="Limit must be between 1 and 100")

    # Validate quiz access if specific quiz requested
    if quiz_id:
        validate_quiz_access(quiz_id, session_id)

    try:
        result = document_service.search_documents(
            query=q, quiz_id=quiz_id, limit=limit
        )

        return SearchResponse(
            query=result["query"],
            results=[SearchResultItem(**item) for item in result["results"]],
            total_results=result["total_results"],
            search_time_ms=result["search_time_ms"],
        )

    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail="Search failed")


# Document file serving endpoint (if needed)
@router.get("/documents/{quiz_id}/{doc_id}/download")
async def download_document(quiz_id: str, doc_id: str, request: Request):
    """Download a specific document file"""
    session_id = get_session_id(request)
    validate_quiz_access(quiz_id, session_id)

    # Implementation would serve the actual file
    # This is a placeholder
    raise HTTPException(status_code=501, detail="File download not implemented")


# Bulk operations
@router.delete("/documents/{quiz_id}/all")
async def delete_all_documents(quiz_id: str, request: Request):
    """Delete all documents from a quiz"""
    session_id = get_session_id(request)
    validate_quiz_access(quiz_id, session_id)

    try:
        # Get all documents for the quiz
        documents = document_service.get_quiz_documents(quiz_id)
        deleted_count = 0

        # Delete each document
        for doc in documents:
            try:
                document_service.delete_quiz_document(
                    quiz_id, doc["doc_id"], session_id
                )
                deleted_count += 1
            except Exception as e:
                logger.error(f"Failed to delete document {doc['doc_id']}: {e}")

        return {
            "success": True,
            "message": f"Deleted {deleted_count} documents",
            "deleted_count": deleted_count,
            "total_count": len(documents),
        }

    except Exception as e:
        logger.error(f"Failed to delete all documents: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete documents")


@router.post("/documents/{quiz_id}/reindex")
async def reindex_documents(quiz_id: str, request: Request):
    """Force reindexing of all documents"""
    session_id = get_session_id(request)
    validate_quiz_access(quiz_id, session_id)

    try:
        # Clear existing index
        collection_name = f"quiz_{quiz_id}"
        if document_service.qdrant_manager.collection_exists(collection_name):
            document_service.qdrant_manager.delete_collection(collection_name)

        # Reset indexed status for all documents
        documents = document_service.get_quiz_documents(quiz_id)
        for doc in documents:
            from ..database.crud import update_document_indexed

            update_document_indexed(doc["doc_id"], False)

        # Reindex all documents
        result = await document_service.index_documents(quiz_id, session_id)

        return {
            "success": True,
            "message": "Documents reindexed successfully",
            **result,
        }

    except Exception as e:
        logger.error(f"Failed to reindex documents: {e}")
        raise HTTPException(status_code=500, detail="Failed to reindex documents")
