import streamlit as st
import requests
import uuid
import time

# Ustawienia URL backendu
BASE_URL = "http://localhost:8000"  # Zmien na odpowiedni URL backendu

# Funkcja do generowania losowego user_id (UUID)
def generate_user_id():
    return str(uuid.uuid4())  # Generowanie unikalnego identyfikatora użytkownika

# Funkcja do generowania quizu
def generate_quiz():
    st.title("Generowanie Quizu")
    
    if "user_id" not in st.session_state:
        st.session_state.user_id = generate_user_id()  # Generujemy losowy user_id, jeśli go nie ma
    
    st.write(f"Twoje UserID: {st.session_state.user_id}")

    if "quiz_id" not in st.session_state:  # Sprawdzamy, czy quiz już został wygenerowany
        if st.button("Stwórz nowy quiz"):
            # Spróbuj różnych formatów nagłówka
            headers = {
                "X-User-ID": st.session_state.user_id,
                "Authorization": f"Bearer {st.session_state.user_id}",  # Dodatkowy format
                "User-ID": st.session_state.user_id,  # Alternatywny nagłówek
            }
            
            response = requests.post(
                f"{BASE_URL}/api/quiz/create", 
                headers=headers
            )
            
            if response.status_code == 200:
                quiz = response.json()
                st.session_state.quiz_id = quiz['quiz_id']
                st.session_state.uploaded = False  
                st.session_state.indexing_started = False
                st.session_state.topics_generated = False
                st.success(f"Quiz został stworzony! ID quizu: {quiz['quiz_id']}")
                # Automatyczne przejście do uploadu
                st.rerun()
            else:
                st.error(f"Wystąpił problem podczas tworzenia quizu: {response.text}")
                # Debug info
                st.write("Status code:", response.status_code)
                st.write("Response headers:", dict(response.headers))
                
                # Dodatkowe informacje debugowe
                if response.status_code == 500:
                    st.write("🔧 **Pomoc w debugowaniu:**")
                    st.write("- Sprawdź logi serwera backendu")
                    st.write("- Błąd może być w funkcji `get_user_id()` lub `validate_quiz_access()`")
                    st.write("- Sprawdź czy backend poprawnie odbiera nagłówek X-User-ID")
                    
                    # Pokaż co wysyłamy
                    st.write("**Wysyłane dane:**")
                    st.json({
                        "URL": f"{BASE_URL}/api/quiz/create",
                        "Headers": headers,
                        "User-ID": st.session_state.user_id
                    })
    else:
        st.write(f"Stworzony quiz ID: {st.session_state.quiz_id}")
        return True  # Quiz już istnieje

# Funkcja do przesyłania plików (Drag & Drop)
def upload_files():
    st.title("Upload plików do quizu")
    
    if "quiz_id" not in st.session_state:
        st.error("Najpierw musisz stworzyć quiz.")
        return False
    
    quiz_id = st.session_state.quiz_id

    uploaded_files = st.file_uploader("Wybierz pliki do uploadu", type=["pdf", "docx", "txt", "pptx"], accept_multiple_files=True)
    
    files_uploaded = False
    
    if uploaded_files:
        st.write(f"Liczba wybranych plików: {len(uploaded_files)}")
        for file in uploaded_files:
            st.write(f"Plik: {file.name}")
        
        if st.button("Prześlij pliki"):
            files = [("files", (file.name, file)) for file in uploaded_files]
            headers = {
                "X-User-ID": st.session_state.user_id,
                "Authorization": f"Bearer {st.session_state.user_id}",
                "User-ID": st.session_state.user_id,
            }
            
            response = requests.post(
                f"{BASE_URL}/api/documents/{quiz_id}/upload", 
                files=files, 
                headers=headers
            )
            
            if response.status_code == 200:
                st.session_state.uploaded = True
                st.success("Pliki zostały przesłane!")
                st.rerun()
            else:
                st.error(f"Wystąpił problem przy przesyłaniu plików: {response.text}")
        
        files_uploaded = True
    
    # Sprawdź czy pliki zostały już przesłane
    if "uploaded" in st.session_state and st.session_state.uploaded:
        st.success("✅ Pliki zostały już przesłane!")
        files_uploaded = True
    
    return files_uploaded

