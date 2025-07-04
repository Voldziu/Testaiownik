# components/status_display.py

import streamlit as st
from utils.session_manager import get_user_id
from services.api_client import get_api_client, APIError

def render_indexing_status(quiz_id: str) -> bool:
    """
    Render indexing status and return True if indexing is complete
    
    Args:
        quiz_id: The quiz identifier
        
    Returns:
        bool: True if indexing is complete, False otherwise
    """
    try:
        api_client = get_api_client(get_user_id())
        stats = api_client.get_indexing_stats(quiz_id)
        
        return _display_indexing_stats(stats)
        
    except APIError as e:
        st.error("❌ Nie udało się pobrać statusu indeksowania")
        
        with st.expander("🔧 Szczegóły błędu", expanded=False):
            st.write(f"**Status:** {e.status_code}")
            st.write(f"**Komunikat:** {e.message}")
            
            if e.status_code == 404:
                st.write("**Przyczyna:** Nie znaleziono quizu lub dokumentów")
            elif e.status_code == 500:
                st.write("**Przyczyna:** Błąd serwera podczas pobierania statystyk")
        
        return False
    
    except Exception as e:
        st.error(f"❌ Nieoczekiwany błąd: {str(e)}")
        return False

def _display_indexing_stats(stats: dict) -> bool:
    """
    Display indexing statistics in a formatted way
    
    Args:
        stats: Dictionary containing indexing statistics
        
    Returns:
        bool: True if indexing is complete
    """
    total_documents = stats.get("total_documents", 0)
    indexed_documents = stats.get("indexed_documents", 0)
    indexing_progress = stats.get("indexing_progress", 0)
    
    # Progress metrics
    st.subheader("📊 Statystyki indeksowania")
    
    # Create metrics columns
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            "Całkowita liczba dokumentów",
            total_documents,
            delta=None
        )
    
    with col2:
        st.metric(
            "Zaindeksowane dokumenty",
            indexed_documents,
            delta=indexed_documents - total_documents if total_documents > 0 else None
        )
    
    with col3:
        st.metric(
            "Postęp",
            f"{indexing_progress}%",
            delta=f"{indexing_progress - 100}%" if indexing_progress < 100 else "Gotowe!"
        )
    
    # Progress bar
    progress_bar = st.progress(indexing_progress / 100)
    
    # Status message
    if indexing_progress == 100:
        st.success("🎉 Indeksowanie zostało ukończone!")
        return True
    elif indexing_progress > 0:
        st.info(f"⏳ Indeksowanie w toku... {indexing_progress}%")
        
        # Show estimated time if available
        if "estimated_time_remaining" in stats:
            estimated_time = stats["estimated_time_remaining"]
            st.write(f"⏱️ Szacowany czas pozostały: {estimated_time}")
    else:
        st.warning("⚠️ Indeksowanie nie zostało jeszcze rozpoczęte")
    
    # Additional information
    if "processing_details" in stats:
        _display_processing_details(stats["processing_details"])
    
    return indexing_progress == 100

def _display_processing_details(details: dict):
    """Display detailed processing information"""
    with st.expander("🔍 Szczegóły przetwarzania", expanded=False):
        if "current_file" in details:
            st.write(f"**Aktualnie przetwarzany plik:** {details['current_file']}")
        
        if "files_processed" in details:
            st.write(f"**Przetworzone pliki:** {details['files_processed']}")
        
        if "processing_stage" in details:
            st.write(f"**Etap przetwarzania:** {details['processing_stage']}")
        
        if "errors" in details and details["errors"]:
            st.write("**Błędy podczas przetwarzania:**")
            for error in details["errors"]:
                st.write(f"- {error}")

def render_quiz_summary(quiz_id: str):
    """Render quiz summary information"""
    try:
        api_client = get_api_client(get_user_id())
        
        # Get quiz info (you might need to add this endpoint)
        # quiz_info = api_client.get_quiz_info(quiz_id)
        
        st.subheader("📋 Podsumowanie quizu")
        st.write(f"**Quiz ID:** {quiz_id}")
        
        # Get indexing stats
        stats = api_client.get_indexing_stats(quiz_id)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write(f"**Liczba dokumentów:** {stats.get('total_documents', 0)}")
            st.write(f"**Status indeksowania:** {'Ukończone' if stats.get('indexing_progress', 0) == 100 else 'W toku'}")
        
        with col2:
            st.write(f"**Zaindeksowane dokumenty:** {stats.get('indexed_documents', 0)}")
            st.write(f"**Postęp:** {stats.get('indexing_progress', 0)}%")
        
    except APIError as e:
        st.error("❌ Nie udało się pobrać informacji o quizie")
    except Exception as e:
        st.error(f"❌ Nieoczekiwany błąd: {str(e)}")

def render_topic_generation_status(quiz_id: str):
    """Render topic generation status"""
    try:
        api_client = get_api_client(get_user_id())
        topics_data = api_client.get_topics(quiz_id)
        
        st.subheader("🎯 Status generowania tematów")
        
        suggested_topics = topics_data.get("suggested_topics", [])
        
        if suggested_topics:
            st.success(f"✅ Wygenerowano {len(suggested_topics)} tematów")
            
            # Show topics preview
            with st.expander("👀 Podgląd tematów", expanded=False):
                for i, topic in enumerate(suggested_topics[:5], 1):  # Show first 5
                    st.write(f"{i}. {topic.get('topic', 'Nieznany temat')} (waga: {topic.get('weight', 1.0)})")
                
                if len(suggested_topics) > 5:
                    st.write(f"... i {len(suggested_topics) - 5} więcej")
        else:
            st.info("ℹ️ Tematy nie zostały jeszcze wygenerowane")
            
    except APIError as e:
        st.error("❌ Nie udało się pobrać statusu tematów")
    except Exception as e:
        st.error(f"❌ Nieoczekiwany błąd: {str(e)}")