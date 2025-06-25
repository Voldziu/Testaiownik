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
    BaseResponse,
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
    user_id = get_user_id(request)
    validate_quiz_access(quiz_id, user_id)

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
        )

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
        for doc in documents:
            doc_items.append(
                DocumentItem(
                    doc_id=doc.doc_id,
                    filename=doc.filename,
                    size_bytes=doc.size_bytes,
                    type=doc.file_type,
                    uploaded_at=doc.uploaded_at,
                    indexed=doc.indexed,
                )
            )

        return DocumentListResponse(
            documents=doc_items,
            quiz_id=quiz_id,
            total_documents=len(doc_items),
        )

    except Exception as e:
        logger.error(f"Failed to list documents: {e}")
        raise HTTPException(status_code=500, detail="Failed to list documents")


@router.get("/documents/{quiz_id}/status", response_model=DocumentStatusResponse)
async def get_indexing_status(quiz_id: str, request: Request):
    """Checks indexing status for all quiz documents"""
    user_id = get_user_id(request)
    validate_quiz_access(quiz_id, user_id)

    try:
        status_info = document_service.get_indexing_status(quiz_id)
        return DocumentStatusResponse(**status_info)

    except Exception as e:
        logger.error(f"Failed to get indexing status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get indexing status")


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
async def index_documents(
    quiz_id: str,
    request: Request,
    index_request: IndexDocumentsRequest = IndexDocumentsRequest(),
):
    """Indexes all quiz documents to Qdrant collection"""
    user_id = get_user_id(request)
    quiz = validate_quiz_access(quiz_id, user_id)

    try:
        indexing_result = await document_service.index_quiz_documents(quiz_id)

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


# Search endpoints
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

        # Reset quiz status if all documents deleted
        if deleted_count > 0:
            from ..database.crud import update_quiz_status

            update_quiz_status(quiz_id, "created")

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
            "quiz_status_reset": deleted_count > 0,
        }

    except Exception as e:
        logger.error(f"Failed to delete all documents: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete documents")


# Document information endpoints
@router.get("/documents/{quiz_id}/{doc_id}/info")
async def get_document_info(quiz_id: str, doc_id: str, request: Request):
    """Get detailed information about a specific document"""
    user_id = get_user_id(request)
    validate_quiz_access(quiz_id, user_id)

    try:
        document_info = document_service.get_document_status(doc_id)

        if not document_info:
            raise HTTPException(status_code=404, detail="Document not found")

        return document_info

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get document info: {e}")
        raise HTTPException(status_code=500, detail="Failed to get document info")


@router.get("/documents/{quiz_id}/stats")
async def get_document_stats(quiz_id: str, request: Request):
    """Get aggregated statistics about quiz documents"""
    user_id = get_user_id(request)
    validate_quiz_access(quiz_id, user_id)

    try:
        documents = document_service.get_quiz_documents(quiz_id)

        if not documents:
            return {
                "total_documents": 0,
                "total_size_bytes": 0,
                "indexed_documents": 0,
                "file_types": {},
                "indexing_progress": 0.0,
            }

        # Calculate statistics
        total_documents = len(documents)
        indexed_documents = sum(1 for doc in documents if doc.indexed)
        total_size = sum(doc.size_bytes for doc in documents)

        # Count file types
        file_types = {}
        for doc in documents:
            file_type = doc.file_type
            file_types[file_type] = file_types.get(file_type, 0) + 1

        indexing_progress = (
            (indexed_documents / total_documents * 100) if total_documents > 0 else 0
        )

        return {
            "total_documents": total_documents,
            "total_size_bytes": total_size,
            "indexed_documents": indexed_documents,
            "file_types": file_types,
            "indexing_progress": round(indexing_progress, 1),
            "average_size_bytes": (
                total_size // total_documents if total_documents > 0 else 0
            ),
        }

    except Exception as e:
        logger.error(f"Failed to get document stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get document stats")
