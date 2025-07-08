# utils/session_manager.py

import streamlit as st
import uuid
from config.settings import SessionKeys


def generate_user_id() -> str:
    """Generate a unique user ID"""
    return str(uuid.uuid4())


def init_user_id():
    """Initialize user ID in session state if not exists"""
    if SessionKeys.USER_ID not in st.session_state:
        st.session_state[SessionKeys.USER_ID] = generate_user_id()


def get_user_id() -> str:
    """Get current user ID from session state"""
    init_user_id()
    return st.session_state[SessionKeys.USER_ID]


def get_quiz_id() -> str:
    """Get current quiz ID from session state"""
    return st.session_state.get(SessionKeys.QUIZ_ID)


def set_quiz_id(quiz_id: str):
    """Set quiz ID in session state"""
    st.session_state[SessionKeys.QUIZ_ID] = quiz_id


def is_quiz_created() -> bool:
    """Check if quiz has been created"""
    return SessionKeys.QUIZ_ID in st.session_state


def is_files_uploaded() -> bool:
    """Check if files have been uploaded"""
    return st.session_state.get(SessionKeys.UPLOADED, False)


def set_files_uploaded(status: bool = True):
    """Set files uploaded status"""
    st.session_state[SessionKeys.UPLOADED] = status


def is_indexing_started() -> bool:
    """Check if indexing has been started"""
    return st.session_state.get(SessionKeys.INDEXING_STARTED, False)


def set_indexing_started(status: bool = True):
    """Set indexing started status"""
    st.session_state[SessionKeys.INDEXING_STARTED] = status


def are_topics_generated() -> bool:
    """Check if topics have been generated"""
    return st.session_state.get(SessionKeys.TOPICS_GENERATED, False)


def set_topics_generated(status: bool = True):
    """Set topics generated status"""
    st.session_state[SessionKeys.TOPICS_GENERATED] = status


def get_editing_topic() -> str:
    """Get currently editing topic"""
    return st.session_state.get(SessionKeys.EDITING_TOPIC)


def set_editing_topic(topic_name: str = None):
    """Set currently editing topic"""
    st.session_state[SessionKeys.EDITING_TOPIC] = topic_name


def are_topics_confirmed() -> bool:
    """Check if topics have been confirmed"""
    return st.session_state.get(SessionKeys.TOPICS_CONFIRMED, False)


def set_topics_confirmed(status: bool = True):
    """Set topics confirmed status"""
    st.session_state[SessionKeys.TOPICS_CONFIRMED] = status


def are_questions_generated() -> bool:
    """Check if questions have been generated"""
    return st.session_state.get(SessionKeys.QUESTIONS_GENERATED, False)


def set_questions_generated(status: bool = True):
    """Set questions generation status"""
    st.session_state[SessionKeys.QUESTIONS_GENERATED] = status


def is_home_page_shown() -> bool:
    """Check if home page has been shown"""
    return st.session_state.get(SessionKeys.HOME_PAGE_SHOWN, False)


def set_home_page_shown(status: bool = True):
    """Set the home page shown status"""
    st.session_state[SessionKeys.HOME_PAGE_SHOWN] = status


def reset_quiz_session():
    """Reset all quiz-related session state"""
    keys_to_remove = [
        SessionKeys.QUIZ_ID,
        SessionKeys.UPLOADED,
        SessionKeys.INDEXING_STARTED,
        SessionKeys.TOPICS_GENERATED,
        SessionKeys.EDITING_TOPIC,
        SessionKeys.TOPICS_CONFIRMED,
        SessionKeys.QUESTIONS_GENERATED,
    ]

    for key in keys_to_remove:
        if key in st.session_state:
            del st.session_state[key]


def get_app_phase() -> str:
    """Get current application phase"""

    # Check if explicitly set to homepage
    if st.session_state.get("app_phase") == "homepage":
        return "homepage"

    # Check normal flow
    if not is_home_page_shown():
        return "homepage"
    elif not is_quiz_created():
        return "quiz_creation"
    elif not is_files_uploaded():
        return "file_upload"
    elif not is_indexing_started():
        return "indexing_setup"
    elif not are_topics_generated():
        return "topic_generation"
    elif not are_topics_confirmed():
        return "topic_management"
    elif not are_questions_generated():
        return "question_generation"
    else:
        return "test"


# Dodaj tę funkcję do session_manager.py
def set_session_flags_for_status(status: str):
    """Set appropriate session flags based on quiz status"""
    
    # Zawsze ustawiamy home_page_shown na True, bo przecież jesteśmy w aplikacji
    set_home_page_shown(True)
    
    # Set flags based on status progression
    if status in ['documents_uploaded', 'documents_indexed', 'topic_analysis', 
                  'topic_feedback', 'topic_ready', 'quiz_active', 'quiz_completed']:
        set_files_uploaded(True)
    
    if status in ['documents_indexed', 'topic_analysis', 'topic_feedback', 
                  'topic_ready', 'quiz_active', 'quiz_completed']:
        set_indexing_started(True)
    
    if status in ['topic_analysis', 'topic_feedback', 'topic_ready', 
                  'quiz_active', 'quiz_completed']:
        set_topics_generated(True)
    
    if status in ['topic_ready', 'quiz_active', 'quiz_completed']:
        set_topics_confirmed(True)
    
    if status in ['quiz_active', 'quiz_completed']:
        set_questions_generated(True)
