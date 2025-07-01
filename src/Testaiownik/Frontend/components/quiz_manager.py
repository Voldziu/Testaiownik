import streamlit as st
from utils.session_manager import get_quiz_id, get_user_id
from services.api_client import get_api_client
from typing import List, Dict, Any

def render_quiz_questions():
    """Render active quiz questions with answer submission"""
    quiz_id = get_quiz_id()
    if not quiz_id:
        st.error("❌ Brak ID quizu. Wróć do tworzenia quizu.")
        return

    # Initialize session state for quiz
    if "quiz_state" not in st.session_state:
        st.session_state["quiz_state"] = {
            "current_question": None,
            "answered": False,
            "answer_result": None,
            "selected_choices": [],
            "loading": False
        }
        clear_quiz_cache()

    # Load current question
    load_current_question(quiz_id)
    
    # Render based on current state
    if st.session_state["quiz_state"]["current_question"]:
        render_question()
    else:
        st.info("🔄 Ładowanie pytania...")

def load_current_question(quiz_id: str):
    """Load current question from API"""
    try:
        current_question = st.session_state["quiz_state"]["current_question"]
        answered = st.session_state["quiz_state"]["answered"]
        loading = st.session_state["quiz_state"]["loading"]
        
        
        if current_question and not answered and not loading:
            return  
        
        if not loading:
            st.session_state["quiz_state"]["loading"] = True
            
            api_client = get_api_client(get_user_id())
            current_data = api_client.get_current_question(quiz_id)

            if current_data:
                # Check if it's directly the question data
                question_data = None
                
                if 'id' in current_data and 'question_text' in current_data:
                    question_data = current_data
                
                elif 'current_question' in current_data:
                    question_data = current_data['current_question']
                
                elif 'question' in current_data:
                    question_data = current_data['question']
                
                if question_data:
                    if 'id' not in question_data:
                        st.error("❌ Question data missing 'id' field!")
                        return
                    
                    if 'question_text' not in question_data:
                        st.error("❌ Question data missing 'question_text' field!")
                        return
                else:
                    st.error("❌ No question data found in response!")
                    return
                
                # Reset state for new question
                if (st.session_state["quiz_state"]["current_question"] is None or 
                    st.session_state["quiz_state"]["current_question"]["id"] != question_data["id"]):
                    st.session_state["quiz_state"] = {
                        "current_question": question_data,
                        "answered": False,
                        "answer_result": None,
                        "selected_choices": [],
                        "loading": False
                    }
                elif not st.session_state["quiz_state"]["answered"]:
                    st.session_state["quiz_state"]["current_question"] = question_data
                    st.session_state["quiz_state"]["loading"] = False
                    
    except Exception as e:
        st.session_state["quiz_state"]["loading"] = False
        st.error(f"❌ Błąd podczas ładowania pytania: {str(e)}")

def render_question():
    """Render current question with answer options"""
    question_data = st.session_state["quiz_state"]["current_question"]
    
    if not question_data:
        return
    
    quiz_id = get_quiz_id()
    current_question_num = 1
    total_questions = 1
    progress_percentage = 0
    
    # Cache status
    status_cache_key = f"quiz_status_{quiz_id}"
    if status_cache_key not in st.session_state:
        try:
            api_client = get_api_client(get_user_id())
            status_data = api_client.get_quiz_status(quiz_id)
            
            if status_data and 'quiz_execution' in status_data:
                quiz_exec = status_data['quiz_execution']
                current_question_num = quiz_exec.get('current_index', 0) + 1  
                total_questions = quiz_exec.get('total_questions', 1)
                progress_percentage = quiz_exec.get('progress_percentage', 0)
            
            # save to cache
            st.session_state[status_cache_key] = {
                'current_question_num': current_question_num,
                'total_questions': total_questions,
                'progress_percentage': progress_percentage
            }
            
        except Exception as e:
            st.warning(f"Nie udało się pobrać statusu quizu: {str(e)}")
    else:
        # cached data
        cached_status = st.session_state[status_cache_key]
        current_question_num = cached_status['current_question_num']
        total_questions = cached_status['total_questions']
        progress_percentage = cached_status['progress_percentage']
    
    # Quiz header with progress
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        st.title("📝 Quiz")
    with col2:
        st.metric("Pytanie", f"{current_question_num}/{total_questions}")
    with col3:
        st.metric("Postęp", f"{progress_percentage:.0f}%")

    # Progress bar
    progress_value = progress_percentage / 100 if progress_percentage <= 100 else 1.0
    st.progress(progress_value)
    st.divider()
    
    # Question content
    st.subheader(f"❓ Pytanie {current_question_num}")
    st.write(question_data.get('question_text', 'Brak treści pytania'))
    
    # Answer options
    if not st.session_state["quiz_state"]["answered"]:
        render_answer_options(question_data)
    else:
        render_answer_feedback(question_data)

def clear_quiz_cache():
    """Clear quiz-related cache"""
    keys_to_remove = [key for key in st.session_state.keys() 
                    if key.startswith('quiz_status_')]
    for key in keys_to_remove:
        del st.session_state[key]