# Funkcja do indeksowania plików
def index_files(quiz_id):
    if "uploaded" not in st.session_state or not st.session_state.uploaded:
        return False
    
    if "indexing_started" not in st.session_state or not st.session_state.indexing_started:
        if st.button("🔄 Zaindeksuj pliki i przejdź dalej", key="index_button"):
            headers = {
                "X-User-ID": st.session_state.user_id,
                "Authorization": f"Bearer {st.session_state.user_id}",
                "User-ID": st.session_state.user_id,
            }
            
            response = requests.post(
                f"{BASE_URL}/api/documents/{quiz_id}/index", 
                headers=headers
            )
            
            if response.status_code == 200:
                st.session_state.indexing_started = True
                st.success("Pliki zostały zindeksowane!")
                st.rerun()
            else:
                st.error(f"Wystąpił problem przy indeksowaniu plików: {response.text}")
                return False
    
    return st.session_state.get("indexing_started", False)

# Funkcja do sprawdzania statusu indeksowania
def check_indexing_status(quiz_id):
    headers = {
        "X-User-ID": st.session_state.user_id,
        "Authorization": f"Bearer {st.session_state.user_id}",
        "User-ID": st.session_state.user_id,
    }
    
    response = requests.get(
        f"{BASE_URL}/api/documents/{quiz_id}/stats", 
        headers=headers
    )
    
    if response.status_code == 200:
        stats = response.json()
        total_documents = stats["total_documents"]
        indexed_documents = stats["indexed_documents"]
        indexing_progress = stats["indexing_progress"]

        st.write(f"📊 Całkowita liczba dokumentów: {total_documents}")
        st.write(f"✅ Liczba zaindeksowanych dokumentów: {indexed_documents}")
        st.write(f"📈 Postęp indeksowania: {indexing_progress}%")
        
        return indexing_progress == 100
    else:
        st.error(f"Wystąpił problem podczas sprawdzania statusu indeksowania: {response.text}")
        return False

# Funkcja do dodawania nowego tematu
def add_new_topic(quiz_id):
    st.subheader("➕ Dodaj nowy temat")
    
    with st.expander("Dodaj własny temat", expanded=False):
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            new_topic_name = st.text_input("Nazwa tematu", key="new_topic_name")
        
        with col2:
            new_topic_weight = st.slider("Waga", min_value=0.1, max_value=10.0, value=1.0, key="new_topic_weight")
        
        with col3:
            st.write("")  # Spacer
            st.write("")  # Spacer
            if st.button("➕ Dodaj temat", key="add_new_topic", use_container_width=True):
                if new_topic_name.strip():
                    headers = {
                        "X-User-ID": st.session_state.user_id,
                        "Authorization": f"Bearer {st.session_state.user_id}",
                        "User-ID": st.session_state.user_id,
                    }
                    
                    response = requests.post(
                        f"{BASE_URL}/api/topics/{quiz_id}/add",
                        json={
                            "topic_name": new_topic_name.strip(),
                            "weight": new_topic_weight
                        },
                        headers=headers
                    )
                    
                    if response.status_code == 200:
                        st.success(f"✅ Temat '{new_topic_name}' został dodany!")
                        # Wyczyść formularz poprzez usunięcie z session_state
                        if "new_topic_name" in st.session_state:
                            del st.session_state["new_topic_name"]
                        if "new_topic_weight" in st.session_state:
                            del st.session_state["new_topic_weight"]
                        time.sleep(1)  # Krótka pauza dla UX
                        st.rerun()
                    else:
                        st.error(f"❌ Wystąpił problem przy dodawaniu tematu: {response.text}")
                        # Debug info dla dodawania tematu
                        st.write("Status code:", response.status_code)
                else:
                    st.warning("⚠️ Nazwa tematu nie może być pusta!")

