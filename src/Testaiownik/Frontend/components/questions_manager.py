import streamlit as st
from components.quiz_manager import return_to_main_menu
from utils.session_manager import get_quiz_id, get_user_id, set_questions_generated
from services.api_client import get_api_client
from typing import List
from config.settings import (
    MIN_QUESTIONS,
    DEFAULT_QUESTION_RATIO,
    ERROR_MAX_QUESTION,
)


def get_max_questions_estimate(quiz_id: str, ratio: int = 2) -> int:
    """Estimate max questions for documents"""
    try:
        api_client = get_api_client(get_user_id())
        if not api_client:
            st.error("❌ Brak połączenia z API")
            return ERROR_MAX_QUESTION

        response = api_client.get_question_estimate(quiz_id, ratio)

        if response and "estimated_max_questions" in response:
            return response["estimated_max_questions"]
        else:
            st.warning("⚠️ Nie udało się pobrać oszacowania pytań")
            return ERROR_MAX_QUESTION

    except Exception as e:
        st.warning(f"⚠️ Błąd podczas pobierania oszacowania pytań: {e}")
        return ERROR_MAX_QUESTION


def render_questions_manager():
    """Render quiz questions configuration"""
    quiz_id = get_quiz_id()
    if not quiz_id:
        st.error("❌ Brak ID quizu. Wróć do tworzenia quizu.")
        return

    st.title("📝 Konfiguracja pytań")
    col1, col2 = st.columns([5, 3])

    with col2:
        st.button(
            "🏠 Powrót do strony głównej",
            key="return_to_main_menu",
            help="Wróć do głównej strony",
            on_click=return_to_main_menu,
        )

    st.subheader("⚙️ Ustawienia testu")

    ratio = DEFAULT_QUESTION_RATIO

    cache_key = f"max_questions_{quiz_id}_{ratio}"
    if cache_key not in st.session_state:
        with st.spinner("Sprawdzanie maksymalnej liczby pytań..."):
            max_questions = get_max_questions_estimate(quiz_id, ratio)
            st.session_state[cache_key] = max_questions
    else:
        max_questions = st.session_state[cache_key]

    if max_questions:
        st.info(
            f"📊 Oszacowana maksymalna liczba pytań na podstawie dokumentów: **{max_questions}**"
        )

    num_questions = st.slider(
        "Wybierz liczbę pytań",
        min_value=MIN_QUESTIONS,
        max_value=max_questions,
        value=max_questions // 2,
        help=f"Ustaw całkowitą liczbę pytań w teście (max: {max_questions})",
    )

    st.divider()

    if "user_questions" not in st.session_state:
        st.session_state["user_questions"] = []

    st.subheader("➕ Dodaj własne pytania")
    st.write("*Opcjonalnie: możesz dodać własne pytania do testu*")

    with st.container():
        col1, col2 = st.columns([4, 1])

        with col1:
            if "question_input_key" not in st.session_state:
                st.session_state["question_input_key"] = 0

            question = st.text_area(
                "Treść pytania:",
                height=100,
                placeholder="Wpisz tutaj treść pytania...",
                help="Wprowadź pytanie, które chcesz dodać do testu",
                key=f"question_input_{st.session_state['question_input_key']}",
            )

        with col2:
            st.write("")  
            st.write("")  
            if st.button("✅ Dodaj", type="secondary", use_container_width=True):
                if question.strip():
                    st.session_state["user_questions"].append(question.strip())
                    st.session_state["question_input_key"] += 1
                    st.rerun()  
                else:
                    st.warning("⚠️ Pytanie nie może być puste!")

    if st.session_state["user_questions"]:
        st.divider()
        st.subheader("📋 Twoje pytania:")

        with st.container():
            for idx, q in enumerate(st.session_state["user_questions"], 1):
                col1, col2 = st.columns([10, 1])

                with col1:
                    st.write(f"**{idx}.** {q}")

                with col2:
                    if st.button("🗑️", key=f"delete_{idx}", help="Usuń pytanie"):
                        st.session_state["user_questions"].pop(idx - 1)
                        st.rerun()

        st.info(
            f"💡 Dodano **{len(st.session_state['user_questions'])}** własnych pytań"
        )
    else:
        st.info("💡 Nie dodano jeszcze żadnych własnych pytań")

    st.divider()

    st.subheader("🚀 Rozpocznij test")

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Całkowita liczba pytań", num_questions)
    with col2:
        st.metric("Twoje pytania", len(st.session_state["user_questions"]))

    if st.button("🚀 Rozpocznij test", type="primary", use_container_width=True):
        start_test(quiz_id, num_questions, st.session_state["user_questions"])


def start_test(quiz_id: str, total_questions: int, user_questions: List[str]):
    """Start quiz with user-defined question count and optional custom questions - ENHANCED"""
    try:
        with st.spinner("Rozpoczynanie testu..."):
            api_client = get_api_client(get_user_id())

            request_data = {
                "total_questions": total_questions,
                "difficulty": "very-hard",  
                "user_questions": user_questions if user_questions else [],
            }

            response = api_client.start_quiz(quiz_id=quiz_id, **request_data)

            if response:

                quiz_name = "Quiz"
                if quiz_id and "_" in quiz_id:
                    quiz_name = quiz_id.split("_")[0]

                with st.expander("📊 Szczegóły testu", expanded=True):
                    st.write(f"🆔 **Nazwa quizu:** {quiz_name}")
                    st.write(f"📝 **Liczba pytań:** {total_questions}")
                    st.write(f"👤 **Twoje pytania:** {len(user_questions)}")
                    st.write(f"🎯 **Status:** Generowanie pytań...")

                set_questions_generated()

                if "quiz_state" in st.session_state:
                    del st.session_state["quiz_state"]

                progress_cache_key = f"quiz_progress_{quiz_id}"
                if progress_cache_key in st.session_state:
                    del st.session_state[progress_cache_key]

                st.session_state["app_phase"] = "test"

                st.info("🔄 Test jest generowany. Poczekaj chwilę...")

                st.rerun()

            else:
                st.error("❌ Wystąpił problem podczas rozpoczęcia testu.")

    except Exception as e:
        st.error(f"❌ Błąd podczas rozpoczęcia testu: {str(e)}")

        with st.expander("🔍 Szczegóły błędu", expanded=False):
            st.code(str(e))
            st.write("**Parametry wywołania:**")
            st.json(
                {
                    "quiz_id": quiz_id,
                    "total_questions": total_questions,
                    "user_questions_count": len(user_questions),
                    "confirmed_topics": st.session_state.get("confirmed_topics", []),
                    "user_id": get_user_id(),
                }
            )
