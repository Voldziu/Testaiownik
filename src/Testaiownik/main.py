from Agent.runner import TestaiownikRunner

# # This is the main entry point to test the agent topic - generation and feedback loop.
# if __name__ == "__main__":
#     run_agent()

###
# docker run -p 6333:6333 -p 6334:6334 \
#     -v "$(pwd)/qdrant_storage:/qdrant/storage:z" \
#    qdrant/qdrant

import sys

from RAG.qdrant_manager import QdrantManager
from RAG.Retrieval.Retriever import RAGRetriever
from utils import logger


def prepare_test_retriever() -> RAGRetriever:
    docx_path = r"test_files/testdocx.docx"
    pdf_path = r"test_files/testpdf.pdf"
    txt_path = r"test_files/testtxt.txt"
    pptx_path = r"test_files/testpptx.pptx"
    collection_name = "all_documents_collection3"

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
        for i, payload in enumerate(chunks, 1):
            text = payload.get("text", "")
            source = payload.get("source", "Nieznane źródło")

            print(f"\n--- Fragment {i} ---")

            print(text[:200] + "..." if len(text) > 200 else text)
            if "page" in payload:
                print(f"Strona (PDF): {payload['page']}")
            elif "slide" in payload:
                print(f"Slajd (PPTX): {payload['slide']}")
            print(f"Źródło: {source}")

        logger.info("\nTestowanie funkcji search_in_collection...")

        query = "Czym jest krontość?"
        search_result = qdrant_manager.search_in_collection(
            query, collection_name, limit=3
        )

        if search_result:
            logger.info("Wyniki wyszukiwania:")

            for i, result in enumerate(search_result, 1):
                print(f"\n--- Wynik {i} ---")
                print(result.payload["text"])
        else:
            logger.error("Brak wyników wyszukiwania.")

        return rag_retriever

    except Exception as e:
        logger.error(f"Błąd w main(): {e}")
        raise


def prepare_retriever(*paths, collection_name: str = "TEST_COLLECTION") -> RAGRetriever:
    """Path needs to be in src/Testaiownik/{path}"""
    # Collection_name is keyword only!

    try:
        logger.info("Initialize QdrantManager...")
        qdrant_manager = QdrantManager()

        logger.info(f"Creating collection  '{collection_name}'...")
        qdrant_manager.create_collection(collection_name)

        # Index all provided paths
        for path in paths:
            logger.info(f"Indexing file: {path}")
            success = qdrant_manager.index_file_to_qdrant(path, collection_name)

            if not success:
                logger.error(f"Can't index file: {path}")
                return

        logger.info("Initialize RAGRetriever...")
        rag_retriever = RAGRetriever(collection_name, qdrant_manager)

        chunk_count = rag_retriever.get_chunk_count()
        logger.info(f"Number of chunks in collection: {chunk_count}")

        logger.info("Fetching document chunks..")
        chunks = rag_retriever.get_all_chunks()

        logger.debug("\n=== Found document chunks ===")
        for i, payload in enumerate(chunks, 1):
            text = payload.get("text", "")
            source = payload.get("source", "Nieznane źródło")

            logger.debug(f"\n--- Fragment {i} ---")
            # logger.debug(text[:100] + "..." if len(text) > 100 else text)
            logger.debug(text)
            if "page" in payload:
                logger.debug(f"Page (PDF): {payload['page']}")
            elif "slide" in payload:
                logger.debug(f"Slide (PPTX): {payload['slide']}")
            logger.debug(f"Source: {source}")

        return rag_retriever

    except Exception as e:
        logger.error(f"Błąd w main(): {e}")
        raise


def main():
    """Main entry point with command line arguments"""

    # Simple command line argument parsing
    import argparse

    parser = argparse.ArgumentParser(description="TESTAIOWNIK - AI Learning Assistant")
    parser.add_argument(
        "--topics", type=int, default=10, help="Desired number of topics (default: 10)"
    )
    parser.add_argument(
        "--questions", type=int, default=100, help="Total quiz questions (default: 20)"
    )
    parser.add_argument(
        "--difficulty",
        choices=["easy", "medium", "hard", "very-hard"],
        default="very-hard",
        help="Quiz difficulty",
    )
    parser.add_argument(
        "--user-questions", nargs="*", help="Additional questions to include in quiz"
    )

    args = parser.parse_args()

    # Prepare retriever and docs
    logger.info("Preparing retriever and indexing documents...")

    retriever = prepare_retriever(
        collection_name="collection_zacho"
    )  # Pass paths for testing!

    # retriever = prepare_retriever(
    #     "test_files_big/zacho-mini.pdf", collection_name="collection_zacho_mini"
    # )  # use existing collection
    # logger.info("Retriever prepared successfully.")

    # Create and run
    runner = TestaiownikRunner(retriever)

    try:
        runner.run_complete_workflow(
            desired_topic_count=args.topics,
            total_questions=args.questions,
            difficulty=args.difficulty,
            user_questions=args.user_questions,
        )
    except KeyboardInterrupt:
        print("\n\n Session interrupted by user. Goodbye!")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        print(f"\n❌ An error occurred: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