# Funkcja do wyświetlania tematów
def display_topics(quiz_id):
    st.title("Sugerowane Tematy")
    
    # Dodaj funkcjonalność dodawania nowego tematu
    add_new_topic(quiz_id)
    
    st.divider()
    
    # Inicjalizacja stanu edycji jeśli nie istnieje
    if "editing_topic" not in st.session_state:
        st.session_state.editing_topic = None
    
    headers = {
        "X-User-ID": st.session_state.user_id,
        "Authorization": f"Bearer {st.session_state.user_id}",
        "User-ID": st.session_state.user_id,
    }
    
    response = requests.get(
        f"{BASE_URL}/api/topics/{quiz_id}/status", 
        headers=headers
    )
    
    if response.status_code == 200:
        topics = response.json().get("suggested_topics", [])
        if topics:
            st.subheader(f"📋 Lista tematów ({len(topics)})")
            for topic in topics:
                # Sprawdź czy ten temat jest aktualnie edytowany
                is_editing = st.session_state.editing_topic == topic['topic']
                
                if is_editing:
                    # Tryb edycji
                    st.write(f"**Edytujesz temat:** {topic['topic']}")
                    
                    # Inicjalizuj wartości edycji jeśli nie istnieją
                    if f"edit_name_{topic['topic']}" not in st.session_state:
                        st.session_state[f"edit_name_{topic['topic']}"] = topic['topic']
                    if f"edit_weight_{topic['topic']}" not in st.session_state:
                        st.session_state[f"edit_weight_{topic['topic']}"] = topic['weight']
                    
                    col1, col2 = st.columns([2, 1])
                    
                    with col1:
                        new_name = st.text_input(
                            "Nowa nazwa tematu", 
                            value=st.session_state[f"edit_name_{topic['topic']}"],
                            key=f"name_input_{topic['topic']}"
                        )
                        st.session_state[f"edit_name_{topic['topic']}"] = new_name
                        
                        new_weight = st.slider(
                            "Nowa waga", 
                            min_value=0.1, 
                            max_value=10.0, 
                            value=st.session_state[f"edit_weight_{topic['topic']}"],
                            key=f"weight_input_{topic['topic']}"
                        )
                        st.session_state[f"edit_weight_{topic['topic']}"] = new_weight
                    
                    with col2:
                        if st.button("Zatwierdź", key=f"confirm_{topic['topic']}"):
                            update_topic(quiz_id, topic['topic'], new_name, new_weight)
                            # Wyczyść stan edycji
                            st.session_state.editing_topic = None
                            del st.session_state[f"edit_name_{topic['topic']}"]
                            del st.session_state[f"edit_weight_{topic['topic']}"]
                            st.rerun()
                        
                        if st.button("Anuluj", key=f"cancel_{topic['topic']}"):
                            # Wyczyść stan edycji
                            st.session_state.editing_topic = None
                            if f"edit_name_{topic['topic']}" in st.session_state:
                                del st.session_state[f"edit_name_{topic['topic']}"]
                            if f"edit_weight_{topic['topic']}" in st.session_state:
                                del st.session_state[f"edit_weight_{topic['topic']}"]
                            st.rerun()
                else:
                    # Tryb normalny (wyświetlanie)
                    col1, col2, col3 = st.columns([3, 1, 1])
                    
                    with col1:
                        st.write(f"- {topic['topic']} (waga: {topic['weight']})")
                    
                    with col2:
                        if st.button("Edytuj", key=f"edit_{topic['topic']}"):
                            st.session_state.editing_topic = topic['topic']
                            st.rerun()
                    
                    with col3:
                        if st.button("Usuń", key=f"delete_{topic['topic']}"):
                            delete_topic(quiz_id, topic['topic'])
                            st.rerun()
                
                st.divider()
        else:
            st.write("Brak sugerowanych tematów.")
    else:
        st.error(f"Wystąpił problem podczas pobierania tematów: {response.text}")

