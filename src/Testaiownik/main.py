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
    pdf_path = r"C:\Users\marci\OneDrive\Pulpit\accenture\testaiownik\test_files\testpdf.pdf"
    txt_path = r"C:\Users\marci\OneDrive\Pulpit\accenture\testaiownik\test_files\testtxt.txt"
    pptx_path = r"C:\Users\marci\OneDrive\Pulpit\accenture\testaiownik\test_files\testpptx.pptx"
    docx_path = r"C:\Users\marci\OneDrive\Pulpit\accenture\testaiownik\test_files\testdocx.docx"
    collection_name = "all_documents_collection2"

    try:
        logger.info("Inicjalizacja QdrantManager...")
        qdrant_manager = QdrantManager()
        
        logger.info(f"Tworzenie kolekcji '{collection_name}'...")
        qdrant_manager.create_collection(collection_name)

        logger.info(f"Indeksowanie pliku txt: {txt_path}")
        success = qdrant_manager.index_file_to_qdrant(txt_path, collection_name)
        
        if not success:
            logger.error("Nie udało się zindeksować pliku txt")
            return
        
        logger.info(f"Indeksowanie pliku PDF: {pdf_path}")
        success = qdrant_manager.index_file_to_qdrant(pdf_path, collection_name)
        
        if not success:
            logger.error("Nie udało się zindeksować pliku pdf")
            return
        

        logger.info(f"Indeksowanie pliku pptx: {pptx_path}")
        success = qdrant_manager.index_file_to_qdrant(pptx_path, collection_name)
        
        if not success:
            logger.error("Nie udało się zindeksować pliku pptx")
            return
        
        logger.info(f"Indeksowanie pliku docx: {docx_path}")
        success = qdrant_manager.index_file_to_qdrant(docx_path, collection_name)
        
        if not success:
            logger.error("Nie udało się zindeksować pliku docx")
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


        logger.info("\nTestowanie funkcji search_in_collection...")

        query = "Czym jest krontość?"
        search_result = qdrant_manager.search_in_collection(query, collection_name, limit=3)

        if search_result:
            logger.info("Wyniki wyszukiwania:")
           
            for i, result in enumerate(search_result, 1):  
                print(f"\n--- Wynik {i} ---")
                print(result.payload['text'])  
        else:
            logger.error("Brak wyników wyszukiwania.")


    except Exception as e:
        logger.error(f"Błąd w main(): {e}")
        raise

if __name__ == "__main__":
    main()