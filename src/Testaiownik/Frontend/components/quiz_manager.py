from datetime import datetime
import time
import streamlit as st
from utils.session_manager import get_quiz_id, get_user_id
from services.api_client import get_api_client
from typing import List, Dict, Any

def render_quiz_questions():
    """Render active quiz questions with enhanced error handling"""
    quiz_id = get_quiz_id()
    if not quiz_id:
        st.error("❌ Brak ID quizu. Wróć do tworzenia quizu.")
        return

    # Initialize quiz state
    if "quiz_state" not in st.session_state:
        st.session_state["quiz_state"] = {
            "current_question": None,
            "answered": False,
            "answer_result": None,
            "selected_choices": [],
            "loading": False,
            "completed": False,
            "start_time": datetime.now().isoformat()
        }
        clear_quiz_cache()

    # Check if quiz is completed
    if st.session_state["quiz_state"]["completed"]:
        render_mastery_summary()
        return

    # ENHANCED: Check if quiz has started before loading questions
    try:
        # Try to get quiz progress first to check if quiz exists/started
        progress_data = get_quiz_progress(quiz_id, force_refresh=False)
        
        # If we can get progress, quiz has started
        load_current_question(quiz_id)
        
        # Render based on state
        if st.session_state["quiz_state"]["current_question"]:
            render_question()
        else:
            # Check if quiz is completed when no question available
            if is_quiz_completed_by_progress(progress_data):
                st.session_state["quiz_state"]["completed"] = True
                st.rerun()
            else:
                st.info("🔄 Ładowanie pytania...")
                
    except Exception as e:
        error_msg = str(e).lower()
        if "quiz has not started yet" in error_msg:
            st.info("🔄 Quiz nie został jeszcze uruchomiony. Przechodzę do konfiguracji pytań.")
            
            # FIXED: Automatically redirect to questions manager instead of just showing info
            st.session_state["app_phase"] = "questions_manager"
            time.sleep(0.5)  # Small delay to show the message
            st.rerun()
            
        elif "no current question available" in error_msg:
            st.info("🔄 Brak dostępnych pytań. Przechodzę do konfiguracji pytań.")
            
            # FIXED: Automatically redirect to questions manager
            st.session_state["app_phase"] = "questions_manager"
            time.sleep(0.5)
            st.rerun()
            
        else:
            st.error(f"❌ Błąd podczas ładowania quizu: {str(e)}")
            
            # FIXED: For other errors, also provide option to go back to questions manager
            col1, col2 = st.columns(2)
            with col1:
                if st.button("⬅️ Wróć do konfiguracji pytań"):
                    st.session_state["app_phase"] = "questions_manager"
                    st.rerun()
            with col2:
                if st.button("🏠 Menu główne"):
                    return_to_main_menu()



