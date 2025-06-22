# tests/conftest.py
import pytest
import sys
from pathlib import Path
from unittest.mock import Mock
from dotenv import load_dotenv

# Add src to path for imports
test_dir = Path(__file__).parent
src_dir = test_dir.parent / "src"
sys.path.insert(0, str(src_dir))

# Also add the Testaiownik package to path
testaiownik_dir = src_dir / "Testaiownik"
sys.path.insert(0, str(testaiownik_dir))

# Load test environment
load_dotenv(test_dir.parent / ".env.test")


# Agent fixtures
@pytest.fixture
def mock_llm():
    """Mock LLM for testing"""
    llm = Mock()
    llm.invoke.return_value = Mock()
    llm.with_structured_output.return_value = llm
    return llm


@pytest.fixture
def real_llm():
    """Real LLM for integration tests"""
    from src.Testaiownik.AzureModels import get_llm

    return get_llm(temperature=0.1, max_tokens=500)


@pytest.fixture
def sample_weighted_topics():
    """Sample WeightedTopic objects for testing"""

    return [
        {"topic": "Algorithms", "weight": 0.4},
        {"topic": "Data Structures", "weight": 0.3},
        {"topic": "Complexity Analysis", "weight": 0.3},
    ]


@pytest.fixture
def mock_retriever():
    """Mock DocumentRetriever for testing"""
    from src.Testaiownik.RAG.Retrieval import DocumentRetriever

    retriever = Mock(spec=DocumentRetriever)

    # Default sample chunks
    sample_chunks = [
        {
            "text": "Algorithms are step-by-step procedures for solving computational problems.",
            "source": "algorithms.pdf",
        },
        {
            "text": "Data structures organize and store data efficiently in computer memory.",
            "source": "data_structures.pdf",
        },
        {
            "text": "Time complexity analysis helps measure algorithm efficiency using Big O notation.",
            "source": "complexity.pdf",
        },
    ]

    retriever.get_all_chunks.return_value = sample_chunks
    retriever.get_chunk_count.return_value = len(sample_chunks)
    retriever.search_in_collection.return_value = [
        Mock(payload={"text": chunk["text"]}) for chunk in sample_chunks
    ]

    return retriever


@pytest.fixture
def agent_state_minimal():
    """Minimal AgentState for testing"""
    from src.Testaiownik.Agent.TopicSelection.state import AgentState

    state: AgentState = {
        "suggested_topics": [],
        "rejected_topics": [],
        "confirmed_topics": [],
        "subtopics": {},
        "user_input": None,
        "feedback_request": None,
        "conversation_history": [],
        "next_node": "",
        "messages": [],
        "desired_topic_count": 10,
    }
    return state


@pytest.fixture
def agent_state_with_topics(sample_weighted_topics):
    """AgentState with sample topics"""
    from src.Testaiownik.Agent.TopicSelection.state import AgentState

    state: AgentState = {
        "suggested_topics": sample_weighted_topics,
        "rejected_topics": [],
        "confirmed_topics": [],
        "subtopics": {},
        "user_input": None,
        "feedback_request": None,
        "conversation_history": [],
        "next_node": "request_feedback",
        "messages": ["Analysis complete"],
        "desired_topic_count": 3,
    }
    return state


# Quiz fixtures
@pytest.fixture
def quiz_configuration(sample_weighted_topics):
    """Sample QuizConfiguration for testing"""
    from src.Testaiownik.Agent.Quiz.models import QuizConfiguration

    return QuizConfiguration(
        topics=sample_weighted_topics,
        total_questions=10,
        difficulty="medium",
        batch_size=3,
        user_questions=["What is recursion?"],
    )


@pytest.fixture
def sample_question():
    """Sample Question for testing"""
    from src.Testaiownik.Agent.Quiz.models import Question, QuestionChoice

    return Question(
        topic="Algorithms",
        question_text="What is the time complexity of QuickSort in the average case?",
        choices=[
            QuestionChoice(text="O(n)", is_correct=False),
            QuestionChoice(text="O(n log n)", is_correct=True),
            QuestionChoice(text="O(n²)", is_correct=False),
            QuestionChoice(text="O(log n)", is_correct=False),
        ],
        explanation="QuickSort has O(n log n) average case time complexity",
        difficulty="medium",
    )


