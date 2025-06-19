from abc import ABC, abstractmethod
from typing import Iterator, Optional, List
from ..qdrant_manager import QdrantManager
from qdrant_client.models import PointStruct
from utils.logger import logger


# DocumentRetriever is an abstract base class for retrieving documents.
class DocumentRetriever(ABC):
    @abstractmethod
    def get_all_chunks(self) -> Iterator[str]:
        """Stream all indexed chunks."""
        pass

    @abstractmethod
    def get_chunk_count(self) -> int:
        """Total number of chunks."""
        pass

    @abstractmethod
    def search_in_collection(
        query: str, collection_name: str, limit: int = 10
    ) -> Optional[List[PointStruct]]:
        pass


# MockRetriever is a mock implementation of DocumentRetriever for testing purposes.
class MockRetriever(DocumentRetriever):
    def get_all_chunks(self) -> Iterator[str]:
        chunks = [
            "Algorytmy sortowania to fundamentalne narzędzia w informatyce...",
            "Struktury danych to sposoby organizacji i przechowywania informacji...",
            "Złożoność obliczeniowa to miara efektywności algorytmów...",
        ]
        for chunk in chunks:
            yield chunk

    def get_chunk_count(self) -> int:
        return 3

    def search_in_collection(
        query: str, collection_name: str, limit: int = 10
    ) -> Optional[List[PointStruct]]:
        pass


class RAGRetriever(DocumentRetriever):
    def __init__(self, collection_name: str, vector_store: QdrantManager):
        self.vector_store = vector_store
        self.collection_name = collection_name

    def get_all_chunks(self) -> Iterator[dict]:
        """Streams all payloads (text + metadata) from Qdrant."""
        try:
            scroll_result = self.vector_store.client.scroll(
                collection_name=self.collection_name,
                limit=100,
                with_payload=True,
                with_vectors=False,
            )

            points, next_page_offset = scroll_result

            for point in points:
                if "text" in point.payload:
                    yield point.payload

            while next_page_offset is not None:
                scroll_result = self.vector_store.client.scroll(
                    collection_name=self.collection_name,
                    limit=100,
                    offset=next_page_offset,
                    with_payload=True,
                    with_vectors=False,
                )
                points, next_page_offset = scroll_result

                for point in points:
                    if "text" in point.payload:
                        yield point.payload

        except Exception as e:
            logger.error(f"Błąd podczas pobierania chunks: {e}")
            return

    def get_chunk_count(self) -> int:
        """Returns the total number of chunks in the collection."""
        try:
            count_result = self.vector_store.client.count(
                collection_name=self.collection_name
            )
            return count_result.count
        except Exception as e:
            logger.error(f"Błąd podczas liczenia chunks: {e}")
            return 0

    def search_in_collection(
        self, query: str, limit: int = 10
    ) -> Optional[List[PointStruct]]:
        return self.vector_store.search_in_collection(
            query, self.collection_name, limit
        )
