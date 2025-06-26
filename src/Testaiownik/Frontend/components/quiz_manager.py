import streamlit as st
from utils.session_manager import get_quiz_id, get_user_id
from services.api_client import get_api_client
from typing import List, Dict, Any
import time

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
        if not st.session_state["quiz_state"]["loading"]:
            api_client = get_api_client(get_user_id())
            current_data = api_client.get_current_question(quiz_id)
            
            if current_data:
                # Reset state for new question
                if (st.session_state["quiz_state"]["current_question"] is None or 
                    st.session_state["quiz_state"]["current_question"]["question_id"] != current_data["question_id"]):
                    st.session_state["quiz_state"] = {
                        "current_question": current_data,
                        "answered": False,
                        "answer_result": None,
                        "selected_choices": [],
                        "loading": False
                    }
                elif not st.session_state["quiz_state"]["answered"]:
                    st.session_state["quiz_state"]["current_question"] = current_data
                    
    except Exception as e:
        st.error(f"❌ Błąd podczas ładowania pytania: {str(e)}")

def render_question():
    """Render current question with answer options"""
    question_data = st.session_state["quiz_state"]["current_question"]
    
    if not question_data:
        return
    
    # Quiz header with progress
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        st.title("📝 Quiz")
    with col2:
        st.metric("Pytanie", f"{question_data.get('current_question_number', '?')}/{question_data.get('total_questions', '?')}")
    with col3:
        progress = question_data.get('current_question_number', 0) / question_data.get('total_questions', 1)
        st.metric("Postęp", f"{int(progress * 100)}%")
    
    # Progress bar
    st.progress(progress)
    st.divider()
    
    # Question content
    st.subheader(f"❓ Pytanie {question_data.get('current_question_number', '?')}")
    st.write(question_data.get('question_text', 'Brak treści pytania'))
    
    # Answer options
    if not st.session_state["quiz_state"]["answered"]:
        render_answer_options(question_data)
    else:
        render_answer_feedback(question_data)

def render_answer_options(question_data: Dict[str, Any]):
    """Render answer options for user selection"""
    st.subheader("💭 Wybierz odpowiedź:")
    
    choices = question_data.get('choices', [])
    question_type = question_data.get('question_type', 'single')
    
    if question_type == 'single':
        # Single choice question
        selected_choice = st.radio(
            "Odpowiedzi:",
            options=range(len(choices)),
            format_func=lambda x: f"{chr(65 + x)}. {choices[x]['text']}" if x < len(choices) else "",
            key=f"question_choice_{question_data['question_id']}"
        )
        
        if st.button("✅ Zatwierdź odpowiedź", type="primary", use_container_width=True):
            if selected_choice is not None:
                submit_answer(question_data['question_id'], [choices[selected_choice]['choice_id']])
            else:
                st.warning("⚠️ Wybierz odpowiedź przed zatwierdzeniem!")
                
    elif question_type == 'multiple':
        # Multiple choice question
        st.write("*Możesz wybrać więcej niż jedną odpowiedź*")
        
        selected_choices = []
        for idx, choice in enumerate(choices):
            if st.checkbox(f"{chr(65 + idx)}. {choice['text']}", key=f"choice_{choice['choice_id']}"):
                selected_choices.append(choice['choice_id'])
        
        if st.button("✅ Zatwierdź odpowiedzi", type="primary", use_container_width=True):
            if selected_choices:
                submit_answer(question_data['question_id'], selected_choices)
            else:
                st.warning("⚠️ Wybierz przynajmniej jedną odpowiedź!")
    
    else:
        # True/False question
        selected = st.radio(
            "Odpowiedź:",
            options=[True, False],
            format_func=lambda x: "✅ Prawda" if x else "❌ Fałsz",
            key=f"tf_question_{question_data['question_id']}"
        )
        
        if st.button("✅ Zatwierdź odpowiedź", type="primary", use_container_width=True):
            # Find the choice that matches the selected boolean
            choice_id = None
            for choice in choices:
                if choice.get('is_correct') == selected:
                    choice_id = choice['choice_id']
                    break
            
            if choice_id:
                submit_answer(question_data['question_id'], [choice_id])

def submit_answer(question_id: str, selected_choices: List[str]):
    """Submit answer to API"""
    quiz_id = get_quiz_id()
    
    try:
        st.session_state["quiz_state"]["loading"] = True
        
        with st.spinner("Sprawdzanie odpowiedzi..."):
            api_client = get_api_client(get_user_id())
            
            result = api_client.submit_answer(
                quiz_id=quiz_id,
                question_id=question_id,
                selected_choices=selected_choices
            )
            
            # Update session state with result
            st.session_state["quiz_state"]["answered"] = True
            st.session_state["quiz_state"]["answer_result"] = result
            st.session_state["quiz_state"]["selected_choices"] = selected_choices
            st.session_state["quiz_state"]["loading"] = False
            
            st.rerun()
            
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
    
    for choice in choices:
        if choice['choice_id'] in selected_choice_ids:
            st.write(f"➡️ {choice['text']}")
    
    st.divider()
    
    # Show result
    is_correct = result.get('is_correct', False)
    
    if is_correct:
        st.success("🎉 Brawo! Odpowiedź prawidłowa!")
        st.balloons()
    else:
        st.error("❌ Niestety, odpowiedź nieprawidłowa")
    
    # Show correct answer(s)
    st.subheader("✅ Prawidłowa odpowiedź:")
    for choice in choices:
        if choice.get('is_correct', False):
            st.success(f"✓ {choice['text']}")
    
    # Show explanation if available
    explanation = result.get('explanation') or question_data.get('explanation')
    if explanation:
        st.subheader("💡 Wyjaśnienie:")
        st.info(explanation)
    
    # Show score if available
    if 'current_score' in result:
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Aktualny wynik", f"{result['current_score']}/{result.get('questions_answered', 0)}")
        with col2:
            if result.get('questions_answered', 0) > 0:
                percentage = (result['current_score'] / result['questions_answered']) * 100
                st.metric("Procent poprawnych", f"{percentage:.1f}%")
    
    st.divider()
    
    # Navigation buttons
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("➡️ Następne pytanie", type="primary", use_container_width=True):
            # Reset state for next question
            st.session_state["quiz_state"]["answered"] = False
            st.session_state["quiz_state"]["answer_result"] = None
            st.session_state["quiz_state"]["selected_choices"] = []
            st.session_state["quiz_state"]["current_question"] = None
            st.rerun()
    
    with col2:
        if st.button("📊 Podsumowanie", use_container_width=True):
            # Navigate to results (you might want to implement this)
            st.info("🔄 Przejście do podsumowania...")

# Utility function to check if quiz is completed
def is_quiz_completed(question_data: Dict[str, Any]) -> bool:
    """Check if quiz is completed"""
    current_q = question_data.get('current_question_number', 0)
    total_q = question_data.get('total_questions', 0)
    return current_q >= total_q