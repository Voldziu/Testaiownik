import time
import streamlit as st
from utils.session_manager import get_quiz_id, get_user_id, set_questions_generated
from services.api_client import get_api_client
from typing import List


def render_questions_manager():
    """Render quiz questions configuration"""
    quiz_id = get_quiz_id()
    if not quiz_id:
        st.error("❌ Brak ID quizu. Wróć do tworzenia quizu.")
        return

    st.title("📝 Konfiguracja pytań")

    # Sekcja konfiguracji liczby pytań z suwakiem
    st.subheader("⚙️ Ustawienia testu")
    num_questions = st.slider(
        "Wybierz liczbę pytań",
        min_value=1,
        max_value=50,
        value=10,
        help="Ustaw całkowitą liczbę pytań w teście",
    )

    # Wyświetlenie aktualnej wartości
    st.info(f"📊 Liczba pytań w teście: **{num_questions}**")

    # Separator
    st.divider()

    # Lista pytań dodanych przez użytkownika (będzie przechowywana w session_state)
    if "user_questions" not in st.session_state:
        st.session_state["user_questions"] = []

    # Sekcja dodawania pytań
    st.subheader("➕ Dodaj własne pytania")
    st.write("*Opcjonalnie: możesz dodać własne pytania do testu*")

    # Komponent do dodawania pytania
    with st.container():
        col1, col2 = st.columns([4, 1])

        with col1:
            # Ustawienie wartości domyślnej dla inputu w session_state, jeżeli nie istnieje
            if "new_question_input" not in st.session_state:
                st.session_state["new_question_input"] = ""

            question = st.text_area(
                "Treść pytania:",
                value=st.session_state["new_question_input"],
                height=100,
                placeholder="Wpisz tutaj treść pytania...",
                help="Wprowadź pytanie, które chcesz dodać do testu",
            )

        with col2:
            st.write("")  # Spacer
            st.write("")  # Spacer
            if st.button("✅ Dodaj", type="secondary", use_container_width=True):
                if question.strip():
                    st.session_state["user_questions"].append(question.strip())
                    st.session_state["new_question_input"] = ""  # Clear the input field
                    st.rerun()  # Refresh to show the new question
                else:
                    st.warning("⚠️ Pytanie nie może być puste!")

    # Wyświetlanie dodanych pytań na dole
    if st.session_state["user_questions"]:
        st.divider()
        st.subheader("📋 Twoje pytania:")

        # Kontener z przewijaniem dla pytań
        with st.container():
            for idx, q in enumerate(st.session_state["user_questions"], 1):
                col1, col2 = st.columns([10, 1])

                with col1:
                    st.write(f"**{idx}.** {q}")

                with col2:
                    # Przycisk usuwania pytania
                    if st.button("🗑️", key=f"delete_{idx}", help="Usuń pytanie"):
                        st.session_state["user_questions"].pop(idx - 1)
                        st.rerun()

        st.info(
            f"💡 Dodano **{len(st.session_state['user_questions'])}** własnych pytań"
        )
    else:
        st.info("💡 Nie dodano jeszcze żadnych własnych pytań")

    # Separator przed przyciskiem rozpoczęcia
    st.divider()

    # Przycisk do rozpoczęcia testu - zawsze widoczny
    st.subheader("🚀 Rozpocznij test")

    # Podsumowanie konfiguracji
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Całkowita liczba pytań", num_questions)
    with col2:
        st.metric("Twoje pytania", len(st.session_state["user_questions"]))

    # Główny przycisk rozpoczęcia
    if st.button("🚀 Rozpocznij test", type="primary", use_container_width=True):
        start_test(quiz_id, num_questions, st.session_state["user_questions"])


def start_test(quiz_id: str, total_questions: int, user_questions: List[str]):
    """Start quiz with user-defined question count and optional custom questions"""
    try:
        with st.spinner("Rozpoczynanie testu..."):
            api_client = get_api_client(get_user_id())

            # Przygotowanie danych do wysłania
            request_data = {
                "total_questions": total_questions,
                "difficulty": "very-hard",  # Domyślny poziom trudności
                "user_questions": user_questions if user_questions else [],
            }

            # Wywołanie endpointu /quiz/{quiz_id}/start
            response = api_client.start_quiz(quiz_id=quiz_id, **request_data)

            if response:
                st.success("✅ Test został pomyślnie rozpoczęty!")

                # Wyświetlenie informacji o teście
                st.balloons()

                with st.expander("📊 Szczegóły testu", expanded=True):
                    st.write(f"🆔 **ID Quizu:** {quiz_id}")
                    st.write(f"📝 **Liczba pytań:** {total_questions}")
                    st.write(f"👤 **Twoje pytania:** {len(user_questions)}")
                    st.write(f"🎯 **Status:** Generowanie pytań...")
                    st.write(f"⏱️ **Szacowany czas generowania:** ~30 sekund")

                set_questions_generated()
                st.session_state["app_phase"] = "test"
                # Opcjonalnie przekierowanie lub dalsze akcje
                st.info("🔄 Test jest generowany.")

                time.sleep(1)
                st.rerun()

            else:
                st.error("❌ Wystąpił problem podczas rozpoczęcia testu.")

    except Exception as e:
        st.error(f"❌ Błąd podczas rozpoczęcia testu: {str(e)}")

        # Debug info w przypadku błędu
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