def load_current_question(quiz_id: str):
    """Load current question from API with enhanced error handling"""
    try:
        # Sprawdzenie, czy quiz jest zakończony
        if st.session_state["quiz_state"].get("completed", False):
            return

        current_question = st.session_state["quiz_state"]["current_question"]
        answered = st.session_state["quiz_state"]["answered"]
        loading = st.session_state["quiz_state"]["loading"]

        # ENHANCED: Check if quiz has started before trying to get progress
        try:
            progress_data = get_quiz_progress(quiz_id, force_refresh=False)
            total_questions = progress_data.get('total_questions', 0)
            unique_answered = progress_data.get('unique_answered', 0)
            remaining_questions = total_questions - unique_answered
        except Exception as progress_error:
            # If we can't get progress, assume quiz hasn't started
            error_msg = str(progress_error).lower()
            if "quiz has not started yet" in error_msg:
                st.info("🔄 Quiz nie został jeszcze uruchomiony...")
                return
            else:
                # Re-raise other errors
                raise progress_error

        # If all questions answered, mark as completed
        if remaining_questions == 0:
            st.session_state["quiz_state"]["completed"] = True
            return

        # Don't load new question if current one is answered but feedback not shown
        if current_question and answered and not loading:
            return

        # Don't load new question if we have one but haven't answered yet
        if current_question and not answered and not loading:
            return

        # Only load new question if we don't have one or we're loading
        if not loading and not answered:
            st.session_state["quiz_state"]["loading"] = True
            api_client = get_api_client(get_user_id())
            
            try:
                current_data = api_client.get_current_question(quiz_id)
            except Exception as question_error:
                error_msg = str(question_error).lower()
                if "no current question available" in error_msg or "quiz has not started yet" in error_msg:
                    st.info("🔄 Brak dostępnych pytań. Quiz może nie być jeszcze uruchomiony.")
                    st.session_state["quiz_state"]["loading"] = False
                    return
                else:
                    raise question_error

            if current_data:
                # Check if question data is valid
                question_data = None
                if 'id' in current_data and 'question_text' in current_data:
                    question_data = current_data
                elif 'current_question' in current_data:
                    question_data = current_data['current_question']
                elif 'question' in current_data:
                    question_data = current_data['question']

                if question_data:
                    if 'id' not in question_data:
                        st.error("❌ Pytanie nie zawiera 'id'!")
                        st.session_state["quiz_state"]["loading"] = False
                        return

                    if 'question_text' not in question_data:
                        st.error("❌ Pytanie nie zawiera 'question_text'!")
                        st.session_state["quiz_state"]["loading"] = False
                        return
                else:
                    # No questions - quiz completed
                    st.session_state["quiz_state"]["completed"] = True
                    st.session_state["quiz_state"]["loading"] = False
                    return

                # Reset state for new question
                if (st.session_state["quiz_state"]["current_question"] is None or
                        st.session_state["quiz_state"]["current_question"]["id"] != question_data["id"]):
                    st.session_state["quiz_state"]["current_question"] = question_data
                    st.session_state["quiz_state"]["answered"] = False
                    st.session_state["quiz_state"]["answer_result"] = None
                    st.session_state["quiz_state"]["selected_choices"] = []
                    st.session_state["quiz_state"]["loading"] = False
                elif not st.session_state["quiz_state"]["answered"]:
                    st.session_state["quiz_state"]["current_question"] = question_data
                    st.session_state["quiz_state"]["loading"] = False
            else:
                # No data - quiz completed
                st.session_state["quiz_state"]["completed"] = True
                st.session_state["quiz_state"]["loading"] = False
                return

    except Exception as e:
        st.session_state["quiz_state"]["loading"] = False
        error_msg = str(e).lower()
        
        # ENHANCED ERROR HANDLING
        if any(phrase in error_msg for phrase in [
            "no more questions", 
            "quiz completed", 
            "zakończony",
            "quiz has not started yet",
            "no current question available"
        ]):
            if "quiz has not started yet" in error_msg or "no current question available" in error_msg:
                st.info("🔄 Quiz nie został jeszcze uruchomiony lub nie ma dostępnych pytań.")
            else:
                st.session_state["quiz_state"]["completed"] = True
            return
        else:
            st.error(f"❌ Błąd podczas ładowania pytania: {str(e)}")




