from typing import List

class RetrieverInterface:
    def retrieve(self, query: str) -> List[str]:
        pass

class MockRetriever(RetrieverInterface):
    def retrieve(self, query: str) -> List[str]:
        # Mock implementation for testing purposes
        return ["Mocked result 1", "Mocked result 2"]
    
    
class RealRetriever(RetrieverInterface):  
    pass





if __name__ == "__main__":
    mr = MockRetriever()
    print(mr.retrieve("test query"))
    
    # Uncomment the following lines to test RealRetriever when implemented
    # rr = RealRetriever()
    # print(rr.retrieve("test query"))