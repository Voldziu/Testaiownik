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
        self, quiz_id: str, session_id: str, files: List[Any]
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
                        "status": "uploaded",
                    }
                )

                logger.info(f"Uploaded document: {file.filename} for quiz {quiz_id}")

            log_activity(
                session_id,
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

    def get_indexing_status(self, quiz_id: str) -> Dict:
        """Get indexing status for quiz documents"""
        documents = get_documents_by_quiz(quiz_id)

        if not documents:
            return {
                "quiz_id": quiz_id,
                "indexing_status": "no_documents",
                "indexed_documents": 0,
                "total_documents": 0,
                "collection_name": None,
                "chunk_count": None,
            }

        indexed_count = sum(1 for doc in documents if doc.indexed)
        total_count = len(documents)

        # Determine status
        if indexed_count == 0:
            status = "pending"
        elif indexed_count < total_count:
            status = "processing"
        else:
            status = "completed"

        # Get collection info
        collection_name = f"quiz_{quiz_id}"
        chunk_count = None

        if self.qdrant_manager.collection_exists(collection_name):
            try:
                # Get chunk count from collection
                from RAG.Retrieval import RAGRetriever

                retriever = RAGRetriever(collection_name, self.qdrant_manager)
                chunk_count = retriever.get_chunk_count()
            except Exception as e:
                logger.error(f"Failed to get chunk count: {e}")

        return {
            "quiz_id": quiz_id,
            "indexing_status": status,
            "indexed_documents": indexed_count,
            "total_documents": total_count,
            "collection_name": collection_name if chunk_count else None,
            "chunk_count": chunk_count,
        }

    async def index_documents(
        self, quiz_id: str, session_id: str, chunk_size: int = 500, batch_size: int = 50
    ) -> Dict:
        """Index all documents for a quiz into Qdrant"""
        try:
            documents = get_documents_by_quiz(quiz_id)
            if not documents:
                raise ValueError("No documents found for quiz")

            collection_name = f"quiz_{quiz_id}"

            # Create collection
            success = self.qdrant_manager.create_collection(collection_name)
            if not success:
                raise RuntimeError("Failed to create Qdrant collection")

            start_time = time.time()
            indexed_docs = 0
            total_chunks = 0

            # Index each document
            for document in documents:
                if document.indexed:
                    logger.info(
                        f"Skipping already indexed document: {document.filename}"
                    )
                    continue

                try:
                    # Index document
                    success = self.qdrant_manager.index_file_to_qdrant(
                        file_path=document.file_path,
                        collection_name=collection_name,
                        batch_size=batch_size,
                    )

                    if success:
                        # Mark as indexed
                        update_document_indexed(document.doc_id, True)
                        indexed_docs += 1
                        logger.info(f"Indexed document: {document.filename}")
                    else:
                        logger.error(f"Failed to index document: {document.filename}")

                except Exception as e:
                    logger.error(f"Error indexing document {document.filename}: {e}")
                    continue

            # Get final chunk count
            try:
                retriever = RAGRetriever(collection_name, self.qdrant_manager)
                total_chunks = retriever.get_chunk_count()
            except Exception as e:
                logger.error(f"Failed to get final chunk count: {e}")
                total_chunks = 0

            indexing_time = time.time() - start_time

            # Update quiz with collection name
            update_quiz_collection(quiz_id, collection_name)

            log_activity(
                session_id,
                "documents_indexed",
                {
                    "quiz_id": quiz_id,
                    "indexed_documents": indexed_docs,
                    "total_chunks": total_chunks,
                    "indexing_time": indexing_time,
                },
            )

            return {
                "success": True,
                "collection_name": collection_name,
                "indexed_documents": indexed_docs,
                "total_chunks": total_chunks,
                "indexing_time_seconds": round(indexing_time, 2),
            }

        except Exception as e:
            logger.error(f"Failed to index documents: {e}")
            raise

    def delete_quiz_document(self, quiz_id: str, doc_id: str, session_id: str) -> Dict:
        """Delete a specific document"""
        try:
            # Get document info
            documents = get_documents_by_quiz(quiz_id)
            document = next((doc for doc in documents if doc.doc_id == doc_id), None)

            if not document:
                raise ValueError("Document not found")

            # Delete file from disk
            try:
                file_path = Path(document.file_path)
                if file_path.exists():
                    file_path.unlink()
            except Exception as e:
                logger.error(f"Failed to delete file from disk: {e}")

            # Delete from database
            success = delete_document(doc_id)
            if not success:
                raise RuntimeError("Failed to delete document from database")

            log_activity(
                session_id,
                "document_deleted",
                {"quiz_id": quiz_id, "doc_id": doc_id, "filename": document.filename},
            )

            # Check if reindexing is needed
            remaining_docs = get_documents_by_quiz(quiz_id)
            reindexing_required = any(doc.indexed for doc in remaining_docs)

            return {
                "success": True,
                "message": "Document removed successfully",
                "doc_id": doc_id,
                "reindexing_required": reindexing_required,
            }

        except Exception as e:
            logger.error(f"Failed to delete document: {e}")
            raise

    def search_documents(
        self, query: str, quiz_id: Optional[str] = None, limit: int = 10
    ) -> Dict:
        """Search through indexed documents"""
        try:
            start_time = time.time()
            results = []

            if quiz_id:
                # Search in specific quiz collection
                collection_name = f"quiz_{quiz_id}"
                if self.qdrant_manager.collection_exists(collection_name):
                    search_results = self.qdrant_manager.search_in_collection(
                        query=query, collection_name=collection_name, limit=limit
                    )

                    if search_results:
                        for result in search_results:
                            payload = result.payload
                            results.append(
                                {
                                    "text": payload.get("text", ""),
                                    "source": payload.get("source", ""),
                                    "page": payload.get("page"),
                                    "relevance_score": result.score,
                                    "quiz_id": quiz_id,
                                }
                            )
            else:
                # Search across all collections (not implemented in current design)
                # Would need to track all collections and search each
                pass

            search_time = time.time() - start_time

            return {
                "query": query,
                "results": results,
                "total_results": len(results),
                "search_time_ms": round(search_time * 1000),
            }

        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise

    def cleanup_quiz_files(self, quiz_id: str, session_id: str) -> bool:
        """Clean up all files for a quiz"""
        try:
            # Delete files from disk
            quiz_upload_dir = self.upload_dir / quiz_id
            if quiz_upload_dir.exists():
                import shutil

                shutil.rmtree(quiz_upload_dir)

            # Delete Qdrant collection
            collection_name = f"quiz_{quiz_id}"
            if self.qdrant_manager.collection_exists(collection_name):
                self.qdrant_manager.delete_collection(collection_name)

            log_activity(session_id, "quiz_files_cleaned", {"quiz_id": quiz_id})
            return True

        except Exception as e:
            logger.error(f"Failed to cleanup quiz files: {e}")
            return False
