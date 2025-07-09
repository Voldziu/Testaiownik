# components/quiz_creation.py

import streamlit as st
from components.quiz_manager import return_to_main_menu
from utils.session_manager import (
    get_user_id,
    set_quiz_id,
    reset_quiz_session
)
from services.api_client import get_api_client, APIError

def render_quiz_creation():
    """Render quiz creation component"""
    st.title("Generowanie Quizu")
    
    # Quiz name input section
    st.subheader("📝 Nazwij swój quiz")
    
    quiz_name = st.text_input(
        "Nazwa quizu:",
        placeholder="Wprowadź nazwę quizu...",
        help="Nadaj swojemu quizowi unikalną nazwę. Nazwa nie może zawierać podłogi ani spacji (_)."
    )
    
    # Validate quiz name
    name_error = _validate_quiz_name(quiz_name)
    if name_error:
        st.error(f"❌ {name_error}")

    
    # Create new quiz section
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Disable button if name is invalid or empty
        button_disabled = bool(name_error) or not quiz_name.strip()
        
        if st.button("🎯 Stwórz nowy quiz", 
                    type="primary", 
                    use_container_width=True,
                    disabled=button_disabled):
            _create_new_quiz(quiz_name.strip())
    
    with col2:
        st.button("🏠 Powrót do strony głównej", 
              key="return_to_main_menu", 
              help="Wróć do głównej strony", 
              on_click=return_to_main_menu)
    
    # Help section
    with st.expander("ℹ️ Jak to działa?", expanded=False):
        st.markdown("""
        **Proces tworzenia quizu:**
        1. **Nazwij quiz** - nadaj mu unikalną nazwę (bez podłogi i spacji)
        2. **Stwórz quiz** - nadaj unikalny identyfikator
        3. **Prześlij pliki** - dodaj dokumenty do analizy
        4. **Zaindeksuj** - przygotuj dokumenty do przetwarzania
        5. **Wygeneruj tematy** - automatycznie znajdź kluczowe tematy
        6. **Zarządzaj** - edytuj, dodawaj i usuwaj tematy
        
        **Zasady nazewnictwa:**
        - Nazwa nie może być pusta
        - Nazwa nie może zawierać podłogi ani spacji (_)
        - Użyj opisowej nazwy dla łatwiejszej identyfikacji
        """)

def _validate_quiz_name(name):
    """Validate quiz name according to rules"""
    if not name:
        return None  # Empty name is handled by button disable
    
    name = name.strip()
    
    if not name:
        return "Nazwa quizu nie może być pusta"
    
    if '_' in name or ' ' in name:
        return "Nazwa quizu nie może zawierać podłogi ani spacji (_)"
    
    if len(name) > 100:
        return "Nazwa quizu nie może być dłuższa niż 100 znaków"
    
    return None


def _create_new_quiz(name):
    """Handle quiz creation logic"""
    try:
        # Show loading spinner
        with st.spinner("Tworzenie quizu..."):
            user_id = get_user_id()
            api_client = get_api_client(user_id)
            
            # Create quiz via API
            quiz_data = api_client.create_quiz(name)
            quiz_id = quiz_data['quiz_id']
            
            # Save to session
            set_quiz_id(quiz_id)
            
            
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
                st.json({
                    "URL": f"{api_client._base_url}/api/quiz/create",
                    "Headers": api_client.headers,
                    "User-ID": get_user_id()
                })
    
    except Exception as e:
        st.error(f"❌ Nieoczekiwany błąd: {str(e)}")
        st.write("Spróbuj ponownie lub skontaktuj się z administratorem.")