@pytest.fixture
def quiz_session_basic(sample_weighted_topics):
    """Basic QuizSession for testing"""
    from src.Testaiownik.Agent.Quiz.models import QuizSession

    return QuizSession(
        topics=sample_weighted_topics,
        total_questions=10,
        questions_per_topic={
            "Algorithms": 4,
            "Data Structures": 3,
            "Complexity Analysis": 3,
        },
        difficulty="medium",
    )


@pytest.fixture
def quiz_state_minimal(quiz_configuration):
    """Minimal QuizState for testing"""
    from src.Testaiownik.Agent.Quiz.state import create_initial_quiz_state

    return create_initial_quiz_state(
        confirmed_topics=quiz_configuration.topics,
        total_questions=5,
        difficulty="easy",
    )


# RAG fixtures
@pytest.fixture
def mock_embedding_model():
    """Mock embedding model"""
    model = Mock()
    model.embed_documents.return_value = [[0.1, 0.2, 0.3] * 512]
    model.embed_query.return_value = [0.1, 0.2, 0.3] * 512
    return model


@pytest.fixture
def mock_qdrant_client():
    """Mock Qdrant client"""
    client = Mock()
    client.get_collection.return_value = Mock()
    client.create_collection.return_value = None
    client.upsert.return_value = None

    # Mock scroll response
    mock_point = Mock()
    mock_point.payload = {"text": "sample text", "source": "test.pdf"}
    client.scroll.return_value = ([mock_point], None)

    # Mock count response
    mock_count_result = Mock()
    mock_count_result.count = 10
    client.count.return_value = mock_count_result

    return client


@pytest.fixture
def mock_qdrant_manager(mock_qdrant_client, mock_embedding_model):
    """Mock QdrantManager with all dependencies"""
    from src.Testaiownik.RAG.qdrant_manager import QdrantManager

    with (
        pytest.mock.patch(
            "RAG.qdrant_manager.QdrantClient", return_value=mock_qdrant_client
        ),
        pytest.mock.patch(
            "RAG.qdrant_manager.get_embedding_model", return_value=mock_embedding_model
        ),
    ):
        manager = QdrantManager()
        manager.client = mock_qdrant_client
        manager.embedding_model = mock_embedding_model
        return manager


# Integration test fixtures
@pytest.fixture
def testaiownik_runner(mock_retriever):
    """TestaiownikRunner for integration testing"""
    from src.Testaiownik.Agent.runner import TestaiownikRunner

    return TestaiownikRunner(mock_retriever)


# Test data fixtures
@pytest.fixture
def sample_conversation_history():
    """Sample conversation history for testing"""
    return [
        {
            "suggested_topics": [
                {"topic": "Sorting Algorithms", "weight": 0.6},
                {"topic": "Search Algorithms", "weight": 0.4},
            ],
            "user_feedback": "Add more advanced topics",
        },
        {
            "suggested_topics": [
                {"topic": "Advanced Sorting (QuickSort, MergeSort)", "weight": 0.4},
                {"topic": "Tree Traversal Algorithms", "weight": 0.3},
                {"topic": "Graph Search Algorithms", "weight": 0.3},
            ],
            "user_feedback": "These look good, I accept",
        },
    ]


@pytest.fixture
def temp_test_file():
    """Create temporary test file"""
    import tempfile
    import os

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as f:
        f.write("Test content for file processing")
        temp_path = f.name

    yield temp_path

    # Cleanup
    try:
        os.unlink(temp_path)
    except OSError:
        pass


# Pytest configuration
def pytest_configure(config):
    """Configure pytest markers"""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test (may be slower)"
    )
    config.addinivalue_line("markers", "unit: mark test as unit test (fast, isolated)")
    config.addinivalue_line(
        "markers", "requires_llm: mark test as requiring real LLM (uses API calls)"
    )


def pytest_collection_modifyitems(config, items):
    """Auto-mark tests based on their location"""
    for item in items:
        # Mark integration tests
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)

        # Mark tests that use real_llm fixture
        if "real_llm" in getattr(item, "fixturenames", []):
            item.add_marker(pytest.mark.requires_llm)


# Cleanup fixtures
@pytest.fixture(autouse=True)
def cleanup_temp_files():
    """Automatically cleanup temporary files after tests"""
    yield
    # Any cleanup code here would run after each test
    pass
