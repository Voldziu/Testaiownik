# components/topics_manager.py

import streamlit as st
import time
from typing import List, Dict, Any
from utils.session_manager import (
    get_user_id,
    get_quiz_id,
    are_topics_generated,
    set_topics_generated,
    get_editing_topic,
    set_editing_topic
)
from services.api_client import get_api_client, APIError
from config.settings import (
    DEFAULT_TOPIC_COUNT,
    MIN_TOPIC_COUNT,
    MAX_TOPIC_COUNT,
    MIN_TOPIC_WEIGHT,
    MAX_TOPIC_WEIGHT,
    DEFAULT_TOPIC_WEIGHT
)
from components.status_display import render_topic_generation_status

def render_topics_manager():
    """Render topics management component"""
    quiz_id = get_quiz_id()
    
    if not quiz_id:
        st.error("❌ Brak ID quizu. Wróć do tworzenia quizu.")
        return
    
    if not are_topics_generated():
        _render_topic_generation_setup()
    else:
        _render_topic_management()

def _render_topic_generation_setup():
    """Render topic generation setup section"""
    st.title("🎯 Generowanie tematów")
    
    quiz_id = get_quiz_id()
    
    # Show current status
    render_topic_generation_status(quiz_id)
    
    st.divider()
    
    # Topic generation configuration
    st.subheader("⚙️ Konfiguracja generowania")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.write("**Liczba tematów do wygenerowania:**")
        num_topics = st.slider(
            "Wybierz liczbę tematów",
            min_value=MIN_TOPIC_COUNT,
            max_value=MAX_TOPIC_COUNT,
            value=DEFAULT_TOPIC_COUNT,
            help="Więcej tematów = bardziej szczegółowa analiza, ale dłuższy czas przetwarzania"
        )
    
    with col2:
        st.write("**Podgląd:**")
        st.info(f"📊 {num_topics} tematów")
        
        if num_topics <= 10:
            st.write("🎯 Analiza podstawowa")
        elif num_topics <= 25:
            st.write("📈 Analiza standardowa")
        else:
            st.write("🔍 Analiza szczegółowa")
    
    # Generation settings
    with st.expander("🔧 Zaawansowane ustawienia", expanded=False):
        st.markdown("""
        **Jak działa generowanie tematów:**
        
        1. **Analiza dokumentów** - system analizuje całą zawartość przesłanych plików
        2. **Identyfikacja kluczowych słów** - znajduje najważniejsze terminy i pojęcia
        3. **Grupowanie** - łączy powiązane pojęcia w logiczne tematy
        4. **Ocena ważności** - przypisuje wagi na podstawie częstotliwości i kontekstu
        5. **Finalizacja** - tworzy listę gotowych tematów do edycji
        
        **Wskazówki:**
        - Mniejsza liczba tematów = szersze kategorie
        - Większa liczba tematów = bardziej szczegółowe podziały
        - Możesz później edytować, dodawać i usuwać tematy
        """)
    
    # Generate button
    st.divider()
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        if st.button("🚀 Rozpocznij generowanie tematów", type="primary", use_container_width=True):
            _start_topic_generation(num_topics)
    
    with col2:
        if st.button("⬅️ Wróć do indeksowania", use_container_width=True):
            st.info("Powrót do poprzedniego kroku...")
            # Here you could implement navigation back
            time.sleep(1)

def _render_topic_management():
    """Render topic management section"""
    st.title("📝 Zarządzanie tematami")
    
    quiz_id = get_quiz_id()
    
    # Add new topic section
    _render_add_topic_section(quiz_id)
    
    st.divider()
    
    # Display existing topics
    _render_topics_list(quiz_id)

def _render_add_topic_section(quiz_id: str):
    """Render add new topic section"""
    st.subheader("➕ Dodaj nowy temat")
    
    with st.expander("Dodaj własny temat", expanded=False):
        with st.form("add_topic_form"):
            col1, col2 = st.columns([2, 1])
            
            with col1:
                new_topic_name = st.text_input(
                    "Nazwa tematu",
                    placeholder="np. Podstawy programowania",
                    help="Wprowadź nazwę nowego tematu"
                )
            
            with col2:
                new_topic_weight = st.slider(
                    "Waga tematu",
                    min_value=MIN_TOPIC_WEIGHT,
                    max_value=MAX_TOPIC_WEIGHT,
                    value=DEFAULT_TOPIC_WEIGHT,
                    help="Wyższa waga = więcej pytań z tego tematu"
                )
            
            # Form submit button
            submitted = st.form_submit_button("➕ Dodaj temat", type="primary", use_container_width=True)
            
            if submitted:
                if new_topic_name.strip():
                    _add_new_topic(quiz_id, new_topic_name.strip(), new_topic_weight)
                else:
                    st.error("⚠️ Nazwa tematu nie może być pusta!")

