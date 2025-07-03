import pytest
from unittest.mock import patch, Mock
from fastapi import HTTPException
import tempfile
from pathlib import Path


class TestDocumentsAPI:
    """Test Documents API endpoints"""

    def test_upload_files_success(self, client, mock_user_id):
        """Test successful file upload"""
        with patch(
            "src.Testaiownik.Backend.api.documents.get_user_id",
            return_value=mock_user_id,
        ):
            with patch("src.Testaiownik.Backend.api.documents.validate_quiz_access"):
                with patch(
                    "src.Testaiownik.Backend.api.documents.document_service"
                ) as mock_service:
                    # Mock the async upload_documents method
                    async def mock_upload_documents(quiz_id, user_id, files, db):
                        return [
                            {
                                "doc_id": "doc_123",
                                "filename": "test.pdf",
                                "size_bytes": 1024,
                                "type": "pdf",
                                "uploaded_at": "2025-01-15T10:00:00Z",
                                "indexed": False,
                            }
                        ]

                    mock_service.upload_documents = mock_upload_documents

                    # Create a temporary file for testing
                    with tempfile.NamedTemporaryFile(
                        suffix=".pdf", delete=False
                    ) as temp_file:
                        temp_file.write(b"Test PDF content")
                        temp_file_path = temp_file.name

                    try:
                        with open(temp_file_path, "rb") as f:
                            files = {"files": ("test.pdf", f, "application/pdf")}
                            response = client.post(
                                "/api/documents/quiz_456/upload", files=files
                            )

                        assert response.status_code == 200
                        data = response.json()
                        assert "uploaded_files" in data
                        assert data["quiz_id"] == "quiz_456"
                    finally:
                        Path(temp_file_path).unlink()

    def test_upload_unsupported_file_type(self, client, mock_user_id):
        """Test upload with unsupported file type"""
        with patch(
            "src.Testaiownik.Backend.api.documents.get_user_id",
            return_value=mock_user_id,
        ):
            with patch("src.Testaiownik.Backend.api.documents.validate_quiz_access"):
                files = {
                    "files": ("test.exe", b"executable", "application/x-executable")
                }
                response = client.post("/api/documents/quiz_456/upload", files=files)

                assert response.status_code == 400

    def test_list_documents_success(self, client, mock_user_id):
        """Test successful document listing"""
        with patch(
            "src.Testaiownik.Backend.api.documents.get_user_id",
            return_value=mock_user_id,
        ):
            with patch("src.Testaiownik.Backend.api.documents.validate_quiz_access"):
                with patch(
                    "src.Testaiownik.Backend.api.documents.document_service"
                ) as mock_service:
                    mock_service.get_quiz_documents.return_value = [
                        Mock(
                            doc_id="doc_123",
                            filename="test.pdf",
                            size_bytes=1024,
                            file_type="pdf",
                            uploaded_at="2025-01-15T10:00:00Z",
                            indexed=True,
                        )
                    ]

                    response = client.get("/api/documents/quiz_456/list")

                    assert response.status_code == 200
                    data = response.json()
                    assert "documents" in data
                    assert data["quiz_id"] == "quiz_456"

    def test_index_documents_success(self, client, mock_user_id):
        """Test successful document indexing"""
        with patch(
            "src.Testaiownik.Backend.api.documents.get_user_id",
            return_value=mock_user_id,
        ):
            with patch("src.Testaiownik.Backend.api.documents.validate_quiz_access"):
                with patch(
                    "src.Testaiownik.Backend.api.documents.document_service"
                ) as mock_service:
                    mock_service.index_documents.return_value = {
                        "indexed_documents": 1,
                        "total_chunks": 50,
                    }

                    request_data = {"chunk_size": 500, "batch_size": 50}

                    response = client.post(
                        "/api/documents/quiz_456/index", json=request_data
                    )

                    assert response.status_code == 200
                    data = response.json()
                    assert "indexed_documents" in data
                    assert "total_chunks" in data

    def test_delete_document_success(self, client, mock_user_id):
        """Test successful document deletion"""
        with patch(
            "src.Testaiownik.Backend.api.documents.get_user_id",
            return_value=mock_user_id,
        ):
            with patch("src.Testaiownik.Backend.api.documents.validate_quiz_access"):
                with patch(
                    "src.Testaiownik.Backend.api.documents.document_service"
                ) as mock_service:
                    mock_service.delete_document.return_value = {
                        "success": True,
                        "doc_id": "doc_123",
                    }

                    response = client.delete("/api/documents/quiz_456/doc_123")

                    assert response.status_code == 200
                    data = response.json()
                    assert data["success"] is True

    def test_get_indexing_status(self, client, mock_user_id):
        """Test indexing status retrieval"""
        with patch(
            "src.Testaiownik.Backend.api.documents.get_user_id",
            return_value=mock_user_id,
        ):
            with patch("src.Testaiownik.Backend.api.documents.validate_quiz_access"):
                with patch(
                    "src.Testaiownik.Backend.api.documents.document_service"
                ) as mock_service:
                    mock_service.get_indexing_status.return_value = {
                        "status": "completed",
                        "indexed_documents": 3,
                        "total_documents": 3,
                    }

                    response = client.get("/api/documents/quiz_456/status")

                    assert response.status_code == 200
                    data = response.json()
                    assert data["indexing_status"] == "completed"
