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

def reset_quiz_session():
    """Reset all quiz-related session state"""
    keys_to_remove = [
        SessionKeys.QUIZ_ID,
        SessionKeys.UPLOADED,
        SessionKeys.INDEXING_STARTED,
        SessionKeys.TOPICS_GENERATED,
        SessionKeys.EDITING_TOPIC
    ]
    
    for key in keys_to_remove:
        if key in st.session_state:
            del st.session_state[key]

def get_app_phase() -> str:
    """Get current application phase"""
    if not is_quiz_created():
        return "quiz_creation"
    elif not is_files_uploaded():
        return "file_upload"
    elif not is_indexing_started():
        return "indexing_setup"
    elif not are_topics_generated():
        return "topic_generation"
    else:
        return "topic_management"