def _render_topics_list(quiz_id: str):
    """Render list of existing topics"""
    try:
        api_client = get_api_client(get_user_id())
        topics_data = api_client.get_topics(quiz_id)
        
        suggested_topics = topics_data.get("suggested_topics", [])
        
        if not suggested_topics:
            st.info("📝 Brak tematów do wyświetlenia. Dodaj pierwszy temat powyżej!")
            return
        
        st.subheader(f"📋 Lista tematów ({len(suggested_topics)})")
        
        # Topics summary
        total_weight = sum(topic.get('weight', 1.0) for topic in suggested_topics)
        st.write(f"**Całkowita waga wszystkich tematów:** {total_weight:.1f}")
        
        # Topics list
        for i, topic in enumerate(suggested_topics):
            _render_topic_item(quiz_id, topic, i)
            
            if i < len(suggested_topics) - 1:  # Don't add divider after last item
                st.divider()
                
    except APIError as e:
        st.error("❌ Nie udało się pobrać listy tematów")
        with st.expander("🔧 Szczegóły błędu", expanded=False):
            st.write(f"**Status:** {e.status_code}")
            st.write(f"**Komunikat:** {e.message}")
    except Exception as e:
        st.error(f"❌ Nieoczekiwany błąd: {str(e)}")

def _render_topic_item(quiz_id: str, topic: Dict[str, Any], index: int):
    """Render individual topic item"""
    topic_name = topic.get('topic', 'Nieznany temat')
    topic_weight = topic.get('weight', 1.0)
    
    # Check if this topic is being edited
    is_editing = get_editing_topic() == topic_name
    
    if is_editing:
        _render_topic_edit_mode(quiz_id, topic_name, topic_weight)
    else:
        _render_topic_display_mode(quiz_id, topic_name, topic_weight, index)

def _render_topic_display_mode(quiz_id: str, topic_name: str, topic_weight: float, index: int):
    """Render topic in display mode"""
    col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
    
    with col1:
        # Topic info with visual indicators
        weight_indicator = "🔥" if topic_weight > 5.0 else "⭐" if topic_weight > 2.0 else "📝"
        st.write(f"{weight_indicator} **{topic_name}**")
        st.caption(f"Waga: {topic_weight:.1f}")
    
    with col2:
        # Edit button
        if st.button("✏️ Edytuj", key=f"edit_{topic_name}_{index}", use_container_width=True):
            set_editing_topic(topic_name)
            st.rerun()
    
    with col3:
        # Delete button with confirmation
        if st.button("🗑️ Usuń", key=f"delete_{topic_name}_{index}", use_container_width=True):
            _delete_topic(quiz_id, topic_name)    


def _render_topic_edit_mode(quiz_id: str, topic_name: str, current_weight: float):
    """Render topic in edit mode"""
    st.write(f"**✏️ Edytujesz temat:** {topic_name}")
    
    # Initialize edit values in session state if they don't exist
    edit_name_key = f"edit_name_{topic_name}"
    edit_weight_key = f"edit_weight_{topic_name}"
    
    if edit_name_key not in st.session_state:
        st.session_state[edit_name_key] = topic_name
    if edit_weight_key not in st.session_state:
        st.session_state[edit_weight_key] = current_weight
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        new_name = st.text_input(
            "Nowa nazwa tematu",
            value=st.session_state[edit_name_key],
            key=f"name_input_{topic_name}",
            help="Wprowadź nową nazwę tematu"
        )
        st.session_state[edit_name_key] = new_name
        
        new_weight = st.slider(
            "Nowa waga",
            min_value=MIN_TOPIC_WEIGHT,
            max_value=MAX_TOPIC_WEIGHT,
            value=st.session_state[edit_weight_key],
            key=f"weight_input_{topic_name}",
            help="Wyższa waga = więcej pytań z tego tematu"
        )
        st.session_state[edit_weight_key] = new_weight
    
    with col2:
        st.write("")  # Spacer for alignment
        st.write("")  # Spacer for alignment
        
        # Action buttons
        col_confirm, col_cancel = st.columns(2)
        
        with col_confirm:
            if st.button("✅ Zatwierdź", key=f"confirm_{topic_name}", use_container_width=True):
                if new_name.strip():
                    _update_topic(quiz_id, topic_name, new_name.strip(), new_weight)
                    _clear_edit_state(topic_name)
                    set_editing_topic(None)
                    st.rerun()
                else:
                    st.error("⚠️ Nazwa tematu nie może być pusta!")
        
        with col_cancel:
            if st.button("❌ Anuluj", key=f"cancel_{topic_name}", use_container_width=True):
                _clear_edit_state(topic_name)
                set_editing_topic(None)
                st.rerun()

