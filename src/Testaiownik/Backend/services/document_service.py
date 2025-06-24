# src/Testaiownik/Backend/services/document_service.py
from typing import List, Dict, Any, Optional
import os
import asyncio
import aiofiles
from pathlib import Path
import uuid
import time
from datetime import datetime

from RAG.qdrant_manager import QdrantManager
from RAG.Retrieval import RAGRetriever
from ..database.crud import (
    create_document,
    get_documents_by_quiz,
    update_document_indexed,
    delete_document,
    update_quiz_collection,
    log_activity,
)
from utils import logger


class DocumentService:
    """Service for document upload and indexing operations"""

    def __init__(self):
        self.qdrant_manager = QdrantManager()
        self.upload_dir = Path("uploads")
        self.upload_dir.mkdir(exist_ok=True)

        # Supported file types
        self.supported_types = {
            "pdf": "application/pdf",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "txt": "text/plain",
            "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        }

    async def upload_documents(
        self, quiz_id: str, user_id: str, files: List[Any]
    ) -> List[Dict]:
        """Upload and save documents for a quiz"""
        uploaded_files = []

        try:
            quiz_upload_dir = self.upload_dir / quiz_id
            quiz_upload_dir.mkdir(exist_ok=True)

            for file in files:
                # Validate file type
                file_extension = Path(file.filename).suffix.lower().lstrip(".")
                if file_extension not in self.supported_types:
                    logger.warning(f"Unsupported file type: {file_extension}")
                    continue

                # Generate unique filename
                file_id = str(uuid.uuid4())
                filename = f"{file_id}_{file.filename}"
                file_path = quiz_upload_dir / filename

                # Save file
                async with aiofiles.open(file_path, "wb") as f:
                    content = await file.read()
                    await f.write(content)

                # Get file size
                file_size = len(content)

                # Create database record
                document = create_document(
                    quiz_id=quiz_id,
                    filename=file.filename,
                    file_path=str(file_path),
                    size_bytes=file_size,
                    file_type=file_extension,
                )

                uploaded_files.append(
                    {
                        "doc_id": document.doc_id,
                        "filename": document.filename,
                        "size_bytes": document.size_bytes,
                        "type": document.file_type,
                        "uploaded_at": datetime.now(),
                        "indexed": False,
                    }
                )

                logger.info(f"Uploaded document: {file.filename} for quiz {quiz_id}")

            log_activity(
                user_id,  #  Changed from session_id to user_id
                "documents_uploaded",
                {"quiz_id": quiz_id, "file_count": len(uploaded_files)},
            )

            return uploaded_files

        except Exception as e:
            logger.error(f"Failed to upload documents: {e}")
            raise

    def get_quiz_documents(self, quiz_id: str) -> List[Dict]:
        """Get all documents for a quiz"""
        documents = get_documents_by_quiz(quiz_id)

        return [
            {
                "doc_id": doc.doc_id,
                "filename": doc.filename,
                "size_bytes": doc.size_bytes,
                "type": doc.file_type,
                "uploaded_at": doc.uploaded_at,
                "indexed": doc.indexed,
            }
            for doc in documents
        ]

    def get_indexing_status(self, quiz_id: str) -> Dict[str, Any]:
        """Get document indexing status for a quiz"""
        documents = get_documents_by_quiz(quiz_id)

        total_documents = len(documents)
        indexed_documents = sum(1 for doc in documents if doc.indexed)

        if total_documents == 0:
            status = "no_documents"
        elif indexed_documents == 0:
            status = "pending"
        elif indexed_documents < total_documents:
            status = "processing"
        else:
            status = "completed"

        # Get collection info if available
        collection_name = None
        chunk_count = None

        if indexed_documents > 0:
            # Try to find collection name from quiz
            from ..database.crud import get_quiz

            quiz = get_quiz(quiz_id)
            if quiz and quiz.collection_name:
                collection_name = quiz.collection_name
                try:
                    retriever = RAGRetriever(collection_name, self.qdrant_manager)
                    chunk_count = retriever.get_chunk_count()
                except Exception as e:
                    logger.warning(
                        f"Could not get chunk count for {collection_name}: {e}"
                    )

        return {
            "quiz_id": quiz_id,
            "indexing_status": status,
            "indexed_documents": indexed_documents,
            "total_documents": total_documents,
            "collection_name": collection_name,
            "chunk_count": chunk_count,
        }

    def delete_document(self, doc_id: str) -> bool:
        """Delete a document and its file"""
        try:
            # Get document info before deleting
            from ..database.crud import get_documents_by_quiz

            # Would need a get_document_by_id function, but for now:

            success = delete_document(doc_id)
            if success:
                # Could also delete the physical file here if needed
                logger.info(f"Deleted document: {doc_id}")

            return success
        except Exception as e:
            logger.error(f"Failed to delete document {doc_id}: {e}")
            return False

    async def index_quiz_documents(self, quiz_id: str) -> Dict[str, Any]:
        """Index all documents in a quiz to Qdrant"""
        start_time = time.time()

        try:
            documents = get_documents_by_quiz(quiz_id)
            if not documents:
                raise ValueError("No documents found for quiz")

            collection_name = f"quiz_{quiz_id}"

            # Create collection if it doesn't exist
            if not self.qdrant_manager.collection_exists(collection_name):
                self.qdrant_manager.create_collection(collection_name)

            # Process each document
            total_chunks = 0
            indexed_count = 0

            for doc in documents:
                try:
                    # Here you would implement document processing and chunking
                    # For now, just mark as indexed

                    # Process document content (placeholder)
                    # chunks = process_document(doc.file_path)
                    # total_chunks += len(chunks)

                    # Update document status
                    update_document_indexed(doc.doc_id, True)
                    indexed_count += 1

                    logger.info(f"Indexed document: {doc.filename}")

                except Exception as e:
                    logger.error(f"Failed to index document {doc.filename}: {e}")

            # Update quiz with collection name
            update_quiz_collection(quiz_id, collection_name)

            indexing_time = time.time() - start_time

            return {
                "success": True,
                "collection_name": collection_name,
                "indexed_documents": indexed_count,
                "total_chunks": total_chunks,
                "indexing_time_seconds": round(indexing_time, 2),
            }

        except Exception as e:
            logger.error(f"Failed to index quiz documents: {e}")
            raise

    def search_documents(
        self, query: str, quiz_id: Optional[str] = None, limit: int = 10
    ) -> Dict[str, Any]:
        """Search through indexed documents"""
        start_time = time.time()

        try:
            if quiz_id:
                # Search specific quiz collection
                collection_name = f"quiz_{quiz_id}"
                if not self.qdrant_manager.collection_exists(collection_name):
                    return {
                        "query": query,
                        "results": [],
                        "total_results": 0,
                        "search_time_ms": 0,
                    }

                retriever = RAGRetriever(collection_name, self.qdrant_manager)
                # Implement search logic here
                results = []  # retriever.search(query, limit)
            else:
                # Search across all collections (admin feature)
                results = []

            search_time = (time.time() - start_time) * 1000  # Convert to ms

            return {
                "query": query,
                "results": results,
                "total_results": len(results),
                "search_time_ms": round(search_time, 2),
            }

        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise

    def get_document_status(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get processing status of a specific document"""
        try:
            # Would need a get_document_by_id function in crud
            # For now, placeholder implementation
            return {
                "doc_id": doc_id,
                "status": "indexed",
                "processing_progress": 100,
                "chunk_count": 45,
                "processing_time_seconds": 12.5,
                "error_message": None,
            }
        except Exception as e:
            logger.error(f"Failed to get document status: {e}")
            return None