def render_answer_options(question_data: Dict[str, Any]):
    """Render answer options for user selection"""
    choices = question_data.get('choices', [])
    is_multi_choice = question_data.get('is_multi_choice', False)
    
    # Safely get question_id (check different possible field names)
    question_id = question_data.get('id') or question_data.get('question_id')
    
    if not question_id:
        st.error("❌ Brak ID pytania!")
        return
    
    if not choices:
        st.error("❌ Brak opcji odpowiedzi!")
        return
    
    # Display appropriate header based on question type
    if is_multi_choice:
        st.subheader("💭 Wybierz odpowiedzi (możesz wybrać więcej niż jedną):")
    else:
        st.subheader("💭 Wybierz odpowiedź:")
    
    selected_choices = []
    
    if is_multi_choice:
        # Multiple choice - use checkboxes
        for idx, choice in enumerate(choices):
            is_selected = st.checkbox(
                choice['text'], 
                key=f"choice_{question_id}_{idx}"
            )
            
            if is_selected:
                selected_choices.append(idx)
        
    else:
        # Single choice - use radio buttons
        choice_texts = [choice['text'] for choice in choices]
        
        selected_index = st.radio(
            "Wybierz odpowiedź:",
            options=range(len(choices)),
            format_func=lambda x: choice_texts[x],
            key=f"radio_{question_id}",
            index=None 
        )
        
        if selected_index is not None:
            selected_choices = [selected_index]

    # Display submit button
    if st.button("✅ Zatwierdź odpowiedź", key=f"submit_{question_id}", use_container_width=True):
        if not selected_choices:
            st.warning("⚠️ Wybierz przynajmniej jedną odpowiedź!")
        else:
            submit_answer(question_id, selected_choices)
            st.session_state["quiz_state"]["answered"] = True
            render_answer_feedback(question_data)


def submit_answer(question_id: str, selected_choices: List[int]):
    """Submit answer to API"""
    quiz_id = get_quiz_id()
    
    try:
        st.session_state["quiz_state"]["loading"] = True
        
        with st.spinner("Sprawdzanie odpowiedzi..."):
            api_client = get_api_client(get_user_id())
            
            result = api_client.submit_answer(
                quiz_id=quiz_id,
                question_id=question_id,
                selected_choices=selected_choices  # Send selected_choices as integers (indices)
            )
            
            # Update session state with result
            st.session_state["quiz_state"]["answered"] = True
            st.session_state["quiz_state"]["answer_result"] = result
            st.session_state["quiz_state"]["selected_choices"] = selected_choices
            st.session_state["quiz_state"]["loading"] = False
            
            clear_quiz_cache()

            
    except Exception as e:
        st.session_state["quiz_state"]["loading"] = False
        st.error(f"❌ Błąd podczas wysyłania odpowiedzi: {str(e)}")

def render_answer_feedback(question_data: Dict[str, Any]):
    """Render feedback after answer submission"""

    result = st.session_state["quiz_state"]["answer_result"]

    
    if not result:
        return
    
    # Show selected answer(s)
    st.subheader("📋 Twoja odpowiedź:")
    choices = question_data.get('choices', [])
    selected_choice_ids = st.session_state["quiz_state"]["selected_choices"]
    
    for idx, choice in enumerate(choices):
        if idx in selected_choice_ids:
            st.write(f"➡️ {choice['text']}")
    
    st.divider()
    
   
    is_correct = result.get('correct', False)
    
    if is_correct:
        st.success("🎉 Brawo! Odpowiedź prawidłowa!")
    else:
        st.error("❌ Niestety, odpowiedź nieprawidłowa")
    
    st.subheader("✅ Prawidłowa odpowiedź:")
    
    correct_answers = result.get('correct_answers', [])
    if correct_answers:
        for correct_answer in correct_answers:
            st.success(f"✓ {correct_answer}")
    else:
        for choice in choices:
            if choice.get('is_correct', False):
                st.success(f"✓ {choice['text']}")
    
    explanation_data = None
    try:
        explanation_data = get_api_client(get_user_id()).get_explanation(
            quiz_id=get_quiz_id(),
            question_id=question_data['id']
        )
        
        explanation = explanation_data.get('explanation')
        source_chunks = explanation_data.get('source_chunks', [])
        
        # If explanation is not available, fallback to a message
        if not explanation:
            st.warning("❌ Brak wyjaśnienia dla tej odpowiedzi.")
        else:
            # Expander for explanation
            with st.expander("💡 Wyjaśnienie:", expanded=False):
                st.info(explanation)

  

                # Display source chunks (file, page, slide, chunk text)
                if source_chunks:
                    for source_chunk in source_chunks:
                        source = source_chunk.get('source', 'Brak źródła')
                        page = source_chunk.get('page', None)

                        st.write(f"📄 Źródło: {source}")

                        if page is not None:
                            st.write(f"📄 Strona: {page}")
                        
        
                        # Optionally, display the chunk text (relevant text extracted)
                        chunk_text = source_chunk.get('text', 'Brak wyciągu')
                        if chunk_text:
                            st.write(f"📖 Wyciąg z tekstu: {chunk_text}")
            
    except Exception as e:
        st.warning(f"Nie udało się pobrać wyjaśnienia: {str(e)}")
        
        st.divider()
        
    progress = result.get('progress', {})
    if progress:
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Aktualny wynik", f"{progress.get('correct', 0)}/{progress.get('answered', 0)}")
        with col2:
            answered = progress.get('answered', 0)
            if answered > 0:
                percentage = (progress.get('correct', 0) / answered) * 100
                st.metric("Procent poprawnych", f"{percentage:.1f}%")
    
    st.divider()
    
    # Navigation buttons
    if st.button("➡️ Następne pytanie", use_container_width=True):
        # Reset state for next question
        st.session_state["quiz_state"]["answered"] = False
        st.session_state["quiz_state"]["answer_result"] = None
        st.session_state["quiz_state"]["selected_choices"] = []
        st.session_state["quiz_state"]["current_question"] = None
        clear_quiz_cache()
        st.rerun()

# Utility function to check if quiz is completed
def is_quiz_completed(question_data: Dict[str, Any]) -> bool:
    """Check if quiz is completed"""
    current_q = question_data.get('current_question_number', 0)
    total_q = question_data.get('total_questions', 0)
    return current_q >= total_q