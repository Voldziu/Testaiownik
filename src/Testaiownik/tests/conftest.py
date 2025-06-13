import pytest
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load test environment
test_dir = Path(__file__).parent
parent_dir = test_dir.parent
sys.path.insert(0, str(parent_dir))

# Load .env.test for real API calls
load_dotenv(parent_dir / ".env.test")


@pytest.fixture
def real_llm():
    """Real LLM for integration tests"""
    from src.Testaiownik.AzureModels import get_llm

    return get_llm(temperature=0.1, max_tokens=500)  # Niższe limity dla testów
