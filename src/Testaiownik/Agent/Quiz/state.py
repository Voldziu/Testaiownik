from typing import TypedDict, Optional, Dict, Any, List
from .models import QuizSession, Question, QuizResults
from Agent.Shared import WeightedTopic


class QuizState(TypedDict):
    # Session management
    quiz_session: Optional[QuizSession]

    # Current question flow
    current_question: Optional[Question]
    user_input: Optional[str]

    # Results and completion
    quiz_results: Optional[QuizResults]
    quiz_complete: bool

    # Navigation
    next_node: str

    # Configuration from main graph
    confirmed_topics: List[WeightedTopic]  # From topic subgraph output
    quiz_config: Dict[str, Any]  # {"total_questions": 20, "difficulty": "medium"}

    # Future persistence preparation
    session_data: Optional[Dict[str, Any]]  # Prepared for DB storage
    persistence_required: bool
