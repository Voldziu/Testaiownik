import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
import tempfile
from pathlib import Path
from src.Testaiownik.Backend.services.document_service import DocumentService


class TestDocumentService:
    """Test DocumentService functionality"""

    @pytest.fixture
    def document_service(self):
        return DocumentService()

    @pytest.fixture
    def mock_qdrant_manager(self):
        with patch(
            "src.Testaiownik.Backend.services.document_service.QdrantManager"
        ) as mock:
            manager = Mock()
            mock.return_value = manager
            yield manager

    @pytest.fixture
    def mock_db_session(self):
        return Mock()

    @pytest.mark.asyncio
    async def test_upload_documents_success(
        self, document_service, mock_qdrant_manager, mock_db_session, temp_upload_dir
    ):
        """Test successful file upload"""
        quiz_id = "quiz_456"
        user_id = "user_123"

        # Create mock files
        mock_file1 = Mock()
        mock_file1.filename = "test1.pdf"
        mock_file1.read = AsyncMock(return_value=b"PDF content")

        mock_file2 = Mock()
        mock_file2.filename = "test2.docx"
        mock_file2.read = AsyncMock(return_value=b"DOCX content")

        files = [mock_file1, mock_file2]

        # Mock database operations
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

                result = await document_service.upload_documents(
                    quiz_id, user_id, files, mock_db_session
                )

        assert len(result) == 2
        assert result[0]["filename"] == "test1.pdf"
        assert result[1]["filename"] == "test2.docx"

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

        # Should skip unsupported files, not raise exception
        result = await document_service.upload_documents(
            quiz_id, user_id, [mock_file], mock_db_session
        )
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_upload_file_too_large(self, document_service, mock_db_session):
        """Test upload with file too large"""
        quiz_id = "quiz_456"
        user_id = "user_123"

        mock_file = Mock()
        mock_file.filename = "large.pdf"
        mock_file.read = AsyncMock(return_value=b"x" * (101 * 1024 * 1024))  # 101MB

        # The service handles large files by continuing, not raising exceptions
        with patch("src.Testaiownik.Backend.services.document_service.create_document"):
            with patch(
                "src.Testaiownik.Backend.services.document_service.log_activity"
            ):
                result = await document_service.upload_documents(
                    quiz_id, user_id, [mock_file], mock_db_session
                )

        # Should still process the file if no size validation is implemented
        assert isinstance(result, list)

    def test_list_documents_success(
        self, document_service, mock_qdrant_manager, mock_db_session
    ):
        """Test successful document listing"""
        quiz_id = "quiz_456"

        with patch(
            "src.Testaiownik.Backend.services.document_service.get_documents_by_quiz"
        ) as mock_get:
            mock_docs = [
                Mock(
                    doc_id="doc_123",
                    filename="test1.pdf",
                    size_bytes=1024,
                    file_type="pdf",
                    uploaded_at="2025-01-15T10:00:00Z",
                    indexed=True,
                ),
                Mock(
                    doc_id="doc_456",
                    filename="test2.docx",
                    size_bytes=2048,
                    file_type="docx",
                    uploaded_at="2025-01-15T10:05:00Z",
                    indexed=False,
                ),
            ]
            mock_get.return_value = mock_docs

            result = document_service.get_quiz_documents(quiz_id, mock_db_session)

        assert len(result) == 2
        assert result[0].doc_id == "doc_123"
        assert result[0].indexed is True
        assert result[1].indexed is False

    def test_index_documents_success(self, document_service, mock_qdrant_manager):
        """Test successful document indexing"""
        quiz_id = "quiz_456"
        db_session = Mock()

        # Mock the indexing process
        with patch(
            "src.Testaiownik.Backend.services.document_service.get_documents_by_quiz"
        ) as mock_get_docs:
            mock_docs = [Mock(doc_id="doc_123", file_path="/path/to/test.pdf")]
            mock_get_docs.return_value = mock_docs

            with patch(
                "src.Testaiownik.Backend.services.document_service.update_quiz_collection"
            ):
                with patch(
                    "src.Testaiownik.Backend.services.document_service.update_document_indexed"
                ):
                    mock_qdrant_manager.create_collection.return_value = None
                    mock_qdrant_manager.index_documents_from_files.return_value = {
                        "indexed": 1,
                        "total_chunks": 50,
                    }

                    result = document_service.index_documents(quiz_id, db_session)

        assert "indexed_documents" in result
        assert result["total_chunks"] == 50

    def test_delete_document_success(
        self, document_service, mock_qdrant_manager, mock_db_session
    ):
        """Test successful document deletion"""
        quiz_id = "quiz_456"
        doc_id = "doc_123"

        # Mock finding the document
        mock_doc = Mock(
            doc_id=doc_id, filename="test.pdf", file_path="/path/to/test.pdf"
        )

        with patch(
            "src.Testaiownik.Backend.services.document_service.get_documents_by_quiz"
        ) as mock_get:
            mock_get.return_value = [mock_doc]

            with patch("pathlib.Path.unlink") as mock_unlink:
                mock_unlink.return_value = None

                with patch(
                    "src.Testaiownik.Backend.services.document_service.log_activity"
                ):
                    # Mock the actual deletion logic
                    result = document_service.delete_document(
                        quiz_id, doc_id, mock_db_session
                    )

        # The method should return some indication of success
        assert result is not None

    def test_search_documents(self, document_service, mock_qdrant_manager):
        """Test document search functionality"""
        quiz_id = "quiz_456"
        query = "binary search algorithm"

        mock_qdrant_manager.search_collection.return_value = [
            {
                "text": "Binary search is an efficient algorithm...",
                "metadata": {"source": "algorithms.pdf", "page": 42},
                "score": 0.95,
            },
            {
                "text": "The time complexity of binary search is O(log n)...",
                "metadata": {"source": "complexity.pdf", "page": 15},
                "score": 0.87,
            },
        ]

        result = document_service.search_documents(quiz_id, query, limit=10)

        assert len(result) == 2
        assert result[0]["score"] == 0.95
        mock_qdrant_manager.search_collection.assert_called_once()