def get_quiz_progress(quiz_id: str, force_refresh: bool = False):
    """Get quiz progress with enhanced error handling"""
    progress_cache_key = f"quiz_progress_{quiz_id}"
    
    # Force refresh or cache miss
    if force_refresh or progress_cache_key not in st.session_state:
        try:
            api_client = get_api_client(get_user_id())
            progress_data = api_client.get_quiz_progress(quiz_id)
            
            if progress_data and 'progress' in progress_data:
                progress = progress_data['progress']
                
                current_question_num = progress.get('current_question', 1)
                total_questions = progress.get('total_questions_in_pool', 1)
                unique_answered = progress.get('unique_answered', 0)
                total_unique_questions = progress.get('total_unique_questions', 1)
                correct_answers = progress.get('unique_correct', 0)
                
                # Progress based on unique questions
                if total_unique_questions > 0:
                    progress_percentage = (unique_answered / total_questions) * 100
                else:
                    progress_percentage = 0
                
                # Current question number based on unique answered
                current_question_num = unique_answered + 1
                
                # Ensure we don't exceed total questions
                if current_question_num > total_questions:
                    current_question_num = total_questions
                
                # Cache the results
                st.session_state[progress_cache_key] = {
                    'current_question_num': current_question_num,
                    'total_questions': total_questions,
                    'progress_percentage': progress_percentage,
                    'unique_answered': unique_answered,
                    'total_unique_questions': total_unique_questions,
                    'correct_answers': correct_answers,
                    'raw_progress': progress
                }
                
                return st.session_state[progress_cache_key]
            else:
                # Fallback values
                fallback_data = {
                    'current_question_num': 1,
                    'total_questions': 10,
                    'progress_percentage': 0,
                    'unique_answered': 0,
                    'total_unique_questions': 10,
                    'correct_answers': 0,
                    'raw_progress': {}
                }
                st.session_state[progress_cache_key] = fallback_data
                return fallback_data
                
        except Exception as e:
            error_msg = str(e).lower()
            
            # ENHANCED ERROR HANDLING - Check for specific quiz state errors
            if any(phrase in error_msg for phrase in [
                "quiz has not started yet", 
                "not started", 
                "quiz not found",
                "quiz does not exist"
            ]):
                # Quiz hasn't started yet - this is expected for new quizzes
                # Don't show error, just return default values
                fallback_data = {
                    'current_question_num': 1,
                    'total_questions': 10,
                    'progress_percentage': 0,
                    'unique_answered': 0,
                    'total_unique_questions': 10,
                    'correct_answers': 0,
                    'raw_progress': {}
                }
                return fallback_data
            else:
                # Show warning for other errors
                st.warning(f"Nie udało się pobrać postępu quizu: {str(e)}")
                
            # Return cached data if available, otherwise fallback
            if progress_cache_key in st.session_state:
                return st.session_state[progress_cache_key]
            else:
                fallback_data = {
                    'current_question_num': 1,
                    'total_questions': 10,
                    'progress_percentage': 0,
                    'unique_answered': 0,
                    'total_unique_questions': 10,
                    'correct_answers': 0,
                    'raw_progress': {}
                }
                return fallback_data
    else:
        # Return cached data
        return st.session_state[progress_cache_key]

def render_question():
    """Render current question with answer options"""
    question_data = st.session_state["quiz_state"]["current_question"]
    
    if not question_data:
        return
    
    quiz_id = get_quiz_id()
    
    # Get current progress (use cached unless we need fresh data)
    force_refresh = False
    progress_data = get_quiz_progress(quiz_id, force_refresh=force_refresh)
    
    current_question_num = progress_data['current_question_num']
    total_questions = progress_data['total_questions']
    progress_percentage = progress_data['progress_percentage']
    
    # If question is answered, don't increment the display numbers yet
    if st.session_state["quiz_state"]["answered"]:
        current_question_num = current_question_num
        
    col1, col2 = st.columns([5, 3])

    with col2:
        if st.button("🏠 Powrót do strony głównej", key="return_to_main_menu", help="Wróć do głównej strony", on_click=return_to_main_menu):
            return_to_main_menu()
            
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
        render_disabled_answers(question_data)
        render_answer_feedback(question_data)

def is_quiz_completed_by_progress(progress_data: Dict[str, Any]) -> bool:
    """Check if quiz is completed based on progress data"""
    unique_answered = progress_data.get('unique_answered', 0)
    total_unique_questions = progress_data.get('total_unique_questions', 0)
    return unique_answered >= total_unique_questions and total_unique_questions > 0

