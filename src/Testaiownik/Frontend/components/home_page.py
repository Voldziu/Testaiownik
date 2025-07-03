# components/home_page.py

import streamlit as st
from datetime import datetime
from utils.session_manager import reset_quiz_session, set_home_page_shown, get_user_id
from services.api_client import get_api_client
from typing import List, Dict, Any

def render_home_page():
    """Render home page with main options"""
    st.title("🏠 Strona Główna")
    
    st.subheader("Witaj w aplikacji TestAIownik!")
    st.write("Wybierz jedną z poniższych opcji:")

    # Przyciski do przejścia do generowania quizu i dotychczasowych testów
    col1, col2 = st.columns([1, 1])
    
    with col1:
        if st.button("🎯 Utwórz nowy quiz", use_container_width=True):
            reset_quiz_session()  # Resetujemy sesję przed rozpoczęciem nowego quizu
            set_home_page_shown()
            st.session_state["app_phase"] = "quiz_creation"  # Ustawiamy fazę aplikacji na quiz_creation
            st.rerun()

    with col2:
        if st.button("📋 Moje testy", use_container_width=True):
            st.session_state["show_quiz_list"] = True
            st.rerun()

    # Show quiz list if requested
    if st.session_state.get("show_quiz_list", False):
        render_quiz_list()

def render_quiz_list():
    """Render list of user's quizzes"""
    st.divider()
    st.subheader("📋 Moje testy")
    
    # Back button
    if st.button("🔙 Powrót", key="back_to_main"):
        st.session_state["show_quiz_list"] = False
        st.rerun()
    
    # Load quizzes
    with st.spinner("Ładowanie twoich quizów..."):
        quizzes = load_user_quizzes()
    
    if not quizzes:
        st.info("🎯 Nie masz jeszcze żadnych quizów. Utwórz swój pierwszy quiz!")
        return
    
    st.write(f"Znaleziono **{len(quizzes)}** quizów:")
    
    # Display quizzes
    for quiz in quizzes:
        render_quiz_item(quiz)

