# main.py

import streamlit as st
from components.questions_manager import render_questions_manager
from components.quiz_manager import render_quiz_questions
from components.home_page import render_home_page
from utils.session_manager import get_app_phase, init_user_id
from components.quiz_creation import render_quiz_creation
from components.file_upload import render_file_upload
from components.topics_manager import render_topics_manager


def main():
    """Main application flow"""
    # Initialize user session
    init_user_id()

    # Get current application phase
    phase = get_app_phase()

    # Route to appropriate component based on phase

    if phase == "homepage":
        render_home_page()

    elif phase == "quiz_creation":
        render_quiz_creation()

    elif phase == "file_upload":
        render_file_upload()

    elif phase == "indexing_setup":
        render_file_upload()  # Same component handles indexing

    elif phase in ["topic_generation", "topic_management"]:
        render_topics_manager()

    elif phase == "question_generation":
        render_questions_manager()

    elif phase == "test":
        render_quiz_questions()

    else:
        st.error("Nieznany stan aplikacji. Spróbuj odświeżyć stronę.")


if __name__ == "__main__":
    main()
