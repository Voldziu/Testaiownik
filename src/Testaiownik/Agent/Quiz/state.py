from typing import TypedDict, Optional, Dict, Any, List
from .models import QuizSession, Question, QuizResults, QuizConfiguration
from Agent.Shared import WeightedTopic
from RAG.Retrieval import DocumentRetriever


class QuizState(TypedDict):
    # PERSISTENT - serializable to database
    quiz_session: Optional[QuizSession]
    session_snapshot: Optional[Dict[str, Any]]  # Full state backup for persistence

    # EPHEMERAL - only during execution
    current_question: Optional[Question]
    user_input: Optional[str]  # User's answer to the current question
    questions_to_generate: Optional[Dict[str, int]]  # topic -> remaining count
    current_topic_batch: Optional[str]  # Currently generating topic

    # Results and completion
    quiz_results: Optional[QuizResults]
    quiz_complete: bool

    # Navigation
    next_node: str

    # Configuration (input from main graph)
    quiz_config: Optional[QuizConfiguration]
    confirmed_topics: Optional[List[WeightedTopic]]  # From topic selection subgraph

    # Context for RAG integration
    retriever: Optional[DocumentRetriever]


def create_initial_quiz_state(
    confirmed_topics: List[WeightedTopic],
    total_questions: int = 20,
    difficulty: str = "medium",
    batch_size: int = 5,
    copies_per_incorrect_answer: int = 2,
    quiz_mode: str = "fresh",
    user_questions: Optional[List[str]] = [],
    user_id: Optional[str] = None,
    previous_session_id: Optional[str] = None,
) -> QuizState:
    """Create initial quiz state from topic selection output"""

    quiz_config = QuizConfiguration(
        topics=confirmed_topics,
        total_questions=total_questions,
        difficulty=difficulty,
        batch_size=batch_size,
        copies_per_incorrect_answer=copies_per_incorrect_answer,
        quiz_mode=quiz_mode,
        user_questions=user_questions,
        user_id=user_id,
        previous_session_id=previous_session_id,
    )

    return QuizState(
        # Persistent
        quiz_session=None,  # Will be created in initialize_quiz node
        session_snapshot=None,
        # Ephemeral
        current_question=None,
        user_input=None,
        questions_to_generate=None,
        current_topic_batch=None,
        # Results
        quiz_results=None,
        quiz_complete=False,
        # Navigation
        next_node="initialize_quiz",
        # Configuration
        quiz_config=quiz_config,
        confirmed_topics=confirmed_topics,
        retriever=None,  # Will be set in initialize_quiz node
    )


def prepare_state_for_persistence(state: QuizState) -> Dict[str, Any]:
    """Prepare state for database storage"""
    if not state["quiz_session"]:
        return {}

    return {
        "session_id": state["quiz_session"].session_id,
        "user_id": state["quiz_session"].user_id,
        "quiz_data": state["quiz_session"].model_dump(),
        "snapshot": {
            "quiz_complete": state.get("quiz_complete", False),
            "questions_to_generate": state.get("questions_to_generate", {}),
            "current_topic_batch": state.get("current_topic_batch", None),
        },
        "last_activity": state["quiz_session"].last_activity,
        "status": state["quiz_session"].status,
    }


def restore_state_from_persistence(db_data: Dict[str, Any]) -> QuizState:
    """Restore state from database"""
    quiz_session = QuizSession(**db_data["quiz_data"])
    snapshot = db_data.get("snapshot", {})

    return QuizState(
        # Persistent
        quiz_session=quiz_session,
        session_snapshot=snapshot,
        # Ephemeral - restore from snapshot
        current_question=quiz_session.get_current_question(),
        user_input=None,
        questions_to_generate=snapshot.get("questions_to_generate"),
        current_topic_batch=snapshot.get("current_topic_batch"),
        # Results
        quiz_results=None,
        quiz_complete=snapshot.get("quiz_complete", False),
        # Navigation
        next_node=(
            "present_question"
            if not snapshot.get("quiz_complete")
            else "finalize_results"
        ),
        # Configuration
        quiz_config=None,  # Not needed after initialization
        confirmed_topics=quiz_session.topics,
        retriever=None,  # Will be set in initialize_quiz node
    )
