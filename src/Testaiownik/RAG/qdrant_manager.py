from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct
from AzureModels.models import get_embedding_model
from .file_processor import extract_text_from_docx, extract_text_from_pdf, extract_text_from_txt, extract_text_from_pptx
from typing import Optional, List
from utils.logger import logger

class QdrantManager:
    def __init__(self, url: str = "http://localhost:6333", vector_size: int = 1536):
        self.client = QdrantClient(url=url)
        self.vector_size = vector_size
        self.embedding_model = get_embedding_model(api_version="2024-12-01-preview")
        self.last_used_id = 0

    def create_collection(self, collection_name: str, distance_metric: str = "Dot") -> bool:
        """Creates a collection in Qdrant with error handling."""
        if not collection_name:
            raise ValueError("Collection name cannot be empty")
            
        try:
            self.client.get_collection(collection_name=collection_name)
            logger.info(f"Kolekcja '{collection_name}' już istnieje.")
            return True
        except Exception:
            try:
                logger.info(f"Tworzę nową kolekcję '{collection_name}'...")
                self.client.create_collection(
                    collection_name=collection_name,
                    vectors_config={"size": self.vector_size, "distance": distance_metric}
                )
                logger.info(f"Kolekcja '{collection_name}' została utworzona.")
                return True
            except Exception as e:
                logger.error(f"Błąd podczas tworzenia kolekcji: {e}")
                return False

    def safe_to_list(self, data):
        """Convert safely to list"""
        if hasattr(data, 'tolist'):  
            return data.tolist()
        elif isinstance(data, list):  
            return data
        else:
            return list(data)

    def chunk_text(self, text: str, min_chunk_size: int = 500) -> List[str]:
        """Chunks the text into larger fragments of at least `min_chunk_size` characters."""
        chunks = []
        start_idx = 0

        while start_idx < len(text):
            # Find the next reasonable split point (either by space or the `min_chunk_size`)
            end_idx = start_idx + min_chunk_size
            if end_idx >= len(text):
                chunks.append(text[start_idx:])
                break

            # Find the last space within the chunk to avoid cutting off in the middle of a word
            if text[end_idx] != ' ':
                space_idx = text.rfind(' ', start_idx, end_idx)
                if space_idx != -1:
                    end_idx = space_idx
            
            # Append the chunk
            chunks.append(text[start_idx:end_idx].strip())
            start_idx = end_idx
        
        return chunks
    

    def process_file(self, file_path: str) -> Optional[str]:
        """Determines the type of file (PDF/TXT) and processes it accordingly."""
        if file_path.endswith('.pdf'):
            return extract_text_from_pdf(file_path)
        elif file_path.endswith('.txt'):
            return extract_text_from_txt(file_path)
        elif file_path.endswith('.pptx'):
            return extract_text_from_pptx(file_path)
        elif file_path.endswith('.docx'):
            return extract_text_from_docx(file_path)
        else:
            logger.error(f"Nieobsługiwany typ pliku: {file_path}")
            return None


    def index_file_to_qdrant(self, file_path: str, collection_name: str) -> bool:
        """Indexes content from a file (PDF or TXT) into Qdrant."""
        try:
            # Process the file to extract text
            text = self.process_file(file_path)
            if not text:
                logger.warning(f"Nie udało się wyodrębnić tekstu z pliku: {file_path}")
                return False

            # Chunk the text into larger pieces
            chunks = self.chunk_text(text, min_chunk_size=500)
            if not chunks:
                logger.warning("Nie znaleziono fragmentów tekstu do indeksowania")
                return False

            # Encoding chunks to vectors using the embedding model
            vectors = self.embedding_model.embed_documents(chunks)

            if vectors:
                logger.info(f"Type of first vector: {type(vectors[0])}")
                logger.info(f"Length of vectors: {len(vectors)}")

            points = []
            for i, (chunk, vector) in enumerate(zip(chunks, vectors)):
                self.last_used_id += 1  
                safe_vector = self.safe_to_list(vector)
                points.append(PointStruct(
                    id=self.last_used_id,  # sequential ID
                    vector=safe_vector,
                    payload={
                        "text": chunk,
                        "source": file_path,
                        "chunk_id": i
                    }
                ))

            # Upsert points
            self.client.upsert(collection_name=collection_name, points=points)
            logger.info(f"Dodano {len(points)} punktów do kolekcji '{collection_name}' z ID od {self.last_used_id - len(points) + 1} do {self.last_used_id}.")
            return True

        except Exception as e:
            logger.error(f"Błąd podczas indeksowania pliku: {e}")
            return False

    def search_in_collection(self, query: str, collection_name: str, limit: int = 3):
        """Search for similar documents in Qdrant with validation."""
        if not query.strip():
            raise ValueError("Query cannot be empty")
        if limit <= 0:
            raise ValueError("Limit must be positive")

        try:
            query_vector = self.embedding_model.embed_query(query)
            
            safe_query_vector = self.safe_to_list(query_vector)

            search_result = self.client.query_points(
                collection_name=collection_name,
                query=safe_query_vector,
                limit=limit,
                with_payload=True  
            )

            if hasattr(search_result, 'points'):
                return search_result.points  
            else:
                raise ValueError("Brak punktów w wynikach zapytania.")

        except Exception as e:
            logger.error(f"Błąd podczas wyszukiwania: {e}")
            return None

    def collection_exists(self, collection_name: str) -> bool:
        """Check if collection exists."""
        try:
            self.client.get_collection(collection_name=collection_name)
            return True
        except:
            return False

    def delete_collection(self, collection_name: str) -> bool:
        """Delete a collection."""
        try:
            self.client.delete_collection(collection_name=collection_name)
            logger.info(f"Kolekcja '{collection_name}' została usunięta.")
            return True
        except Exception as e:
            logger.error(f"Błąd podczas usuwania kolekcji: {e}")
            return False
