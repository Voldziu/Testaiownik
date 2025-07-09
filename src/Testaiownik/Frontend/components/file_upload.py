import time
import streamlit as st
from typing import List
from components.quiz_manager import return_to_main_menu
from utils.session_manager import (
    get_user_id,
    get_quiz_id,
    is_files_uploaded,
    set_files_uploaded,
    is_indexing_started,
    set_indexing_started,
    get_app_phase,
)
from services.api_client import get_api_client, APIError
from config.settings import ALLOWED_FILE_TYPES
from components.status_display import render_indexing_status


def render_file_upload():
    """Render file upload component based on current phase"""
    phase = get_app_phase()

    col1, col2 = st.columns([5, 3])

    with col2:
        st.button(
            "🏠 Powrót do strony głównej",
            key="return_to_main_menu",
            help="Wróć do głównej strony",
            on_click=return_to_main_menu,
        )

    if phase == "file_upload":
        _render_upload_section()
    elif phase == "indexing_setup":
        _render_indexing_setup()
    else:
        _render_indexing_monitor()


def _render_upload_section():
    """Render file upload section"""
    st.title("📁 Upload plików do quizu")

    quiz_id = get_quiz_id()
    if not quiz_id:
        st.error("❌ Brak ID quizu. Wróć do tworzenia quizu.")
        return

    st.info(f"Quiz ID: {quiz_id}")

    # File uploader
    uploaded_files = st.file_uploader(
        "Wybierz pliki do uploadu",
        type=ALLOWED_FILE_TYPES,
        accept_multiple_files=True,
        help=f"Obsługiwane formaty: {', '.join(ALLOWED_FILE_TYPES)}",
    )

    if uploaded_files:
        _display_selected_files(uploaded_files)

        # Enable "Prześlij pliki" button only if files are uploaded
        if uploaded_files:
            if st.button("📤 Prześlij pliki", type="primary", use_container_width=True):
                _upload_files(quiz_id, uploaded_files)
        else:
            # Disable button if no files are uploaded
            st.button(
                "📤 Prześlij pliki",
                disabled=True,
                type="primary",
                use_container_width=True,
            )

    # Show upload status if files were uploaded
    if is_files_uploaded():
        st.success("✅ Pliki zostały już przesłane!")

        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button(
                "➡️ Przejdź do indeksowania", type="primary", use_container_width=True
            ):
                st.rerun()

        with col2:
            if st.button("🔄 Prześlij inne pliki", use_container_width=True):
                set_files_uploaded(False)
                st.rerun()


def _render_indexing_setup():
    """Render indexing setup section"""
    st.title("🔄 Indeksowanie plików")

    quiz_id = get_quiz_id()

    st.success("✅ Pliki zostały przesłane pomyślnie!")
    st.info("Teraz możesz zaindeksować pliki, aby przygotować je do analizy.")

    # Indexing explanation
    with st.expander("ℹ️ Co to jest indeksowanie?", expanded=False):
        st.markdown(
            """        
        **Indeksowanie** to proces przygotowania Twoich dokumentów do analizy:
        
        - 📄 **Analiza zawartości** - system czyta i analizuje teksty
        - 🔍 **Tworzenie indeksu** - buduje strukturę do szybkiego wyszukiwania
        - 🎯 **Identyfikacja tematów** - znajduje kluczowe tematy i pojęcia
        - ⚡ **Optymalizacja** - przygotowuje dane do szybkiego przetwarzania
        
        Ten proces może potrwać kilka minut w zależności od liczby i rozmiaru plików.
        """
        )

    # Start indexing button
    col1, col2 = st.columns([2, 1])
    with col1:
        if st.button(
            "🚀 Rozpocznij indeksowanie", type="primary", use_container_width=True
        ):
            _start_indexing(quiz_id)

    with col2:
        if st.button("⬅️ Wróć do uploadu", use_container_width=True):
            set_files_uploaded(False)
            st.rerun()


def _render_indexing_monitor():
    """Render indexing monitoring section"""
    st.title("📊 Status indeksowania")

    quiz_id = get_quiz_id()

    # Show indexing status
    indexing_complete = render_indexing_status(quiz_id)

    # Navigation buttons
    col1, col2 = st.columns([1, 1])

    with col1:
        if st.button("🔄 Odśwież status", use_container_width=True):
            st.rerun()

    with col2:
        if indexing_complete:
            if st.button(
                "➡️ Przejdź do tematów", type="primary", use_container_width=True
            ):
                st.rerun()
        else:
            st.button(
                "⏳ Indeksowanie w toku...", disabled=True, use_container_width=True
            )


def _display_selected_files(files: List):
    """Display selected files information"""
    st.write(f"**Wybrane pliki:** {len(files)}")

    total_size = 0
    with st.expander("📋 Lista plików", expanded=True):
        for i, file in enumerate(files, 1):
            file_size = len(file.getvalue()) / 1024 / 1024  # Size in MB
            total_size += file_size

            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(f"{i}. **{file.name}**")
            with col2:
                st.write(f"{file_size:.2f} MB")

    st.write(f"**Całkowity rozmiar:** {total_size:.2f} MB")


def _upload_files(quiz_id: str, files: List):
    """Handle file upload logic"""
    try:
        with st.spinner("Przesyłanie plików..."):
            # Prepare files for upload
            files_data = [("files", (file.name, file)) for file in files]

            # Upload via API
            api_client = get_api_client(get_user_id())
            result = api_client.upload_files(quiz_id, files_data)

            # Update session state
            set_files_uploaded(True)

            st.success(f"✅ Pomyślnie przesłano {len(files)} plików!")

            # Show upload summary
            if "uploaded_files" in result:
                st.write("**Przesłane pliki:**")
                for file_info in result["uploaded_files"]:
                    st.write(f"- {file_info.get('filename', 'Nieznany plik')}")

            time.sleep(1)
            st.rerun()

    except APIError as e:
        st.error("❌ Błąd podczas przesyłania plików")

        with st.expander("🔧 Szczegóły błędu", expanded=False):
            st.write(f"**Status:** {e.status_code}")
            st.write(f"**Komunikat:** {e.message}")

            if e.status_code == 413:
                st.write("**Przyczyna:** Pliki są za duże")
                st.write("**Rozwiązanie:** Spróbuj przesłać mniejsze pliki")
            elif e.status_code == 400:
                st.write("**Przyczyna:** Nieprawidłowy format plików")
                st.write(f"**Obsługiwane formaty:** {', '.join(ALLOWED_FILE_TYPES)}")

    except Exception as e:
        st.error(f"❌ Nieoczekiwany błąd: {str(e)}")


def _start_indexing(quiz_id: str):
    """Handle indexing start logic"""
    try:
        with st.spinner("Indeksowanie..."):
            api_client = get_api_client(get_user_id())
            result = api_client.index_documents(quiz_id)

            set_indexing_started(True)

            st.success("✅ Indeksowanie zostało rozpoczęte!")

            if "message" in result:
                st.info(result["message"])

            time.sleep(1)
            st.rerun()

    except APIError as e:
        st.error("❌ Błąd podczas indeksowania")

        with st.expander("🔧 Szczegóły błędu", expanded=False):
            st.write(f"**Status:** {e.status_code}")
            st.write(f"**Komunikat:** {e.message}")

            if e.status_code == 400:
                st.write("**Możliwe przyczyny:**")
                st.write("- Brak przesłanych plików")
                st.write("- Indeksowanie już w toku")
                st.write("- Nieprawidłowe ID quizu")

    except Exception as e:
        st.error(f"❌ Nieoczekiwany błąd: {str(e)}")
