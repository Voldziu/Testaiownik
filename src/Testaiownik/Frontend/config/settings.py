# config/settings.py
import os

# Backend configuration
BASE_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

# File upload settings
ALLOWED_FILE_TYPES = ["pdf", "docx", "txt", "pptx"]
MAX_FILE_SIZE_MB = 100

# Quiz settings
DEFAULT_TOPIC_COUNT = 25
MIN_TOPIC_COUNT = 1
MAX_TOPIC_COUNT = 50

# Topic weight settings
MIN_TOPIC_WEIGHT = 0.01
MAX_TOPIC_WEIGHT = 1.0
DEFAULT_TOPIC_WEIGHT = 0.1


# API Headers template
def get_api_headers(user_id: str) -> dict:
    """Generate standard API headers with user authentication"""
    return {
        "X-User-ID": user_id,
        "Authorization": f"Bearer {user_id}",
        "User-ID": user_id,
    }


# Session state keys
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
