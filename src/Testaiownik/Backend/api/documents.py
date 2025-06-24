# src/Testaiownik/Backend/api/documents.py
from fastapi import APIRouter, HTTPException, Request, UploadFile, File
from typing import List, Optional
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
    user_id = get_user_id(request)  # ✅ Fixed
    validate_quiz_access(quiz_id, user_id)  # ✅ Fixed

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
                detail=f"Unsupported file type: {extension}. Supported: {', '.join(allowed_extensions)}",
            )

    try:
        upload_results = await document_service.upload_documents(
            quiz_id, user_id, files
        )  # ✅ Fixed

        # Log the upload activity
        log_activity(
            user_id,
            "documents_uploaded",
            {
                "quiz_id": quiz_id,
                "file_count": len(files),
                "total_size": sum(result["size_bytes"] for result in upload_results),
            },
        )

        return DocumentUploadResponse(
            uploaded_files=[DocumentItem(**result) for result in upload_results],
            quiz_id=quiz_id,
        )

    except Exception as e:
        logger.error(f"Failed to upload documents: {e}")
        raise HTTPException(status_code=500, detail="Document upload failed")


@router.get("/documents/{quiz_id}/list", response_model=DocumentListResponse)
async def list_documents(quiz_id: str, request: Request):
    """Lists all documents uploaded to a quiz"""
    user_id = get_user_id(request)
    validate_quiz_access(quiz_id, user_id)

    try:
        documents = document_service.get_quiz_documents(quiz_id)

        doc_items = []
        total_size = 0

        for doc in documents:
            doc_items.append(
                DocumentItem(
                    doc_id=doc.doc_id,
                    filename=doc.filename,
                    content_type=doc.content_type,
                    size_bytes=doc.size_bytes,
                    upload_date=doc.created_at,
                    status="indexed" if doc.indexed else "processing",
                )
            )
            total_size += doc.size_bytes

        return DocumentListResponse(
            documents=doc_items,
            total_documents=len(doc_items),
            total_size_bytes=total_size,
        )

    except Exception as e:
        logger.error(f"Failed to list documents: {e}")
        raise HTTPException(status_code=500, detail="Failed to list documents")


@router.get(
    "/documents/{quiz_id}/{doc_id}/status", response_model=DocumentStatusResponse
)
async def get_document_status(quiz_id: str, doc_id: str, request: Request):
    """Gets processing status of specific document"""
    user_id = get_user_id(request)
    validate_quiz_access(quiz_id, user_id)

    try:
        status_info = document_service.get_document_status(doc_id)

        if not status_info:
            raise HTTPException(status_code=404, detail="Document not found")

        return DocumentStatusResponse(**status_info)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get document status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get document status")


@router.delete("/documents/{quiz_id}/{doc_id}", response_model=DocumentDeleteResponse)
async def delete_document(quiz_id: str, doc_id: str, request: Request):
    """Removes specific document from quiz"""
    user_id = get_user_id(request)
    validate_quiz_access(quiz_id, user_id)

    try:
        success = document_service.delete_document(doc_id)

        if not success:
            raise HTTPException(status_code=404, detail="Document not found")

        # Log the deletion
        log_activity(
            user_id,
            "document_deleted",
            {"quiz_id": quiz_id, "doc_id": doc_id},
        )

        return DocumentDeleteResponse(
            success=True,
            message="Document removed successfully",
            doc_id=doc_id,
            reindexing_required=True,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete document: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete document")


@router.post("/documents/{quiz_id}/index", response_model=DocumentIndexResponse)
async def index_documents(quiz_id: str, request: Request):
    """Indexes all quiz documents to Qdrant collection"""
    user_id = get_user_id(request)
    quiz = validate_quiz_access(quiz_id, user_id)

    try:
        indexing_result = await document_service.index_quiz_documents(quiz_id)

        # Update quiz with collection name
        if indexing_result.get("collection_name") and not quiz.collection_name:
            from ..database.crud import update_quiz

            update_quiz(quiz_id, collection_name=indexing_result["collection_name"])

        # Log the indexing activity
        log_activity(
            user_id,
            "documents_indexed",
            {
                "quiz_id": quiz_id,
                "collection_name": indexing_result["collection_name"],
                "document_count": indexing_result["indexed_documents"],
                "chunk_count": indexing_result["total_chunks"],
            },
        )

        return DocumentIndexResponse(**indexing_result)

    except Exception as e:
        logger.error(f"Failed to index documents: {e}")
        raise HTTPException(status_code=500, detail="Document indexing failed")


# Search endpoint
@router.get("/search", response_model=SearchResponse)
async def search_documents(
    request: Request,
    q: str,
    quiz_id: Optional[str] = None,
    limit: int = 10,
):
    """Search through indexed documents using vector similarity"""
    user_id = get_user_id(request)

    if not q.strip():
        raise HTTPException(status_code=400, detail="Search query cannot be empty")

    if limit <= 0 or limit > 100:
        raise HTTPException(status_code=400, detail="Limit must be between 1 and 100")

    # Validate quiz access if specific quiz requested
    if quiz_id:
        validate_quiz_access(quiz_id, user_id)

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
    user_id = get_user_id(request)
    validate_quiz_access(quiz_id, user_id)

    # Implementation would serve the actual file
    # This is a placeholder
    raise HTTPException(status_code=501, detail="File download not implemented")


# Bulk operations
@router.delete("/documents/{quiz_id}/all")
async def delete_all_documents(quiz_id: str, request: Request):
    """Delete all documents from a quiz"""
    user_id = get_user_id(request)
    validate_quiz_access(quiz_id, user_id)

    try:
        # Get all documents for the quiz
        documents = document_service.get_quiz_documents(quiz_id)
        deleted_count = 0

        # Delete each document
        for doc in documents:
            success = document_service.delete_document(doc.doc_id)
            if success:
                deleted_count += 1

        # Log bulk deletion
        log_activity(
            user_id,
            "bulk_documents_deleted",
            {"quiz_id": quiz_id, "deleted_count": deleted_count},
        )

        return {
            "success": True,
            "message": f"Deleted {deleted_count} documents",
            "deleted_count": deleted_count,
        }

    except Exception as e:
        logger.error(f"Failed to delete all documents: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete documents")


# Document search within quiz context
@router.get("/documents/{quiz_id}/search", response_model=SearchResponse)
async def search_quiz_documents(
    quiz_id: str,
    request: Request,
    q: str,
    limit: int = 10,
):
    """Search documents within a specific quiz"""
    user_id = get_user_id(request)
    validate_quiz_access(quiz_id, user_id)

    # Delegate to main search with quiz_id constraint
    return await search_documents(request, q=q, quiz_id=quiz_id, limit=limit)