def render_mastery_summary():
    """Render mastery completion summary focused on learning achievement"""
    # Sprawdź czy już pokazano balony w tej sesji
    if not st.session_state.get("balloons_shown", False):
        st.balloons()  # Celebratory balloons!
        st.session_state["balloons_shown"] = True
    
    quiz_id = get_quiz_id()
    progress_data = get_quiz_progress(quiz_id, force_refresh=True)
    
    # Header - focus on mastery
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("🎓 Materiał opanowany!")
        st.success("Gratulacje! Znasz już wszystkie zagadnienia!")
    
    st.divider()
    
    # Learning-focused metrics - FIXED: Use correct API fields
    st.subheader("📚 Twoja droga do sukcesu:")
    
    # Get data from API progress (raw_progress contains actual API response)
    raw_progress = progress_data.get('raw_progress', {})
    
    # Fixed field mapping based on API response
    total_attempts = raw_progress.get('total_attemps', 0)  # Note: API has typo "attemps"
    unique_questions = raw_progress.get('total_unique_questions', 0) 
    unique_answered = raw_progress.get('unique_answered', 0)
    unique_correct = raw_progress.get('unique_correct', 0)
    
    # Zabezpieczenie przed dzieleniem przez zero
    if total_attempts == 0:
        total_attempts = unique_questions  # Minimum 1 próba na pytanie jeśli są odpowiedzi
    
    # Display metrics in columns
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            label="🎯 Opanowane pytania",
            value=f"{unique_questions}",
            help="Liczba unikalnych pytań, na które poprawnie odpowiedziałeś"
        )
    
    with col2:
        st.metric(
            label="💪 Łączne próby",
            value=f"{total_attempts}",
            help="Ile razy odpowiadałeś na pytania podczas nauki"
        )
    
    with col3:
        # Wskaźnik wytrwałości - im więcej prób na pytanie, tym więcej się uczył
        if unique_questions > 0 and total_attempts > 0:
            avg_attempts = total_attempts / unique_questions
            st.metric(
                label="🔄 Średnio prób/pytanie",
                value=f"{avg_attempts:.1f}",
                help="Średnia liczba prób potrzebnych do poprawnej odpowiedzi na pytanie"
            )
        else:
            avg_attempts = 1.0
            st.metric(
                label="🔄 Średnio prób/pytanie",
                value="1.0",
                help="Średnia liczba prób potrzebnych do poprawnej odpowiedzi na pytanie"
            )
    
    st.divider()
    
    # Statystyki uczenia się - FIXED: Use stored start time and API timing data
    st.subheader("📈 Twój proces uczenia się:")
    
    # Calculate learning time - FIXED: Use stored start time
    start_time_str = st.session_state.get("quiz_state", {}).get("start_time")
    duration_str = "Nieznany"
    
    if start_time_str:
        try:
            start_time = datetime.fromisoformat(start_time_str)
            end_time = datetime.now()
            learning_duration = end_time - start_time
            
            # Format duration nicely
            total_seconds = int(learning_duration.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            
            if hours > 0:
                duration_str = f"{hours}h {minutes}min"
            elif minutes > 0:
                duration_str = f"{minutes}min {seconds}s"
            else:
                duration_str = f"{seconds}s"
        except Exception as e:
            # Fallback to API timing data if available
            api_time_elapsed = raw_progress.get('time_elapsed_seconds', 0)
            if api_time_elapsed > 0:
                minutes = int(api_time_elapsed // 60)
                seconds = int(api_time_elapsed % 60)
                if minutes > 0:
                    duration_str = f"{minutes}min {seconds}s"
                else:
                    duration_str = f"{seconds}s"
            else:
                duration_str = "Nieznany"
    else:
        # Try to get from API if session state is missing
        api_time_elapsed = raw_progress.get('time_elapsed_seconds', 0)
        if api_time_elapsed > 0:
            minutes = int(api_time_elapsed // 60)
            seconds = int(api_time_elapsed % 60)
            if minutes > 0:
                duration_str = f"{minutes}min {seconds}s"
            else:
                duration_str = f"{seconds}s"
    
    # Show learning statistics
    col1, col2 = st.columns(2)
    
    with col1:
        with st.expander("⏱️ Statystyki sesji nauki", expanded=True):
            st.write(f"• **Czas nauki**: {duration_str}")
            st.write(f"• **Zakończenie**: {datetime.now().strftime('%H:%M, %d.%m.%Y')}")
            if total_attempts > 0 and unique_questions > 0:
                st.write(f"• **Tempo nauki**: {total_attempts/unique_questions:.1f} próby/pytanie")
                
            # Show API timing data if available
            avg_time_attempt = raw_progress.get('average_time_per_attempt', 0)
            if avg_time_attempt > 0:
                st.write(f"• **Średni czas/próbę**: {avg_time_attempt:.1f}s")
    
    with col2:
        with st.expander("🧠 Analiza procesu nauki", expanded=True):
            if unique_questions > 0:
                if avg_attempts <= 1.0:
                    st.write("• **Wszystkie pytania** opanowane za pierwszym razem!")
                else:
                    # Show unique correct vs unique answered
                    first_try_success = (unique_correct / unique_questions) * 100 if unique_questions > 0 else 0
                    st.write(f"• **{first_try_success:.1f}%** pytań opanowanych za pierwszym razem")
                    
                st.write(f"• **{unique_questions}** unikalnych pytań przeanalizowanych")
                st.write(f"• **{unique_correct}** poprawnych odpowiedzi")
                
                # Show success rates from API
                unique_success_rate = raw_progress.get('unique_success_rate', 0)
                if unique_success_rate > 0:
                    st.write(f"• **Wskaźnik opanowania**: {unique_success_rate}%")
    
    st.divider()
    
    # Enhanced action buttons focused on continued learning
    st.subheader("🚀 Co dalej?")

    # Check if restart is in progress to prevent multiple buttons
    if st.session_state.get("quiz_restart_in_progress", False):
        st.info("🔄 Restart w toku...")
        return
    
    col1, col2 = st.columns(2)

    with col1:
        if st.button("🔄 Sprawdź się ponownie", use_container_width=True, key="retry_quiz"):
            restart_quiz_with_message("Sprawdź, czy tym razem opanujesz materiał jeszcze szybciej!")

    with col2:
        if st.button("🏠 Menu główne", use_container_width=True, key="main_menu"):
            return_to_main_menu()


def restart_quiz_with_message(message: str):
    """Restart the quiz with a motivational message"""
    quiz_id = get_quiz_id()

    # Prevent multiple restart attempts
    if st.session_state.get("quiz_restart_in_progress", False):
        return
    
    st.session_state["quiz_restart_in_progress"] = True

    try:
        # Pokazuj spinner podczas restartowania
        with st.spinner("Restartowanie quizu..."):
            api_client = get_api_client(get_user_id())
            
            # Try soft reset first (preserves questions)
            try:
                st.info("🔄 Resetowanie postępu quizu...")
                response = api_client.restart_quiz(quiz_id, hard=False)  # Soft reset
                
                # Wait for the backend to reset
                import time
                time.sleep(1.0)
                
                # Verify the reset worked by checking quiz status
                try:
                    # Try to get the first question to verify the reset worked
                    test_question = api_client.get_current_question(quiz_id)
                    if not test_question:
                        raise Exception("No question returned after soft reset")
                    
                    st.success("✅ Soft reset wykonany pomyślnie - pytania zachowane!")
                    
                except Exception as verify_error:
                    st.warning(f"Soft reset verification failed: {str(verify_error)}")
                    raise verify_error  # Let it fall through to hard reset
                
            except Exception as soft_reset_error:
                st.warning(f"Soft reset nie powiódł się: {str(soft_reset_error)}")
                st.info("🔄 Próbuję hard reset...")
                
                # Fallback to hard reset if soft reset fails
                try:
                    response = api_client.restart_quiz(quiz_id, hard=True)
                    time.sleep(1.0)
                    
                    # Verify hard reset worked
                    test_question = api_client.get_current_question(quiz_id)
                    if not test_question:
                        raise Exception("No question returned after hard reset")
                    
                    st.success("✅ Hard reset wykonany pomyślnie - nowe pytania!")
                    
                except Exception as hard_reset_error:
                    st.error(f"❌ Błąd podczas hard reset: {str(hard_reset_error)}")
                    st.info("Spróbuj wrócić do menu głównego i rozpocząć quiz ponownie.")
                    st.session_state["quiz_restart_in_progress"] = False
                    return
            
            # Wyczyść wszystkie cache i stan - AFTER successful API reset
            clear_quiz_cache()
            
            # Clear specific progress cache
            progress_cache_key = f"quiz_progress_{quiz_id}"
            if progress_cache_key in st.session_state:
                del st.session_state[progress_cache_key]
            
            # Clear all quiz-related session state
            keys_to_clear = [
                "quiz_state", 
                "balloons_shown", 
                "quiz_restart_in_progress",
                "quiz_completion_time"
            ]
            
            for key in keys_to_clear:
                if key in st.session_state:
                    del st.session_state[key]
            
            # Resetowanie stanu w sesji - create fresh state
            st.session_state["quiz_state"] = {
                "current_question": None,
                "answered": False,
                "answer_result": None,
                "selected_choices": [],
                "loading": False,
                "completed": False,
                "start_time": datetime.now().isoformat()
            }

        st.success(f"🔄 {message}")
        
        # Additional delay before rerun to ensure backend is ready
        import time
        time.sleep(0.5)
        st.rerun()
        
    except Exception as e:
        st.error(f"❌ Wystąpił błąd przy restarcie quizu: {str(e)}")
        st.info("Spróbuj wrócić do menu głównego i rozpocząć quiz ponownie.")
        
        # Clean up restart flag even on error
        if "quiz_restart_in_progress" in st.session_state:
            del st.session_state["quiz_restart_in_progress"]



def return_to_main_menu():
    """Return to main menu with complete state cleanup - ENHANCED"""
    # Import reset_quiz_session from session_manager
    from utils.session_manager import reset_quiz_session
    
    # Clear ALL quiz-related session state using the dedicated function
    reset_quiz_session()
    
    # Clear additional quiz runtime state - EXPANDED LIST
    quiz_runtime_keys = [
        "quiz_state", 
        "balloons_shown", 
        "quiz_restart_in_progress",
        "quiz_completion_time",
        "show_quiz_list",
        "user_questions",  # Clear custom questions
        "new_question_input",  # Clear input field
        "questions_generated_flag",  # Clear generation flag
        "app_phase",  # Reset app phase
        "topics_confirmed",  # ADDED: Clear topics confirmation
        "quiz_created",  # ADDED: Clear quiz creation flag
        "confirmed_topics"  # ADDED: Clear confirmed topics
    ]
    
    for key in quiz_runtime_keys:
        if key in st.session_state:
            del st.session_state[key]
    
    # Clear quiz cache
    clear_quiz_cache()
    
    # Clear ALL cache keys that might interfere - MORE COMPREHENSIVE
    cache_keys_to_clear = [key for key in st.session_state.keys() 
                          if key.startswith('quiz_') or 
                             key.startswith('topic_') or
                             key.startswith('progress_') or
                             key.startswith('question_') or
                             key.startswith('api_')]
    
    for key in cache_keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]
    
    # Force reset to homepage phase
    st.session_state["app_phase"] = "homepage"
    
    # ENHANCED: Reset ALL quiz creation flags
    st.session_state["quiz_created"] = False
    st.session_state["topics_confirmed"] = False
    st.session_state["questions_generated_flag"] = False
    
    st.success("🏠 Powracasz do menu głównego...")
    st.rerun()


def refresh_quiz_progress_cache(quiz_id: str):
    """Refresh quiz progress cache - wywołaj po każdej odpowiedzi"""
    progress_cache_key = f"quiz_progress_{quiz_id}"
    if progress_cache_key in st.session_state:
        del st.session_state[progress_cache_key]
    
    # Force refresh of progress data
    get_quiz_progress(quiz_id, force_refresh=True)
        
def clear_quiz_cache():
    """Clear quiz-related cache - ENHANCED VERSION"""
    keys_to_remove = [key for key in st.session_state.keys() 
                    if key.startswith('quiz_status_') or 
                       key.startswith('quiz_progress_') or
                       key.startswith('quiz_data_') or
                       key.startswith('current_question_') or
                       key.startswith('api_cache_')]
    
    for key in keys_to_remove:
        if key in st.session_state:
            del st.session_state[key]
def render_disabled_answers(question_data: Dict[str, Any]):
    """Render disabled answer options after submission"""
    choices = question_data.get('choices', [])
    is_multi_choice = question_data.get('is_multi_choice', False)
    selected_choice_ids = st.session_state["quiz_state"]["selected_choices"]
    
    # Show what user selected
    if is_multi_choice:
        st.subheader("💭 Wszystkie opcje odpowiedzi:")
    else:
        st.subheader("💭 Wszystkie opcje odpowiedzi:")
    
    # Display all choices as disabled (grayed out)
    for idx, choice in enumerate(choices):
        if idx in selected_choice_ids:
            # User's selected answers - show as checked but disabled
            if is_multi_choice:
                st.checkbox(
                    f"**{choice['text']}** ← Twój wybór",
                    value=True,
                    disabled=True,
                    key=f"disabled_choice_{question_data['id']}_{idx}"
                )
            else:
                st.checkbox(
                    f"**{choice['text']}** ← Twój wybór",
                    value=True,
                    disabled=True,
                    key=f"disabled_choice_{question_data['id']}_{idx}"
                )
        else:
            # Non-selected answers - show as unchecked and disabled
            st.checkbox(
                choice['text'], 
                value=False,
                disabled=True,
                key=f"disabled_choice_unselected_{question_data['id']}_{idx}"
            )

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


def submit_answer(question_id: str, selected_choices: List[int]):
    """Submit answer to API and refresh progress"""
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
            
            # Store completion time if available
            if not st.session_state.get('quiz_completion_time'):
                from datetime import datetime
                st.session_state['quiz_completion_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Force rerun to show the disabled answers and feedback
            st.rerun()
            
    except Exception as e:
        st.session_state["quiz_state"]["loading"] = False
        # Check if this is a completion error
        error_msg = str(e).lower()
        if "completed" in error_msg or "finished" in error_msg or "zakończony" in error_msg:
            st.session_state["quiz_state"]["completed"] = True
            st.rerun()
        else:
            st.error(f"❌ Błąd podczas wysyłania odpowiedzi: {str(e)}")

def render_answer_feedback(question_data: Dict[str, Any]):
    """Render feedback after answer submission"""
    result = st.session_state["quiz_state"]["answer_result"]
    
    if not result:
        return
    
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
        choices = question_data.get('choices', [])
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
    
    # Display updated progress from the API response
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
        quiz_id = get_quiz_id()
        
        # Reset state for next question
        st.session_state["quiz_state"]["answered"] = False
        st.session_state["quiz_state"]["answer_result"] = None
        st.session_state["quiz_state"]["selected_choices"] = []
        st.session_state["quiz_state"]["current_question"] = None
        
        # Refresh cache
        refresh_quiz_progress_cache(quiz_id)
        clear_quiz_cache()
        
        st.rerun()

# Utility function to check if quiz is completed
def is_quiz_completed(question_data: Dict[str, Any]) -> bool:
    """Check if quiz is completed"""
    current_q = question_data.get('current_question_number', 0)
    total_q = question_data.get('total_questions', 0)
    return current_q >= total_q