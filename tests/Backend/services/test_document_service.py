import pytest
from unittest.mock import Mock, patch, AsyncMock
from src.Testaiownik.Backend.services.document_service import DocumentService


class TestDocumentService:
    """Test DocumentService functionality - only real methods"""

    @pytest.fixture
    def document_service(self):
        return DocumentService()

    @pytest.mark.asyncio
    async def test_upload_documents_success(
        self, document_service, mock_db_session, temp_upload_dir
    ):
        """Test successful document upload"""
        quiz_id = "quiz_456"
        user_id = "user_123"

        mock_file1 = Mock()
        mock_file1.filename = "test1.pdf"
        mock_file1.read = AsyncMock(return_value=b"PDF content")

        mock_file2 = Mock()
        mock_file2.filename = "test2.docx"
        mock_file2.read = AsyncMock(return_value=b"DOCX content")

        files = [mock_file1, mock_file2]

        with patch(
            "src.Testaiownik.Backend.services.document_service.create_document"
        ) as mock_create:
            with patch(
                "src.Testaiownik.Backend.services.document_service.log_activity"
            ):
                mock_doc1 = Mock()
                mock_doc1.doc_id = "doc_1"
                mock_doc1.filename = "test1.pdf"
                mock_doc1.size_bytes = 11
                mock_doc1.file_type = "pdf"
                mock_doc1.uploaded_at = "2025-01-15T10:00:00Z"
                mock_doc1.indexed = False

                mock_doc2 = Mock()
                mock_doc2.doc_id = "doc_2"
                mock_doc2.filename = "test2.docx"
                mock_doc2.size_bytes = 12
                mock_doc2.file_type = "docx"
                mock_doc2.uploaded_at = "2025-01-15T10:00:00Z"
                mock_doc2.indexed = False

                mock_create.side_effect = [mock_doc1, mock_doc2]

                document_service.upload_dir = temp_upload_dir

                result = await document_service.upload_documents(
                    quiz_id, user_id, files, mock_db_session
                )

        assert len(result) == 2
        assert result[0]["filename"] == "test1.pdf"
        assert result[1]["filename"] == "test2.docx"
        assert result[0]["doc_id"] == "doc_1"
        assert result[1]["doc_id"] == "doc_2"

    @pytest.mark.asyncio
    async def test_upload_unsupported_file_type(
        self, document_service, mock_db_session
    ):
        """Test upload with unsupported file type"""
        quiz_id = "quiz_456"
        user_id = "user_123"

        mock_file = Mock()
        mock_file.filename = "test.exe"
        mock_file.read = AsyncMock(return_value=b"executable content")

        result = await document_service.upload_documents(
            quiz_id, user_id, [mock_file], mock_db_session
        )

        assert len(result) == 0

    def test_get_quiz_documents(self, document_service, mock_db_session, mock_document):
        """Test getting quiz documents"""
        quiz_id = "quiz_456"

        with patch(
            "src.Testaiownik.Backend.services.document_service.get_documents_by_quiz"
        ) as mock_get:
            mock_get.return_value = [mock_document]

            result = document_service.get_quiz_documents(quiz_id, mock_db_session)

            assert len(result) == 1
            assert result[0].doc_id == "doc_123"
            assert result[0].filename == "test.pdf"

    def test_get_indexing_status_no_documents(self, document_service, mock_db_session):
        """Test indexing status with no documents"""
        quiz_id = "quiz_456"

        with patch(
            "src.Testaiownik.Backend.services.document_service.get_documents_by_quiz"
        ) as mock_get:
            mock_get.return_value = []

            result = document_service.get_indexing_status(quiz_id, mock_db_session)

            assert result["quiz_id"] == quiz_id
            assert result["indexing_status"] == "no_documents"
            assert result["total_documents"] == 0
            assert result["indexed_documents"] == 0

    def test_get_indexing_status_pending(
        self, document_service, mock_db_session, mock_document
    ):
        """Test indexing status with pending documents"""
        quiz_id = "quiz_456"

        with patch(
            "src.Testaiownik.Backend.services.document_service.get_documents_by_quiz"
        ) as mock_get:
            mock_get.return_value = [mock_document]

            result = document_service.get_indexing_status(quiz_id, mock_db_session)

            assert result["indexing_status"] == "pending"
            assert result["total_documents"] == 1
            assert result["indexed_documents"] == 0

    def test_get_indexing_status_completed(
        self, document_service, mock_db_session, mock_document
    ):
        """Test indexing status with completed documents"""
        quiz_id = "quiz_456"
        mock_document.indexed = True

        with patch(
            "src.Testaiownik.Backend.services.document_service.get_documents_by_quiz"
        ) as mock_get:
            with patch(
                "src.Testaiownik.Backend.database.crud.get_quiz"
            ) as mock_get_quiz:
                mock_quiz = Mock()
                mock_quiz.collection_name = "quiz_456_collection"
                mock_get_quiz.return_value = mock_quiz
                mock_get.return_value = [mock_document]

                result = document_service.get_indexing_status(quiz_id, mock_db_session)

                assert result["indexing_status"] == "completed"
                assert result["total_documents"] == 1
                assert result["indexed_documents"] == 1
                assert result["collection_name"] == "quiz_456_collection"

    def test_delete_document_success(self, document_service, mock_db_session):
        """Test successful document deletion"""
        doc_id = "doc_123"

        with patch(
            "src.Testaiownik.Backend.database.crud.delete_document"
        ) as mock_delete:
            mock_delete.return_value = True

            result = document_service.delete_document(doc_id, mock_db_session)

            assert result is True
            mock_delete.assert_called_once_with(mock_db_session, doc_id)

    def test_delete_document_failure(self, document_service, mock_db_session):
        """Test document deletion failure"""
        doc_id = "doc_123"

        with patch(
            "src.Testaiownik.Backend.database.crud.delete_document"
        ) as mock_delete:
            mock_delete.side_effect = Exception("Database error")

            result = document_service.delete_document(doc_id, mock_db_session)

            assert result is False

    @pytest.mark.asyncio
    async def test_index_quiz_documents_success(
        self, document_service, mock_db_session, mock_document, mock_qdrant_manager
    ):
        """Test successful document indexing"""
        quiz_id = "quiz_456"

        with patch(
            "src.Testaiownik.Backend.services.document_service.get_documents_by_quiz"
        ) as mock_get:
            with patch(
                "src.Testaiownik.Backend.services.document_service.update_document_indexed"
            ):
                with patch(
                    "src.Testaiownik.Backend.services.document_service.update_quiz_collection"
                ):
                    document_service.qdrant_manager = mock_qdrant_manager
                    mock_get.return_value = [mock_document]

                    result = await document_service.index_quiz_documents(
                        quiz_id, mock_db_session
                    )

                    assert result["indexed_documents"] == 1
                    assert result["collection_name"] == f"quiz_{quiz_id}"
                    assert "indexing_time_seconds" in result

    @pytest.mark.asyncio
    async def test_index_quiz_documents_no_documents(
        self, document_service, mock_db_session
    ):
        """Test indexing with no documents"""
        quiz_id = "quiz_456"

        with patch(
            "src.Testaiownik.Backend.services.document_service.get_documents_by_quiz"
        ) as mock_get:
            mock_get.return_value = []

            with pytest.raises(ValueError, match="No documents found for quiz"):
                await document_service.index_quiz_documents(quiz_id, mock_db_session)