def load_user_quizzes(limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
    """Load user's quizzes from API"""
    try:
        api_client = get_api_client(get_user_id())
        response = api_client.get_quizzes(limit=limit, offset=offset)
        return response.get('quizzes', [])
    except Exception as e:
        st.error(f"❌ Błąd podczas ładowania quizów: {str(e)}")
        return []

def render_quiz_item(quiz: Dict[str, Any]):
    """Render individual quiz item"""
    quiz_id = quiz.get('quiz_id')
    created_at = quiz.get('created_at')
    status = quiz.get('status')
    document_count = quiz.get('document_count', 0)
    topic_count = quiz.get('topic_count', 0)
    
    # Format creation date
    created_date = "Nieznana data"
    if created_at:
        try:
            if isinstance(created_at, str):
                # Parse ISO format datetime
                dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                created_date = dt.strftime('%d.%m.%Y %H:%M')
            else:
                created_date = created_at.strftime('%d.%m.%Y %H:%M')
        except:
            created_date = str(created_at)
    
    # Status mapping
    status_map = {
        'created': ('🆕', 'Utworzony'),
        'topic_ready': ('📝', 'Tematy gotowe'),
        'quiz_active': ('🎯', 'Aktywny'),
        'completed': ('✅', 'Ukończony'),
        'failed': ('❌', 'Błąd')
    }
    
    status_icon, status_text = status_map.get(status, ('❓', status))
    
    # Create expandable container for each quiz
    with st.expander(f"{status_icon} Quiz z {created_date}", expanded=False):
        # Quiz details
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.write(f"**Status:** {status_text}")
            st.write(f"**Dokumenty:** {document_count}")
        
        with col2:
            st.write(f"**Tematy:** {topic_count}")
            st.write(f"**ID:** `{quiz_id[:8]}...`")
        
        with col3:
            st.write(f"**Utworzono:** {created_date}")
        
        # Action buttons
        st.write("**Akcje:**")
        action_col1, action_col2, action_col3 = st.columns(3)
        
        with action_col1:
            if status in ['topic_ready', 'quiz_active']:
                if st.button("▶️ Kontynuuj", key=f"continue_{quiz_id}", use_container_width=True):
                    continue_quiz(quiz_id, status)
            elif status == 'completed':
                if st.button("🔄 Powtórz", key=f"retry_{quiz_id}", use_container_width=True):
                    retry_quiz(quiz_id)
            elif status == 'created':
                if st.button("⚙️ Skonfiguruj", key=f"configure_{quiz_id}", use_container_width=True):
                    configure_quiz(quiz_id)
        
        with action_col2:
            if st.button("📊 Statystyki", key=f"stats_{quiz_id}", use_container_width=True):
                show_quiz_stats(quiz_id)
        
        with action_col3:
            if st.button("🗑️ Usuń", key=f"delete_{quiz_id}", use_container_width=True):
                delete_quiz(quiz_id)

def continue_quiz(quiz_id: str, status: str):
    """Continue an existing quiz"""
    try:
        # Set quiz ID in session
        st.session_state["quiz_id"] = quiz_id
        
        # Clear any existing quiz state
        if "quiz_state" in st.session_state:
            del st.session_state["quiz_state"]
        
        # Set appropriate app phase based on status
        if status == 'topic_ready':
            st.session_state["app_phase"] = "topic_confirmation"
        elif status == 'quiz_active':
            st.session_state["app_phase"] = "quiz_questions"
        
        # Hide quiz list
        st.session_state["show_quiz_list"] = False
        
        st.success(f"🎯 Kontynuujesz quiz {quiz_id[:8]}...")
        st.rerun()
        
    except Exception as e:
        st.error(f"❌ Błąd podczas kontynuowania quizu: {str(e)}")

def retry_quiz(quiz_id: str):
    """Retry a completed quiz"""
    try:
        # Set quiz ID in session
        st.session_state["quiz_id"] = quiz_id
        
        # Clear quiz state
        if "quiz_state" in st.session_state:
            del st.session_state["quiz_state"]
        
        # Try to restart the quiz with soft reset
        api_client = get_api_client(get_user_id())
        response = api_client.restart_quiz(quiz_id, hard=False)
        
        # Set app phase to quiz questions
        st.session_state["app_phase"] = "quiz_questions"
        
        # Hide quiz list
        st.session_state["show_quiz_list"] = False
        
        st.success(f"🔄 Restartujesz quiz {quiz_id[:8]}...")
        st.rerun()
        
    except Exception as e:
        st.error(f"❌ Błąd podczas restartowania quizu: {str(e)}")

def configure_quiz(quiz_id: str):
    """Configure a created quiz"""
    try:
        # Set quiz ID in session
        st.session_state["quiz_id"] = quiz_id
        
        # Go to topic confirmation phase
        st.session_state["app_phase"] = "topic_confirmation"
        
        # Hide quiz list
        st.session_state["show_quiz_list"] = False
        
        st.success(f"⚙️ Konfigurujesz quiz {quiz_id[:8]}...")
        st.rerun()
        
    except Exception as e:
        st.error(f"❌ Błąd podczas konfigurowania quizu: {str(e)}")

def show_quiz_stats(quiz_id: str):
    """Show quiz statistics"""
    try:
        with st.spinner("Ładowanie statystyk..."):
            api_client = get_api_client(get_user_id())
            # Try to get quiz progress for statistics
            stats = api_client.get_quiz_progress(quiz_id)
            
            if stats and 'progress' in stats:
                progress = stats['progress']
                
                st.subheader(f"📊 Statystyki quizu {quiz_id[:8]}")
                
                # Display stats in columns
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Pytania w puli", progress.get('total_questions_in_pool', 0))
                    st.metric("Unikalne pytania", progress.get('total_unique_questions', 0))
                
                with col2:
                    st.metric("Odpowiedzi udzielone", progress.get('unique_answered', 0))
                    st.metric("Poprawne odpowiedzi", progress.get('unique_correct', 0))
                
                with col3:
                    answered = progress.get('unique_answered', 0)
                    if answered > 0:
                        success_rate = (progress.get('unique_correct', 0) / answered) * 100
                        st.metric("Skuteczność", f"{success_rate:.1f}%")
                    else:
                        st.metric("Skuteczność", "0%")
                        
                    total_attempts = progress.get('total_attemps', 0)  # Note: API typo
                    st.metric("Łączne próby", total_attempts)
                
                # Additional stats if available
                if progress.get('time_elapsed_seconds'):
                    elapsed = progress.get('time_elapsed_seconds', 0)
                    minutes = int(elapsed // 60)
                    seconds = int(elapsed % 60)
                    st.write(f"**Czas spędzony:** {minutes}min {seconds}s")
                    
                if progress.get('average_time_per_attempt'):
                    avg_time = progress.get('average_time_per_attempt', 0)
                    st.write(f"**Średni czas na próbę:** {avg_time:.1f}s")
                    
            else:
                st.info("📊 Brak dostępnych statystyk dla tego quizu.")
                
    except Exception as e:
        st.error(f"❌ Błąd podczas ładowania statystyk: {str(e)}")

def delete_quiz(quiz_id: str):
    """Delete a quiz with confirmation"""
    # Show confirmation dialog
    st.warning(f"⚠️ Czy na pewno chcesz usunąć quiz {quiz_id[:8]}?")
    st.write("Ta operacja jest nieodwracalna!")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("✅ Tak, usuń", key=f"confirm_delete_{quiz_id}", use_container_width=True):
            try:
                api_client = get_api_client(get_user_id())
                # Note: You'll need to implement delete_quiz method in your API client
                # api_client.delete_quiz(quiz_id)
                st.error("❌ Funkcja usuwania quizu nie jest jeszcze zaimplementowana w API.")
                
            except Exception as e:
                st.error(f"❌ Błąd podczas usuwania quizu: {str(e)}")
    
    with col2:
        if st.button("❌ Anuluj", key=f"cancel_delete_{quiz_id}", use_container_width=True):
            st.rerun()  # Refresh to hide confirmation