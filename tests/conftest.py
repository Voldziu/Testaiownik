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


# Service-specific fixtures
@pytest.fixture
def mock_db_session():
    """Mock database session"""
    return Mock()


@pytest.fixture
def mock_qdrant_manager():
    """Mock QdrantManager"""
    manager = Mock()
    manager.create_collection.return_value = None
    manager.collection_exists.return_value = False
    manager.index_file_to_qdrant.return_value = True
    manager.get_collection_info.return_value = {"name": "test_collection", "size": 100}
    return manager


@pytest.fixture
def temp_upload_dir():
    """Create temporary upload directory"""
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def mock_document():
    """Mock document object"""
    doc = Mock()
    doc.doc_id = "doc_123"
    doc.filename = "test.pdf"
    doc.file_path = "/path/to/test.pdf"
    doc.size_bytes = 1024
    doc.file_type = "pdf"
    doc.uploaded_at = "2025-01-15T10:00:00Z"
    doc.indexed = False
    return doc


@pytest.fixture
def mock_quiz():
    """Mock quiz object"""
    quiz = Mock()
    quiz.quiz_id = "quiz_456"
    quiz.status = "documents_indexed"
    quiz.collection_name = "quiz_456_collection"
    quiz.suggested_topics = [
        {"topic": "Algorithms", "weight": 0.4},
        {"topic": "Data Structures", "weight": 0.3},
    ]
    quiz.confirmed_topics = None
    quiz.langgraph_topic_state = None
    quiz.langgraph_quiz_state = None
    return quiz


# Pytest configuration for async support
def pytest_configure(config):
    """Configure pytest markers"""
    config.addinivalue_line("markers", "asyncio: async test support")


# Environment setup
@pytest.fixture(autouse=True)
def setup_test_env():
    """Set up test environment variables"""
    import os

    test_env = {
        "ENVIRONMENT": "test",
        "DATABASE_URL": "sqlite:///:memory:",
        "UPLOAD_DIR": "/tmp/test_uploads",
        "QDRANT_URL": "http://localhost:6333",
    }

    for key, value in test_env.items():
        if key not in os.environ:
            os.environ[key] = value

    yield
