from abc import ABC, abstractmethod
from typing import Iterator


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


# MockRetriever is a mock implementation of DocumentRetriever for testing purposes.
class MockRetriever(DocumentRetriever):
    def get_all_chunks(self) -> Iterator[str]:
        chunks = [
            "Algorytmy sortowania to fundamentalne narzędzia w informatyce, które pozwalają na uporządkowanie danych według określonych kryteriów. Najważniejsze algorytmy to sortowanie bąbelkowe (bubble sort) o złożoności O(n²), które porównuje sąsiadujące elementy i zamienia je miejscami. Sortowanie przez wstawianie (insertion sort) buduje posortowaną sekwencję element po elemencie, również o złożoności O(n²) w najgorszym przypadku. Sortowanie przez wybieranie (selection sort) znajduje najmniejszy element i umieszcza go na właściwej pozycji. Bardziej wydajne są algorytmy typu divide-and-conquer jak merge sort o złożoności O(n log n), który dzieli tablicę na połowy i łączy posortowane części. Quick sort to bardzo popularny algorytm o średniej złożoności O(n log n), który wybiera element pivot i partycjonuje tablicę względem niego. Heap sort wykorzystuje strukturę kopca binarnego do sortowania w czasie O(n log n). Counting sort i radix sort to algorytmy liniowe działające w szczególnych przypadkach.",
            "Struktury danych to sposoby organizacji i przechowywania informacji w pamięci komputera, które umożliwiają efektywny dostęp i modyfikację. Podstawowe struktury liniowe obejmują tablice zapewniające stały czas dostępu O(1) do elementów przez indeks, ale o stałym rozmiarze. Listy łączone oferują dynamiczny rozmiar kosztem dostępu sekwencyjnego O(n). Stosy (stack) implementują zasadę LIFO - ostatni wszedł, pierwszy wyszedł, używane w rekursji i parsowaniu wyrażeń. Kolejki (queue) działają według FIFO - pierwszy wszedł, pierwszy wyszedł, stosowane w algorytmach BFS i systemach obsługi zadań. Struktury drzewiaste jak drzewa binarne umożliwiają hierarchiczne przechowywanie danych. Drzewa BST pozwalają na wyszukiwanie w O(log n). Kopce binarne implementują kolejki priorytetowe. Tablice mieszające (hash tables) oferują średni czas O(1) dla operacji wstawiania, usuwania i wyszukiwania. Grafy reprezentują relacje między obiektami i są kluczowe w algorytmach ścieżek i sieciach.",
            "Złożoność obliczeniowa to miara efektywności algorytmów wyrażana przez czas wykonania i zużycie pamięci w funkcji rozmiaru danych wejściowych. Notacja Big O opisuje górne ograniczenie wzrostu funkcji dla dużych wartości n. Złożoność stała O(1) oznacza czas niezależny od rozmiaru danych, jak dostęp do elementu tablicy. Złożoność logarytmiczna O(log n) występuje w algorytmach dziel i zwyciężaj, np. wyszukiwanie binarne. Złożoność liniowa O(n) charakteryzuje algorytmy przeglądające każdy element raz, jak wyszukiwanie liniowe. Złożoność n log n typowa dla efektywnych algorytmów sortowania jak merge sort i quick sort. Złożoność kwadratowa O(n²) występuje w algorytmach z podwójną pętlą, jak bubble sort. Złożoność sześcienna O(n³) pojawia się w algorytmach mnożenia macierzy. Złożoność wykładnicza O(2ⁿ) charakteryzuje problemy NP-trudne. Oprócz złożoności czasowej istnieje złożoność przestrzenna mierząca zużycie pamięci.",
        ]
        for chunk in chunks:
            yield chunk

    def get_chunk_count(self) -> int:
        return 3


# TODO: Implement RAGRetriever to stream chunks from a vector store
class RAGRetriever(DocumentRetriever):
    def __init__(self, vector_store):
        self.vector_store = vector_store

    def get_all_chunks(self) -> Iterator[str]:
        # TODO: stream all chunks from vector store
        pass

    def get_chunk_count(self) -> int:
        # TODO: get total count
        pass
