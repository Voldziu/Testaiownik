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

    st.subheader("📊 Statystyki indeksowania")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Całkowita liczba dokumentów", total_documents, delta=None)

    with col2:
        st.metric(
            "Zaindeksowane dokumenty",
            indexed_documents,
            delta=indexed_documents - total_documents if total_documents > 0 else None,
        )

    with col3:
        st.metric(
            "Postęp",
            f"{indexing_progress}%",
            delta=(
                f"{indexing_progress - 100}%" if indexing_progress < 100 else "Gotowe!"
            ),
        )

    progress_bar = st.progress(indexing_progress / 100)

    if indexing_progress == 100:
        st.success("🎉 Indeksowanie zostało ukończone!")
        return True
    elif indexing_progress > 0:
        st.info(f"⏳ Indeksowanie w toku... {indexing_progress}%")

        if "estimated_time_remaining" in stats:
            estimated_time = stats["estimated_time_remaining"]
            st.write(f"⏱️ Szacowany czas pozostały: {estimated_time}")
    else:
        st.warning("⚠️ Indeksowanie nie zostało jeszcze rozpoczęte")

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


        st.subheader("📋 Podsumowanie quizu")
        st.write(f"**Quiz ID:** {quiz_id}")

        stats = api_client.get_indexing_stats(quiz_id)

        col1, col2 = st.columns(2)

        with col1:
            st.write(f"**Liczba dokumentów:** {stats.get('total_documents', 0)}")
            st.write(
                f"**Status indeksowania:** {'Ukończone' if stats.get('indexing_progress', 0) == 100 else 'W toku'}"
            )

        with col2:
            st.write(
                f"**Zaindeksowane dokumenty:** {stats.get('indexed_documents', 0)}"
            )
            st.write(f"**Postęp:** {stats.get('indexing_progress', 0)}%")

    except APIError as e:
        st.error("❌ Nie udało się pobrać informacji o quizie")
    except Exception as e:
        st.error(f"❌ Nieoczekiwany błąd: {str(e)}")