def _start_topic_generation(num_topics: int):
    """Start topic generation process"""
    try:
        quiz_id = get_quiz_id()
        user_id = get_user_id()
        
        api_client = get_api_client(user_id)
        
        with st.spinner("🚀 Rozpoczynanie generowania tematów..."):
            response = api_client.start_topic_generation(quiz_id, num_topics)
            
            if response:
                st.success("✅ Generowanie tematów zostało rozpoczęte!")
                set_topics_generated(True)
                time.sleep(1)
                st.rerun()
            else:
                st.error("❌ Wystąpił problem podczas rozpoczynania generowania tematów")
                
    except APIError as e:
        st.error("❌ Nie udało się rozpocząć generowania tematów")
        with st.expander("🔧 Szczegóły błędu", expanded=False):
            st.write(f"**Status:** {e.status_code}")
            st.write(f"**Komunikat:** {e.message}")
    except Exception as e:
        st.error(f"❌ Nieoczekiwany błąd: {str(e)}")

def _add_new_topic(quiz_id: str, topic_name: str, weight: float):
    """Add a new topic"""
    try:
        api_client = get_api_client(get_user_id())
        
        with st.spinner(f"➕ Dodawanie tematu '{topic_name}'..."):
            response = api_client.add_topic(quiz_id, topic_name, weight)
            
            if response:
                st.success(f"✅ Temat '{topic_name}' został dodany!")
                time.sleep(1)
                st.rerun()
            else:
                st.error("❌ Wystąpił problem podczas dodawania tematu")
                
    except APIError as e:
        st.error("❌ Nie udało się dodać tematu")
        with st.expander("🔧 Szczegóły błędu", expanded=False):
            st.write(f"**Status:** {e.status_code}")
            st.write(f"**Komunikat:** {e.message}")
    except Exception as e:
        st.error(f"❌ Nieoczekiwany błąd: {str(e)}")

def _update_topic(quiz_id: str, old_name: str, new_name: str, new_weight: float):
    """Update an existing topic"""
    try:
        api_client = get_api_client(get_user_id())
        
        with st.spinner(f"✏️ Aktualizowanie tematu '{old_name}'..."):
            response = api_client.update_topic(quiz_id, old_name, new_name, new_weight)
            
            if response:
                st.success(f"✅ Temat został zaktualizowany!")
            else:
                st.error("❌ Wystąpił problem podczas aktualizacji tematu")
                
    except APIError as e:
        st.error("❌ Nie udało się zaktualizować tematu")
        with st.expander("🔧 Szczegóły błędu", expanded=False):
            st.write(f"**Status:** {e.status_code}")
            st.write(f"**Komunikat:** {e.message}")
    except Exception as e:
        st.error(f"❌ Nieoczekiwany błąd: {str(e)}")


def _delete_topic(quiz_id: str, topic_name: str):
    try:
        api_client = get_api_client(get_user_id())
        
        with st.spinner(f"🗑️ Usuwanie tematu '{topic_name}'..."):
            response = api_client.delete_topic(quiz_id, topic_name)
            
            if response:
                # Usuń z session_state jeśli tam przechowujesz
                if 'topics' in st.session_state:
                    st.session_state.topics = [
                        topic for topic in st.session_state.topics 
                        if topic.get('name') != topic_name
                    ]
                
                st.success(f"✅ Temat '{topic_name}' został usunięty!")
                time.sleep(1)
                st.rerun()
            else:
                st.error("❌ Wystąpił problem podczas usuwania tematu")
                
    except APIError as e:
        st.error("❌ Nie udało się usunąć tematu")
        with st.expander("🔧 Szczegóły błędu", expanded=False):
            st.write(f"**Status:** {e.status_code}")
            st.write(f"**Komunikat:** {e.message}")
    except Exception as e:
        st.error(f"❌ Nieoczekiwany błąd: {str(e)}")


def _clear_edit_state(topic_name: str):
    """Clear edit state from session"""
    edit_name_key = f"edit_name_{topic_name}"
    edit_weight_key = f"edit_weight_{topic_name}"
    
    if edit_name_key in st.session_state:
        del st.session_state[edit_name_key]
    if edit_weight_key in st.session_state:
        del st.session_state[edit_weight_key]

# Navigation helper functions
def render_navigation_buttons():
    """Render navigation buttons for topic management"""
    st.divider()
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col1:
        if st.button("⬅️ Wróć do indeksowania", use_container_width=True):
            # Reset topics generation state
            set_topics_generated(False)
            st.info("Powrót do indeksowania...")
            time.sleep(1)
            st.rerun()
    
    with col3:
        if st.button("➡️ Dalej do pytań", type="primary", use_container_width=True):
            # Navigate to questions generation
            st.info("Przechodzenie do generowania pytań...")
            time.sleep(1)
            # This would navigate to the next step
            # Implementation depends on your navigation system

def get_topics_summary(quiz_id: str) -> Dict[str, Any]:
    """Get summary of topics for the quiz"""
    try:
        api_client = get_api_client(get_user_id())
        topics_data = api_client.get_topics(quiz_id)
        
        suggested_topics = topics_data.get("suggested_topics", [])
        
        return {
            "total_topics": len(suggested_topics),
            "total_weight": sum(topic.get('weight', 1.0) for topic in suggested_topics),
            "topics": suggested_topics
        }
    except Exception:
        return {
            "total_topics": 0,
            "total_weight": 0.0,
            "topics": []
        }