# Funkcja do aktualizacji tematu
def update_topic(quiz_id, old_name, new_name, new_weight):
    headers = {
        "X-User-ID": st.session_state.user_id,
        "Authorization": f"Bearer {st.session_state.user_id}",
        "User-ID": st.session_state.user_id,
    }
    
    response = requests.patch(
        f"{BASE_URL}/api/topics/{quiz_id}/topic/{old_name}",
        json={"new_name": new_name, "new_weight": new_weight},
        headers=headers
    )
    if response.status_code == 200:
        st.success(f"Temat '{old_name}' został zaktualizowany.")
    else:
        st.error(f"Wystąpił problem przy aktualizacji tematu: {response.text}")

# Funkcja do usuwania tematu
def delete_topic(quiz_id, topic_name):
    headers = {
        "X-User-ID": st.session_state.user_id,
        "Authorization": f"Bearer {st.session_state.user_id}",
        "User-ID": st.session_state.user_id,
    }
    
    response = requests.delete(
        f"{BASE_URL}/api/topics/{quiz_id}/topic/{topic_name}",
        headers=headers
    )
    if response.status_code == 200:
        st.success(f"Temat '{topic_name}' został usunięty.")
    else:
        st.error(f"Wystąpił problem przy usuwaniu tematu: {response.text}")

# Funkcja do generowania tematów (podtematów)
def generate_topics():
    st.title("Generowanie tematów")
    
    if "quiz_id" not in st.session_state:
        st.error("Najpierw musisz stworzyć quiz.")
        return

    quiz_id = st.session_state.quiz_id

    num_topics = st.slider("Wybierz liczbę podtematów", min_value=1, max_value=50, value=25)
    st.write(f"Liczba podtematów: {num_topics}")

    if st.button("Zatwierdź i uruchom generowanie tematów"):
        headers = {
            "X-User-ID": st.session_state.user_id,
            "Authorization": f"Bearer {st.session_state.user_id}",
            "User-ID": st.session_state.user_id,
        }
        
        response = requests.post(
            f"{BASE_URL}/api/topics/{quiz_id}/start",
            json={"desired_topic_count": num_topics},
            headers=headers
        )
        
        if response.status_code == 200:
            st.success("Generowanie tematów zostało rozpoczęte!")
            st.session_state.topics_generated = True
            st.rerun()
        else:
            st.error(f"Wystąpił problem przy generowaniu tematów: {response.text}")
    
    # Wyświetlaj tematy jeśli zostały wygenerowane
    if "topics_generated" in st.session_state and st.session_state.topics_generated:
        display_topics(quiz_id)

# Główna funkcjonalność aplikacji z poprawionym flow
def main():
    # Krok 1: Tworzenie quizu
    if "quiz_id" not in st.session_state:
        generate_quiz()
        return
    
    # Krok 2: Upload plików
    if "uploaded" not in st.session_state or not st.session_state.uploaded:
        files_ready = upload_files()
        
        # Przycisk "Dalej" w lewym dolnym rogu
        if files_ready and "uploaded" in st.session_state and st.session_state.uploaded:
            with st.container():
                col1, col2, col3 = st.columns([1, 1, 1])
                with col1:
                    if index_files(st.session_state.quiz_id):
                        st.rerun()
        return
    
    # Krok 3: Indeksowanie (jeśli nie zostało jeszcze uruchomione)
    if "indexing_started" not in st.session_state or not st.session_state.indexing_started:
        st.title("Indeksowanie plików")
        st.info("Pliki zostały przesłane. Teraz możesz je zaindeksować.")
        
        # Przycisk indeksowania
        if index_files(st.session_state.quiz_id):
            st.rerun()
        return
    
    # Krok 4: Sprawdzanie statusu indeksowania
    if st.session_state.get("indexing_started", False):
        st.title("Status indeksowania")
        indexing_complete = check_indexing_status(st.session_state.quiz_id)
        
        if not indexing_complete:
            if st.button("Odśwież status"):
                st.rerun()
            return
    
    # Krok 5: Generowanie i edycja tematów
    generate_topics()

if __name__ == "__main__":
    main()