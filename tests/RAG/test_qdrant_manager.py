from unittest.mock import Mock, patch
import pytest

from src.Testaiownik.RAG.qdrant_manager import QdrantManager


class TestQdrantManager:

    @pytest.fixture
    def mock_embedding_model(self):
        """Mock embedding model."""
        model = Mock()
        model.embed_query.return_value = [0.1, 0.2, 0.3] * 512
        return model

    @pytest.fixture
    def qdrant_manager(self, mock_embedding_model):
        """Create QdrantManager instance with mocked dependencies."""
        with (
            patch("src.Testaiownik.RAG.qdrant_manager.QdrantClient") as mock_client,
            patch(
                "src.Testaiownik.RAG.qdrant_manager.get_embedding_model",
                return_value=mock_embedding_model,
            ),
        ):

            manager = QdrantManager()
            manager.client = Mock()
            return manager

    def test_init(self):
        with (
            patch("src.Testaiownik.RAG.qdrant_manager.QdrantClient") as mock_client,
            patch(
                "src.Testaiownik.RAG.qdrant_manager.get_embedding_model"
            ) as mock_get_model,
        ):

            manager = QdrantManager(url="http://test:1234", vector_size=768)

            assert manager.vector_size == 768
            assert manager.last_used_id == 0
            mock_client.assert_called_once_with(
                url="http://test:1234", timeout=None
            )  
            mock_get_model.assert_called_once()

    def test_create_collection_new(self, qdrant_manager):
        """Test creating a new collection."""
        qdrant_manager.client.get_collection.side_effect = Exception(
            "Collection not found"
        )
        qdrant_manager.client.create_collection.return_value = None

        result = qdrant_manager.create_collection("test_collection")

        assert result is True
        qdrant_manager.client.create_collection.assert_called_once()

    def test_create_collection_exists(self, qdrant_manager):
        """Test when collection already exists."""
        qdrant_manager.client.get_collection.return_value = Mock()

        result = qdrant_manager.create_collection("existing_collection")

        assert result is True
        qdrant_manager.client.create_collection.assert_not_called()

    def test_create_collection_error(self, qdrant_manager):
        """Test collection creation error."""
        qdrant_manager.client.get_collection.side_effect = Exception(
            "Collection not found"
        )
        qdrant_manager.client.create_collection.side_effect = Exception(
            "Creation failed"
        )

        result = qdrant_manager.create_collection("test_collection")

        assert result is False

    def test_create_collection_empty_name(self, qdrant_manager):
        """Test creating collection with empty name."""
        with pytest.raises(ValueError, match="Collection name cannot be empty"):
            qdrant_manager.create_collection("")

    def test_safe_to_list_with_numpy_array(self, qdrant_manager):
        """Test safe_to_list with numpy-like array."""
        mock_array = Mock()
        mock_array.tolist.return_value = [1, 2, 3]

        result = qdrant_manager.safe_to_list(mock_array)

        assert result == [1, 2, 3]
        mock_array.tolist.assert_called_once()

    def test_safe_to_list_with_list(self, qdrant_manager):
        """Test safe_to_list with regular list."""
        test_list = [1, 2, 3]

        result = qdrant_manager.safe_to_list(test_list)

        assert result == [1, 2, 3]

    def test_safe_to_list_with_other(self, qdrant_manager):
        """Test safe_to_list with other iterable."""
        test_tuple = (1, 2, 3)

        result = qdrant_manager.safe_to_list(test_tuple)

        assert result == [1, 2, 3]

    def test_chunk_text_normal(self, qdrant_manager):
        """Test normal text chunking."""
        text = "This is a test. " * 50

        chunks = qdrant_manager.chunk_text(text, min_chunk_size=200)

        assert len(chunks) > 1
        assert all(len(chunk) >= 150 for chunk in chunks[:-1])

    def test_chunk_text_short(self, qdrant_manager):
        """Test chunking with short text."""
        text = "Short text"

        chunks = qdrant_manager.chunk_text(text, min_chunk_size=500)

        assert len(chunks) == 1
        assert chunks[0] == "Short text"

    def test_chunk_text_empty(self, qdrant_manager):
        """Test chunking empty text."""
        chunks = qdrant_manager.chunk_text("", min_chunk_size=500)

        assert len(chunks) == 1
        assert chunks[0] == ""

    def test_process_file_pdf(self, qdrant_manager):
        """Test processing PDF file."""

        with patch(
            "src.Testaiownik.RAG.qdrant_manager.extract_text_from_pdf",
            return_value=[("PDF content", 1)],
        ) as mock_extract:
            result = qdrant_manager.process_file("test.pdf")

            assert result == [("PDF content", {"page": 1})]
            mock_extract.assert_called_once_with("test.pdf")

    def test_process_file_txt(self, qdrant_manager):
        """Test processing TXT file."""
        with patch(
            "src.Testaiownik.RAG.qdrant_manager.extract_text_from_txt",
            return_value="TXT content",
        ) as mock_extract:
            result = qdrant_manager.process_file("test.txt")

            assert result == [("TXT content", {})]
            mock_extract.assert_called_once_with("test.txt")

    def test_process_file_docx(self, qdrant_manager):
        """Test processing DOCX file."""
        with patch(
            "src.Testaiownik.RAG.qdrant_manager.extract_text_from_docx",
            return_value="DOCX content",
        ) as mock_extract:
            result = qdrant_manager.process_file("test.docx")

            assert result == [("DOCX content", {})]
            mock_extract.assert_called_once_with("test.docx")

    def test_process_file_pptx(self, qdrant_manager):
        """Test processing PPTX file."""

        with patch(
            "src.Testaiownik.RAG.qdrant_manager.extract_text_from_pptx",
            return_value=[("PPTX content", 1)],
        ) as mock_extract:
            result = qdrant_manager.process_file("test.pptx")

            assert result == [("PPTX content", {"slide": 1})]
            mock_extract.assert_called_once_with("test.pptx")

    def test_process_file_unsupported(self, qdrant_manager):
        """Test processing unsupported file type."""
        result = qdrant_manager.process_file("test.xyz")

        assert result == []

    def test_index_file_to_qdrant_success(self, qdrant_manager):

        initial_id = qdrant_manager.last_used_id

        with (
            patch.object(
                qdrant_manager,
                "process_file",
                return_value=[("Test content " * 100, {})],
            ),
            patch.object(
                qdrant_manager, "chunk_text", return_value=["chunk1", "chunk2"]
            ),
            patch.object(
                qdrant_manager.embedding_model,
                "embed_documents",
                return_value=[[0.1, 0.2], [0.3, 0.4]],
            ),
        ):

            qdrant_manager.client.upsert.return_value = None

            result = qdrant_manager.index_file_to_qdrant("test.txt", "test_collection")

            assert result is True
            assert qdrant_manager.last_used_id == initial_id + 2
            qdrant_manager.client.upsert.assert_called_once()

    def test_index_file_to_qdrant_no_text(self, qdrant_manager):
        """Test indexing when no text is extracted."""
        with patch.object(qdrant_manager, "process_file", return_value=""):

            result = qdrant_manager.index_file_to_qdrant("test.txt", "test_collection")

            assert result is False
            qdrant_manager.client.upsert.assert_not_called()

    def test_index_file_to_qdrant_no_chunks(self, qdrant_manager):
        """Test indexing when no chunks are created."""
        with (
            patch.object(qdrant_manager, "process_file", return_value="content"),
            patch.object(qdrant_manager, "chunk_text", return_value=[]),
        ):

            result = qdrant_manager.index_file_to_qdrant("test.txt", "test_collection")

            assert result is False
            qdrant_manager.client.upsert.assert_not_called()

    def test_index_file_to_qdrant_error(self, qdrant_manager):
        """Test indexing with error."""
        with patch.object(
            qdrant_manager, "process_file", side_effect=Exception("Processing error")
        ):

            result = qdrant_manager.index_file_to_qdrant("test.txt", "test_collection")

            assert result is False

    def test_search_in_collection_success(self, qdrant_manager):
        """Test successful search."""
        mock_result = Mock()
        mock_result.points = [Mock(), Mock()]
        qdrant_manager.client.query_points.return_value = mock_result

        result = qdrant_manager.search_in_collection(
            "test query", "test_collection", limit=2
        )

        assert len(result) == 2
        qdrant_manager.client.query_points.assert_called_once()

    def test_search_in_collection_empty_query(self, qdrant_manager):
        """Test search with empty query."""
        with pytest.raises(ValueError, match="Query cannot be empty"):
            qdrant_manager.search_in_collection("", "test_collection")

    def test_search_in_collection_invalid_limit(self, qdrant_manager):
        """Test search with invalid limit."""
        with pytest.raises(ValueError, match="Limit must be positive"):
            qdrant_manager.search_in_collection("test", "collection", limit=0)

    def test_search_in_collection_error(self, qdrant_manager):
        """Test search with error."""
        qdrant_manager.client.query_points.side_effect = Exception("Search error")

        result = qdrant_manager.search_in_collection("test", "collection")

        assert result is None

    def test_collection_exists_true(self, qdrant_manager):
        """Test collection exists check - true."""
        qdrant_manager.client.get_collection.return_value = Mock()

        result = qdrant_manager.collection_exists("test_collection")

        assert result is True

    def test_collection_exists_false(self, qdrant_manager):
        """Test collection exists check - false."""
        qdrant_manager.client.get_collection.side_effect = Exception("Not found")

        result = qdrant_manager.collection_exists("test_collection")

        assert result is False

    def test_delete_collection_success(self, qdrant_manager):
        """Test successful collection deletion."""
        qdrant_manager.client.delete_collection.return_value = None

        result = qdrant_manager.delete_collection("test_collection")

        assert result is True
        qdrant_manager.client.delete_collection.assert_called_once_with(
            collection_name="test_collection"
        )

    def test_delete_collection_error(self, qdrant_manager):
        """Test collection deletion error."""
        qdrant_manager.client.delete_collection.side_effect = Exception("Delete error")

        result = qdrant_manager.delete_collection("test_collection")

        assert result is False


if __name__ == "__main__":
    pytest.main([__file__])
