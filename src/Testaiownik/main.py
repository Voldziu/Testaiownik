# from Agent.runner import run_agent

# # This is the main entry point to test the agent topic - generation and feedback loop.
# if __name__ == "__main__":
#     run_agent()


from RAG.qdrant_manager import QdrantManager
from RAG.Retrieval.Retriever import RAGRetriever
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    pdf_path = r"C:\Users\marci\OneDrive\Pulpit\accenture\testaiownik\testpdf.pdf"
    collection_name = "pdf_documents_collection3"

    try:
        logger.info("Inicjalizacja QdrantManager...")
        qdrant_manager = QdrantManager()
        
        logger.info(f"Tworzenie kolekcji '{collection_name}'...")
        qdrant_manager.create_collection(collection_name)

        logger.info(f"Indeksowanie pliku PDF: {pdf_path}")
        success = qdrant_manager.index_pdf_to_qdrant(pdf_path, collection_name)
        
        if not success:
            logger.error("Nie udało się zindeksować pliku PDF")
            return

        logger.info("Inicjalizacja RAGRetriever...")
        rag_retriever = RAGRetriever(collection_name, qdrant_manager)

        chunk_count = rag_retriever.get_chunk_count()
        logger.info(f"Liczba chunkow w kolekcji: {chunk_count}")

        logger.info("Pobieranie fragmentów dokumentów...")
        chunks = rag_retriever.get_all_chunks()
        
        print("\n=== ZNALEZIONE FRAGMENTY DOKUMENTÓW ===")
        for i, chunk in enumerate(chunks, 1):
            print(f"\n--- Fragment {i} ---")
            print(chunk[:200] + "..." if len(chunk) > 200 else chunk)

    except Exception as e:
        logger.error(f"Błąd w main(): {e}")
        raise

if __name__ == "__main__":
    main()