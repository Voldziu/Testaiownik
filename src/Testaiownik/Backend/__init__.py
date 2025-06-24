"""
TESTAIOWNIK Backend Package

FastAPI backend for the AI-powered learning assistant.
Provides REST API endpoints for quiz creation, document management,
topic selection, and quiz execution.

Main Components:
- API Routes: REST endpoints for all functionality
- Services: Business logic layer integrating with Agent workflows
- Database: SQLite/PostgreSQL persistence layer
- Middleware: Session management and authentication
"""

from .main import app
from .api import api_router
from .services import QuizService, DocumentService, TopicService
from .database import init_db, get_db
from .middleware import SessionMiddleware

__version__ = "1.0.0"
__author__ = "TESTAIOWNIK Team"

__all__ = [
    "app",
    "api_router",
    "QuizService",
    "DocumentService",
    "TopicService",
    "init_db",
    "get_db",
    "SessionMiddleware",
]


# Convenience function to get service instances
def get_services():
    """Get instances of all service classes"""
    return {
        "quiz": QuizService(),
        "document": DocumentService(),
        "topic": TopicService(),
    }


# Configuration constants
DEFAULT_CONFIG = {
    "DATABASE_URL": "sqlite:///./testaiownik.db",
    "UPLOAD_DIR": "uploads",
    "QDRANT_URL": "http://localhost:6333",
    "MAX_FILE_SIZE": 100 * 1024 * 1024,  # 100MB
    "SUPPORTED_FILE_TYPES": ["pdf", "docx", "txt", "pptx"],
    "DEFAULT_CHUNK_SIZE": 500,
    "DEFAULT_BATCH_SIZE": 50,
    "DEFAULT_TOPIC_COUNT": 10,
    "DEFAULT_QUIZ_QUESTIONS": 20,
    "SESSION_TIMEOUT_HOURS": 24,
}


# Startup validation
def validate_environment():
    """Validate that required environment variables and services are available"""
    import os
    from utils import logger

    required_env_vars = [
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_API_KEY",
        "CHAT_MODEL_NAME_DEV",
        "EMBEDDING_MODEL_NAME",
    ]

    missing_vars = [var for var in required_env_vars if not os.getenv(var)]

    if missing_vars:
        logger.error(f"Missing required environment variables: {missing_vars}")
        raise EnvironmentError(f"Missing environment variables: {missing_vars}")

    # Test Qdrant connection
    try:
        from RAG.qdrant_manager import QdrantManager

        qdrant = QdrantManager()
        logger.info("✅ Qdrant connection successful")
    except Exception as e:
        logger.error(f"❌ Qdrant connection failed: {e}")
        raise

    # Test Azure OpenAI connection
    try:
        from AzureModels.models import get_llm

        llm = get_llm()
        logger.info("✅ Azure OpenAI connection successful")
    except Exception as e:
        logger.error(f"❌ Azure OpenAI connection failed: {e}")
        raise

    logger.info("🚀 Environment validation completed successfully")


# Development utilities
def create_test_data():
    """Create test data for development (only in development mode)"""
    import os

    if os.getenv("ENVIRONMENT") != "development":
        return

    from .database.crud import create_session, create_quiz
    from utils import logger

    try:
        # Create test session
        test_session_id = "test_session_123"
        create_session(test_session_id)

        # Create test quiz
        test_quiz = create_quiz(test_session_id)

        logger.info(
            f"✅ Test data created: Session {test_session_id}, Quiz {test_quiz.quiz_id}"
        )

    except Exception as e:
        logger.error(f"Failed to create test data: {e}")


# Export main application factory
def create_app(config_overrides=None):
    """Application factory function"""
    from .main import app as fastapi_app

    # Apply any configuration overrides
    if config_overrides:
        for key, value in config_overrides.items():
            setattr(fastapi_app.state, key, value)

    return fastapi_app
