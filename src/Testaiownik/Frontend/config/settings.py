# config/settings.py
import os

BASE_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

ALLOWED_FILE_TYPES = ["pdf", "docx", "txt", "pptx"]
MAX_FILE_SIZE_MB = 100

DEFAULT_TOPIC_RATIO = 10
MIN_TOPIC_COUNT = 1
ERROR_MAX_TOPICS = 50

MIN_TOPIC_WEIGHT = 0.01
MAX_TOPIC_WEIGHT = 1.0
DEFAULT_TOPIC_WEIGHT = 0.1

MIN_QUESTIONS = 1
DEFAULT_QUESTION_RATIO = 2
ERROR_MAX_QUESTION = 50

BASIC_TIMEOUT = 1200
SHORT_TIMEOUT = 30


def get_api_headers(user_id: str) -> dict:
    """Generate standard API headers with user authentication"""
    return {
        "X-User-ID": user_id,
        "Authorization": f"Bearer {user_id}",
        "User-ID": user_id,
    }


class SessionKeys:
    USER_ID = "user_id"
    QUIZ_ID = "quiz_id"
    UPLOADED = "uploaded"
    INDEXING_STARTED = "indexing_started"
    TOPICS_GENERATED = "topics_generated"
    EDITING_TOPIC = "editing_topic"
    TOPICS_CONFIRMED = "topics_confirmed"
    QUESTIONS_GENERATED = "questions generated"
    HOME_PAGE_SHOWN = "home_page_shown"
