import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct
from AzureModels.models import get_embedding_model
from .pdf_processor import extract_text_from_pdf
from typing import Optional, List
import logging

class QdrantManager:
    def __init__(self, url: str = "http://localhost:6333", vector_size: int = 1536):
        self.client = QdrantClient(url=url)
        self.vector_size = vector_size
        self.embedding_model = get_embedding_model(api_version="2024-12-01-preview")
        self.logger = logging.getLogger(__name__)

    def create_collection(self, collection_name: str, distance_metric: str = "Dot") -> bool:
        """Creates a collection in Qdrant with error handling."""
        if not collection_name:
            raise ValueError("Collection name cannot be empty")
            
        try:
            self.client.get_collection(collection_name=collection_name)
            self.logger.info(f"Kolekcja '{collection_name}' już istnieje.")
            return True
        except Exception:
            try:
                self.logger.info(f"Tworzę nową kolekcję '{collection_name}'...")
                self.client.create_collection(
                    collection_name=collection_name,
                    vectors_config={"size": self.vector_size, "distance": distance_metric}
                )
                self.logger.info(f"Kolekcja '{collection_name}' została utworzona.")
                return True
            except Exception as e:
                self.logger.error(f"Błąd podczas tworzenia kolekcji: {e}")
                return False

    def safe_to_list(self, data):
        """Bezpiecznie konwertuje dane do listy"""
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

    def index_pdf_to_qdrant(self, pdf_path: str, collection_name: str) -> bool:
        """Indexes PDF content into Qdrant with better error handling."""
        try:
            # Extract text from PDF
            text = extract_text_from_pdf(pdf_path)
            if not text:
                self.logger.warning("Nie udało się wyodrębnić tekstu z PDF")
                return False

            # Chunk the text into larger pieces
            chunks = self.chunk_text(text, min_chunk_size=500)  # Adjust chunk size as needed
            if not chunks:
                self.logger.warning("Nie znaleziono fragmentów tekstu do indeksowania")
                return False

            # Encoding chunks to vectors using the embedding model
            vectors = self.embedding_model.embed_documents(chunks)
            
            # Debug: Check the type and length of the first vector
            if vectors:
                self.logger.info(f"Type of first vector: {type(vectors[0])}")
                self.logger.info(f"Length of vectors: {len(vectors)}")
            
            # Create points with better ID management
            points = []
            for i, (chunk, vector) in enumerate(zip(chunks, vectors)):
                # Use safe conversion of vector to list
                safe_vector = self.safe_to_list(vector)
                
                points.append(PointStruct(
                    id=i, 
                    vector=safe_vector, 
                    payload={
                        "text": chunk,
                        "source": pdf_path,
                        "chunk_id": i
                    }
                ))
            
            # Upsert points into Qdrant collection
            self.client.upsert(collection_name=collection_name, points=points)
            self.logger.info(f"Dodano {len(points)} punktów do kolekcji '{collection_name}'.")
            return True
            
        except Exception as e:
            self.logger.error(f"Błąd podczas indeksowania PDF: {e}")
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
            self.logger.error(f"Błąd podczas wyszukiwania: {e}")
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
            self.logger.info(f"Kolekcja '{collection_name}' została usunięta.")
            return True
        except Exception as e:
            self.logger.error(f"Błąd podczas usuwania kolekcji: {e}")
            return False
