# components/home_page.py

import streamlit as st
from datetime import datetime
from utils.session_manager import (
    reset_quiz_session,
    set_home_page_shown,
    get_user_id,
)
from services.api_client import get_api_client
from typing import List, Dict, Any


def render_home_page():
    """Render home page with main options"""
    st.title("🏠 Strona Główna")
    st.subheader("Witaj w aplikacji TestAIownik!")

    if st.button("🎯 Utwórz nowy quiz", use_container_width=True):
        reset_quiz_session()  
        set_home_page_shown()
        st.session_state["app_phase"] = (
            "quiz_creation"  
        )
        st.rerun()

    render_quiz_list()


def render_quiz_list():
    """Render list of user's quizzes"""
    st.divider()
    st.subheader("📋 Moje testy")

    with st.spinner("Ładowanie twoich quizów..."):
        quizzes = load_user_quizzes()

    if not quizzes:
        st.info("🎯 Nie masz jeszcze żadnych quizów. Utwórz swój pierwszy quiz!")
        return

    st.write(f"Znaleziono **{len(quizzes)}** quizów:")

    for quiz in quizzes:
        render_quiz_item(quiz)


def load_user_quizzes(limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
    """Load user's quizzes from API"""
    try:
        api_client = get_api_client(get_user_id())
        response = api_client.get_quizzes(limit=limit, offset=offset)
        return response.get("quizzes", [])
    except Exception as e:
        st.error(f"❌ Błąd podczas ładowania quizów: {str(e)}")
        return []


def render_quiz_item(quiz: Dict[str, Any]):
    """Render individual quiz item"""
    quiz_id = quiz.get("quiz_id")
    created_at = quiz.get("created_at")
    status = quiz.get("status")
    document_count = quiz.get("document_count", 0)
    topic_count = quiz.get("topic_count", 0)

    quiz_name = "Quiz"
    if quiz_id and "_" in quiz_id:
        quiz_name = quiz_id.split("_")[0]

    created_date = "Nieznana data"
    if created_at:
        try:
            if isinstance(created_at, str):
                dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                created_date = dt.strftime("%d.%m.%Y %H:%M")
            else:
                created_date = created_at.strftime("%d.%m.%Y %H:%M")
        except:
            created_date = str(created_at)

    status_map = {
        "created": ("🆕", "Utworzony"),
        "documents_uploaded": ("📄", "Dokumenty przesłane"),
        "documents_indexed": ("📊", "Dokumenty zindeksowane"),
        "topic_analysis": ("🔍", "Analiza tematów"),
        "topic_feedback": ("💬", "Feedback tematów"),
        "topic_ready": ("📝", "Tematy gotowe"),
        "quiz_active": ("🎯", "Aktywny"),
        "quiz_completed": ("✅", "Ukończony"),
        "failed": ("❌", "Błąd"),
    }

    status_icon, status_text = status_map.get(status, ("❓", status))

    with st.expander(f"{status_icon} {quiz_name} - {created_date}", expanded=False):

        col1, col2, col3 = st.columns(3)

        with col1:
            st.write(f"**Status:** {status_text}")

        with col2:
            st.write(f"**Tematy:** {topic_count}")

        with col3:
            st.write(f"**Dokumenty:** {document_count}")

        quiz_started = status in ["quiz_active", "quiz_completed"]

        if status == "created":
            if st.button(
                "📄 Prześlij dokumenty",
                key=f"continue_{quiz_id}",
                use_container_width=True,
            ):
                continue_quiz(quiz_id, status)
        elif status == "documents_uploaded":
            if st.button(
                "📊 Indeksuj dokumenty",
                key=f"continue_{quiz_id}",
                use_container_width=True,
            ):
                continue_quiz(quiz_id, status)
        elif status == "documents_indexed":
            if st.button(
                "🔍 Konfiguruj tematy",
                key=f"continue_{quiz_id}",
                use_container_width=True,
            ):
                continue_quiz(quiz_id, status)
        elif status in ["topic_analysis", "topic_feedback"]:
            if st.button(
                "💬 Kontynuuj konfigurację",
                key=f"continue_{quiz_id}",
                use_container_width=True,
            ):
                continue_quiz(quiz_id, status)
        elif status == "topic_ready":
            if st.button(
                "🎯 Konfiguruj pytania",
                key=f"continue_{quiz_id}",
                use_container_width=True,
            ):
                continue_quiz(quiz_id, status)
        elif status == "quiz_active":
            if st.button(
                "▶️ Kontynuuj quiz", key=f"continue_{quiz_id}", use_container_width=True
            ):
                continue_quiz(quiz_id, status)
        elif status == "quiz_completed":
            if st.button(
                "🔄 Powtórz quiz", key=f"retry_{quiz_id}", use_container_width=True
            ):
                retry_quiz(quiz_id)
        elif status == "failed":
            if st.button(
                "🔧 Spróbuj ponownie", key=f"retry_{quiz_id}", use_container_width=True
            ):
                retry_quiz(quiz_id)

        if quiz_started:
            st.markdown("---")  

            stats_state_key = f"stats_visible_{quiz_id}"

            if stats_state_key not in st.session_state:
                st.session_state[stats_state_key] = False

            stats_visible = st.session_state[stats_state_key]

            button_text = (
                "📊 Ukryj statystyki" if stats_visible else "📊 Pokaż statystyki"
            )

            if st.button(
                button_text, key=f"toggle_stats_{quiz_id}", use_container_width=True
            ):
                st.session_state[stats_state_key] = not stats_visible
                st.rerun()  

            if st.session_state[stats_state_key]:
                show_quiz_stats_inline(quiz_id)


def continue_quiz(quiz_id: str, status: str):
    """Continue an existing quiz based on its current status"""
    try:
        st.session_state["quiz_id"] = quiz_id

        if "quiz_state" in st.session_state:
            del st.session_state["quiz_state"]

        from utils.session_manager import set_session_flags_for_status

        set_session_flags_for_status(status)

        if "app_phase" in st.session_state:
            del st.session_state["app_phase"]

        if status == "created":
            st.success(f"📄 Przechodzimy do przesyłania dokumentów...")
        elif status == "documents_uploaded":
            st.success(f"📊 Przechodzimy do indeksowania dokumentów...")
        elif status == "documents_indexed":
            st.success(f"🔍 Przechodzimy do konfiguracji tematów...")
        elif status in ["topic_analysis", "topic_feedback"]:
            st.success(f"💬 Kontynuujemy konfigurację tematów...")
        elif status == "topic_ready":
            st.success(f"🎯 Przechodzimy do konfiguracji pytań...")
        elif status == "quiz_active":
            st.success(f"▶️ Kontynuujesz quiz...")
        else:
            st.error(f"❌ Nieznany status quizu: {status}")
            return

        st.rerun()

    except Exception as e:
        st.error(f"❌ Błąd podczas kontynuowania quizu: {str(e)}")


def retry_quiz(quiz_id: str):
    """Retry a completed or failed quiz"""
    try:
        st.session_state["quiz_id"] = quiz_id

        from utils.session_manager import (
            set_home_page_shown,
            set_files_uploaded,
            set_indexing_started,
            set_topics_generated,
            set_topics_confirmed,
            set_questions_generated,
        )

        set_home_page_shown(True)
        set_files_uploaded(True)
        set_indexing_started(True)
        set_topics_generated(True)
        set_topics_confirmed(True)
        set_questions_generated(True)

        if "app_phase" in st.session_state:
            del st.session_state["app_phase"]

        if "quiz_state" in st.session_state:
            del st.session_state["quiz_state"]

        api_client = get_api_client(get_user_id())
        response = api_client.restart_quiz(quiz_id, hard=False)

        quiz_name = "Quiz"
        if quiz_id and "_" in quiz_id:
            quiz_name = quiz_id.split("_")[0]
        st.success(f"🔄 Restartujesz quiz {quiz_name}...")

        st.rerun()

    except Exception as e:
        st.error(f"❌ Błąd podczas restartowania quizu: {str(e)}")


def configure_quiz(quiz_id: str):
    """Configure a created quiz (deprecated - use continue_quiz instead)"""
    try:
        st.session_state["quiz_id"] = quiz_id

        st.session_state["app_phase"] = (
            "topic_management"  
        )

        quiz_name = "Quiz"
        if quiz_id and "_" in quiz_id:
            quiz_name = quiz_id.split("_")[0]

        st.success(f"⚙️ Konfigurujesz quiz {quiz_name}...")

        st.rerun()

    except Exception as e:
        st.error(f"❌ Błąd podczas konfigurowania quizu: {str(e)}")


def show_quiz_stats_inline(quiz_id: str):
    """Show quiz statistics inline within the quiz item"""
    try:
        api_client = get_api_client(get_user_id())
        stats = api_client.get_quiz_progress(quiz_id)

        if stats and "progress" in stats:
            progress = stats["progress"]

            st.markdown(
                f"""
            <div style="
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                border-radius: 15px;
                padding: 20px;
                margin: 15px 0;
                color: white;
                box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
                text-align: center;
            ">
                <h3 style="margin: 0 0 20px 0; font-weight: 600;">
                    📊 Statystyki quizu
                </h3>
            </div>
            """,
                unsafe_allow_html=True,
            )

            col1, col2 = st.columns(2)

            with col1:
                st.markdown(
                    f"""
                <div style="background: linear-gradient(135deg, #74b9ff, #0984e3); padding: 15px; border-radius: 10px; margin: 5px 0; color: white; text-align: center;">
                    <h4 style="margin: 0; font-size: 14px; opacity: 0.9;">Pytania w puli</h4>
                    <h2 style="margin: 5px 0; font-size: 24px; font-weight: bold;">{progress.get("total_questions_in_pool", 0)}</h2>
                </div>
                """,
                    unsafe_allow_html=True,
                )

                st.markdown(
                    f"""
                <div style="background: linear-gradient(135deg, #fd79a8, #e84393); padding: 15px; border-radius: 10px; margin: 5px 0; color: white; text-align: center;">
                    <h4 style="margin: 0; font-size: 14px; opacity: 0.9;">Odpowiedzi udzielone</h4>
                    <h2 style="margin: 5px 0; font-size: 24px; font-weight: bold;">{progress.get("unique_answered", 0)}</h2>
                </div>
                """,
                    unsafe_allow_html=True,
                )

            with col2:
                st.markdown(
                    f"""
                <div style="background: linear-gradient(135deg, #55efc4, #00b894); padding: 15px; border-radius: 10px; margin: 5px 0; color: white; text-align: center;">
                    <h4 style="margin: 0; font-size: 14px; opacity: 0.9;">Unikalne pytania</h4>
                    <h2 style="margin: 5px 0; font-size: 24px; font-weight: bold;">{progress.get("total_unique_questions", 0)}</h2>
                </div>
                """,
                    unsafe_allow_html=True,
                )

                st.markdown(
                    f"""
                <div style="background: linear-gradient(135deg, #fdcb6e, #e17055); padding: 15px; border-radius: 10px; margin: 5px 0; color: white; text-align: center;">
                    <h4 style="margin: 0; font-size: 14px; opacity: 0.9;">Poprawne odpowiedzi</h4>
                    <h2 style="margin: 5px 0; font-size: 24px; font-weight: bold;">{progress.get("unique_correct", 0)}</h2>
                </div>
                """,
                    unsafe_allow_html=True,
                )

            col1, col2 = st.columns(2)

            with col1:
                answered = progress.get("unique_answered", 0)
                if answered > 0:
                    success_rate = (progress.get("unique_correct", 0) / answered) * 100
                    color = (
                        "#00b894"
                        if success_rate >= 70
                        else "#fdcb6e" if success_rate >= 50 else "#e17055"
                    )
                    st.markdown(
                        f"""
                    <div style="background: {color}; padding: 12px; border-radius: 8px; margin: 5px 0; color: white; text-align: center;">
                        <h4 style="margin: 0; font-size: 12px; opacity: 0.9;">Skuteczność</h4>
                        <h3 style="margin: 5px 0; font-size: 18px; font-weight: bold;">{success_rate:.1f}%</h3>
                    </div>
                    """,
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        f"""
                    <div style="background: #636e72; padding: 12px; border-radius: 8px; margin: 5px 0; color: white; text-align: center;">
                        <h4 style="margin: 0; font-size: 12px; opacity: 0.9;">Skuteczność</h4>
                        <h3 style="margin: 5px 0; font-size: 18px; font-weight: bold;">0%</h3>
                    </div>
                    """,
                        unsafe_allow_html=True,
                    )

            with col2:
                total_attempts = progress.get("total_attemps", 0)
                st.markdown(
                    f"""
                <div style="background: #74b9ff; padding: 12px; border-radius: 8px; margin: 5px 0; color: white; text-align: center;">
                    <h4 style="margin: 0; font-size: 12px; opacity: 0.9;">Łączne próby</h4>
                    <h3 style="margin: 5px 0; font-size: 18px; font-weight: bold;">{total_attempts}</h3>
                </div>
                """,
                    unsafe_allow_html=True,
                )

            if progress.get("total_unique_questions", 0) > 0:
                total_questions = progress.get("total_unique_questions", 0)
                answered_questions = progress.get("unique_answered", 0)
                progress_percentage = (answered_questions / total_questions) * 100

                st.markdown("**📊 Postęp w quizie**")
                st.progress(progress_percentage / 100)
                st.markdown(
                    f"""
                <div style="text-align: center; margin: 10px 0;">
                    <strong>{answered_questions}/{total_questions} pytań ({progress_percentage:.1f}%)</strong>
                </div>
                """,
                    unsafe_allow_html=True,
                )

        else:
            st.info("📊 Brak dostępnych statystyk dla tego quizu.")

    except Exception as e:
        st.error(f"❌ Błąd podczas ładowania statystyk: {str(e)}")


def show_quiz_stats(quiz_id: str):
    """Show quiz statistics in a modal-like container (deprecated - use show_quiz_stats_inline)"""
    show_quiz_stats_inline(quiz_id)


def delete_quiz(quiz_id: str):
    """Delete a quiz with confirmation"""
    st.warning(f"⚠️ Czy na pewno chcesz usunąć quiz {quiz_id[:8]}?")
    st.write("Ta operacja jest nieodwracalna!")

    col1, col2 = st.columns(2)

    with col1:
        if st.button(
            "✅ Tak, usuń", key=f"confirm_delete_{quiz_id}", use_container_width=True
        ):
            try:
                api_client = get_api_client(get_user_id())
                st.error(
                    "❌ Funkcja usuwania quizu nie jest jeszcze zaimplementowana w API."
                )

            except Exception as e:
                st.error(f"❌ Błąd podczas usuwania quizu: {str(e)}")

    with col2:
        if st.button(
            "❌ Anuluj", key=f"cancel_delete_{quiz_id}", use_container_width=True
        ):
            st.rerun()  
