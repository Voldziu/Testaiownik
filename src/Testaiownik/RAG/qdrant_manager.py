import os
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct
from AzureModels.models import get_embedding_model
from .file_processor import (
    extract_text_from_docx,
    extract_text_from_pdf,
    extract_text_from_txt,
    extract_text_from_pptx,
)
from typing import Optional, List
from utils.logger import logger
import time


class QdrantManager:

    def __init__(
        self,
        url: str = os.getenv("QDRANT_URL", "localhost:6333"),  # From dockercompose
        vector_size: int = 1536,
        timeout: int = None,
    ):
        # Remove timeout completely or set very high value
        self.client = QdrantClient(url=url, timeout=timeout)
        self.vector_size = vector_size
        self.embedding_model = get_embedding_model(api_version="2024-12-01-preview")
        self.last_used_id = 0

    def create_collection(
        self, collection_name: str, distance_metric: str = "Dot"
    ) -> bool:
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
                    vectors_config={
                        "size": self.vector_size,
                        "distance": distance_metric,
                    },
                )
                logger.info(f"Kolekcja '{collection_name}' została utworzona.")
                return True
            except Exception as e:
                logger.error(f"Błąd podczas tworzenia kolekcji: {e}")
                return False

    def safe_to_list(self, data):
        """Convert safely to list"""
        if hasattr(data, "tolist"):
            return data.tolist()
        elif isinstance(data, list):
            return data
        else:
            return list(data)

    def chunk_text(self, text: str, min_chunk_size: int = 500) -> List[str]:
        """Chunks the text into larger fragments of at least `min_chunk_size` characters."""
        if not text:
            return [""]
        chunks = []
        start_idx = 0

        while start_idx < len(text):
            # Find the next reasonable split point (either by space or the `min_chunk_size`)
            end_idx = start_idx + min_chunk_size
            if end_idx >= len(text):
                chunks.append(text[start_idx:])
                break

            # Find the last space within the chunk to avoid cutting off in the middle of a word
            if text[end_idx] != " ":
                space_idx = text.rfind(" ", start_idx, end_idx)
                if space_idx != -1:
                    end_idx = space_idx

            # Append the chunk
            chunks.append(text[start_idx:end_idx].strip())
            start_idx = end_idx

        return chunks

    def process_file(self, file_path: str) -> List[tuple[str, dict]]:
        """Returns extracted text with optional metadata."""
        if file_path.endswith(".pdf"):
            return [
                (text, {"page": page})
                for text, page in extract_text_from_pdf(file_path)
            ]
        elif file_path.endswith(".pptx"):
            return [
                (text, {"slide": slide})
                for text, slide in extract_text_from_pptx(file_path)
            ]
        elif file_path.endswith(".txt"):
            return [(extract_text_from_txt(file_path), {})]
        elif file_path.endswith(".docx"):
            return [(extract_text_from_docx(file_path), {})]
        else:
            logger.error(f"Nieobsługiwany typ pliku: {file_path}")
            return []

    def index_file_to_qdrant(
        self, file_path: str, collection_name: str, batch_size: int = 50
    ) -> bool:
        """Indexes content from a file into Qdrant with batch processing for large files."""
        try:
            logger.info(f"Starting indexing of {file_path}")

            # Process the file and get list of (text, metadata) tuples
            text_sections = self.process_file(file_path)
            if not text_sections:
                logger.warning(f"Nie udało się wyodrębnić tekstu z pliku: {file_path}")
                return False

            # Collect all chunks first to estimate total work
            all_chunks_data = []
            for section_text, metadata in text_sections:
                chunks = self.chunk_text(section_text, min_chunk_size=500)
                for i, chunk in enumerate(chunks):
                    all_chunks_data.append((chunk, metadata, i))

            total_chunks = len(all_chunks_data)
            logger.info(f"Total chunks to process: {total_chunks}")

            if total_chunks == 0:
                logger.warning("No chunks to process")
                return False

            # Process in batches
            processed_chunks = 0
            total_batches = (total_chunks + batch_size - 1) // batch_size

            for batch_idx in range(0, total_chunks, batch_size):
                batch_chunks_data = all_chunks_data[batch_idx : batch_idx + batch_size]
                batch_num = (batch_idx // batch_size) + 1

                logger.info(
                    f"Processing batch {batch_num}/{total_batches} ({len(batch_chunks_data)} chunks)"
                )

                # Extract just the text for embedding
                batch_texts = [chunk_data[0] for chunk_data in batch_chunks_data]

                # Generate embeddings for this batch
                start_time = time.time()
                try:
                    vectors = self.embedding_model.embed_documents(batch_texts)
                    embedding_time = time.time() - start_time
                    logger.info(
                        f"Generated embeddings for batch {batch_num} in {embedding_time:.2f}s"
                    )
                except Exception as e:
                    logger.error(
                        f"Error generating embeddings for batch {batch_num}: {e}"
                    )
                    continue

                # Create points for this batch
                points = []
                for (chunk, metadata, chunk_id), vector in zip(
                    batch_chunks_data, vectors
                ):
                    self.last_used_id += 1

                    payload = {"text": chunk, "source": file_path, "chunk_id": chunk_id}
                    payload.update(metadata)

                    points.append(
                        PointStruct(
                            id=self.last_used_id,
                            vector=self.safe_to_list(vector),
                            payload=payload,
                        )
                    )

                # Upsert this batch
                start_time = time.time()
                try:
                    self.client.upsert(collection_name=collection_name, points=points)
                    upsert_time = time.time() - start_time
                    processed_chunks += len(points)

                    logger.info(
                        f"Batch {batch_num} upserted in {upsert_time:.2f}s. "
                        f"Progress: {processed_chunks}/{total_chunks} chunks "
                        f"({processed_chunks/total_chunks*100:.1f}%)"
                    )
                except Exception as e:
                    logger.error(f"Error upserting batch {batch_num}: {e}")
                    continue

                # Small delay to prevent overwhelming the system
                time.sleep(0.1)

            logger.info(
                f"Successfully indexed {processed_chunks} chunks from {file_path}"
            )
            return processed_chunks > 0

        except Exception as e:
            logger.error(f"Błąd podczas indeksowania pliku: {e}")
            return False

    def search_in_collection(
        self,
        query: str,
        collection_name: str,
        limit: int = 3,
        score_threshold: float = 0.6,
    ) -> Optional[List[PointStruct]]:
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
                with_payload=True,
                score_threshold=score_threshold,
            )

            if hasattr(search_result, "points"):
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
