from unittest.mock import Mock
import pytest


class TestRAGRetriever:

    @pytest.fixture
    def mock_vector_store(self):
        """Mock vector store."""
        vector_store = Mock()
        vector_store.client = Mock()
        return vector_store

    @pytest.fixture
    def rag_retriever(self, mock_vector_store):
        """Create RAGRetriever instance."""
        from RAG.Retrieval.Retriever import RAGRetriever

        return RAGRetriever("test_collection", mock_vector_store)

    def test_get_all_chunks_success(self, rag_retriever, mock_vector_store):
        # Mock first scroll result
        mock_point1 = Mock()
        mock_point1.payload = {"text": "chunk1"}

        mock_point2 = Mock()
        mock_point2.payload = {"text": "chunk2"}

        # Mock second scroll result
        mock_point3 = Mock()
        mock_point3.payload = {"text": "chunk3"}

        mock_vector_store.client.scroll.side_effect = [
            ([mock_point1, mock_point2], "offset1"),  # First call
            ([mock_point3], None),  # Second call
        ]

        chunks = list(rag_retriever.get_all_chunks())

        # Changed: Now expects payload objects, not just text
        assert chunks == [{"text": "chunk1"}, {"text": "chunk2"}, {"text": "chunk3"}]
        assert mock_vector_store.client.scroll.call_count == 2

    def test_get_all_chunks_no_text_payload(self, rag_retriever, mock_vector_store):
        """Test chunk retrieval with points missing text payload."""
        mock_point1 = Mock()
        mock_point1.payload = {"text": "chunk1"}

        mock_point2 = Mock()
        mock_point2.payload = {"other": "data"}

        mock_vector_store.client.scroll.return_value = (
            [mock_point1, mock_point2],
            None,
        )

        chunks = list(rag_retriever.get_all_chunks())

        # Changed: Now expects payload objects
        assert chunks == [{"text": "chunk1"}]

    def test_get_all_chunks_error(self, rag_retriever, mock_vector_store):
        """Test chunk retrieval with error."""
        mock_vector_store.client.scroll.side_effect = Exception("Scroll error")

        chunks = list(rag_retriever.get_all_chunks())

        assert chunks == []

    def test_get_chunk_count_success(self, rag_retriever, mock_vector_store):
        """Test successful chunk count."""
        mock_result = Mock()
        mock_result.count = 42
        mock_vector_store.client.count.return_value = mock_result

        count = rag_retriever.get_chunk_count()

        assert count == 42
        mock_vector_store.client.count.assert_called_once_with(
            collection_name="test_collection"
        )

    def test_get_chunk_count_error(self, rag_retriever, mock_vector_store):
        """Test chunk count with error."""
        mock_vector_store.client.count.side_effect = Exception("Count error")

        count = rag_retriever.get_chunk_count()

        assert count == 0


if __name__ == "__main__":
    pytest.main([__file__])
