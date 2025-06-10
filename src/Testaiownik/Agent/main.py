
from ..RAG import MockRetriever

mr = MockRetriever()
print(mr.retrieve("test query"))