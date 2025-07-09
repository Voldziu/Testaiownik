# components/quiz_creation.py

import streamlit as st
from components.quiz_manager import return_to_main_menu
from utils.session_manager import get_user_id, set_quiz_id, reset_quiz_session
from services.api_client import get_api_client, APIError


def render_quiz_creation():
    """Render quiz creation component"""
    st.title("Generowanie Quizu")

    # Display user ID
    user_id = get_user_id()
    st.write(f"Twoje UserID: {user_id}")

    # Create new quiz section
    col1, col2 = st.columns([2, 1])

    with col1:
        if st.button("🎯 Stwórz nowy quiz", type="primary", use_container_width=True):
            _create_new_quiz()

    with col2:
        st.button(
            "🏠 Powrót do strony głównej",
            key="return_to_main_menu",
            help="Wróć do głównej strony",
            on_click=return_to_main_menu,
        )

    # Help section
    with st.expander("ℹ️ Jak to działa?", expanded=False):
        st.markdown(
            """
        **Proces tworzenia quizu:**
        1. **Stwórz quiz** - nadaj unikalny identyfikator
        2. **Prześlij pliki** - dodaj dokumenty do analizy
        3. **Zaindeksuj** - przygotuj dokumenty do przetwarzania
        4. **Wygeneruj tematy** - automatycznie znajdź kluczowe tematy
        5. **Zarządzaj** - edytuj, dodawaj i usuwaj tematy
        """
        )


def _create_new_quiz():
    """Handle quiz creation logic"""
    try:
        # Show loading spinner
        with st.spinner("Tworzenie quizu..."):
            user_id = get_user_id()
            api_client = get_api_client(user_id)

            # Create quiz via API
            quiz_data = api_client.create_quiz()
            quiz_id = quiz_data["quiz_id"]

            # Save to session
            set_quiz_id(quiz_id)

            # Show success message
            st.success(f"✅ Quiz został stworzony! ID quizu: {quiz_id}")

            # Auto-advance to next step
            st.info("Przekierowuję do uploadu plików...")
            st.rerun()

    except APIError as e:
        st.error(f"❌ Wystąpił problem podczas tworzenia quizu")

        # Show detailed error info in expander
        with st.expander("🔧 Szczegóły błędu", expanded=False):
            st.write(f"**Status code:** {e.status_code}")
            st.write(f"**Komunikat:** {e.message}")

            if e.status_code == 500:
                st.write("**Możliwe przyczyny:**")
                st.write("- Problem z połączeniem do bazy danych")
                st.write("- Błąd w funkcji `get_user_id()` na backendzie")
                st.write("- Błąd w funkcji `validate_quiz_access()`")
                st.write("- Niepoprawna konfiguracja nagłówków HTTP")

                st.write("**Wysyłane dane:**")
                st.json(
                    {
                        "URL": f"{api_client._base_url}/api/quiz/create",
                        "Headers": api_client.headers,
                        "User-ID": get_user_id(),
                    }
                )

    except Exception as e:
        st.error(f"❌ Nieoczekiwany błąd: {str(e)}")
        st.write("Spróbuj ponownie lub skontaktuj się z administratorem.")
