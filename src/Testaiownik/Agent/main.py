from RAG.Retrieval import MockRetriever
from utils import logger

mr = MockRetriever()
logger.info(mr.get_all_chunks())
