# tests/Agent/Quiz/test_state.py
import pytest
from unittest.mock import Mock
from datetime import datetime

from src.Testaiownik.Agent.Quiz.state import (
    QuizState,
    create_initial_quiz_state,
    prepare_state_for_persistence,
    restore_state_from_persistence,
)
from src.Testaiownik.Agent.Quiz.models import (
    QuizSession,
    Question,
    QuestionChoice,
    QuizConfiguration,
    WeightedTopic,  # I dont know why this is needed, but it must be like this
)


class TestCreateInitialQuizState:
    @pytest.fixture
    def sample_topics(self):
        return [
            WeightedTopic(topic="Algorithms", weight=0.6),
            WeightedTopic(topic="Data Structures", weight=0.4),
        ]

    def test_create_initial_state_defaults(self, sample_topics):
        state = create_initial_quiz_state(sample_topics)

        assert state["confirmed_topics"] == sample_topics
        assert state["quiz_session"] is None
        assert state["current_question"] is None
        assert state["user_input"] is None
        assert state["quiz_complete"] == False
        assert state["next_node"] == "initialize_quiz"

        # Check quiz config defaults
        config = state["quiz_config"]
        assert config.topics == sample_topics
        assert config.total_questions == 20
        assert config.difficulty == "medium"
        assert config.batch_size == 5
        assert config.max_incorrect_recycles == 2
        assert config.quiz_mode == "fresh"
        assert config.user_id is None

    def test_create_initial_state_custom_params(self, sample_topics):
        state = create_initial_quiz_state(
            confirmed_topics=sample_topics,
            total_questions=50,
            difficulty="hard",
            batch_size=10,
            max_incorrect_recycles=3,
            quiz_mode="retry_failed",
            user_id="user123",
            previous_session_id="prev-session",
        )

        config = state["quiz_config"]
        assert config.total_questions == 50
        assert config.difficulty == "hard"
        assert config.batch_size == 10
        assert config.max_incorrect_recycles == 3
        assert config.quiz_mode == "retry_failed"
        assert config.user_id == "user123"
        assert config.previous_session_id == "prev-session"

    def test_create_initial_state_structure(self, sample_topics):
        state = create_initial_quiz_state(sample_topics)

        # Check all required keys exist
        required_keys = [
            "quiz_session",
            "session_snapshot",
            "current_question",
            "user_input",
            "questions_to_generate",
            "current_topic_batch",
            "quiz_results",
            "quiz_complete",
            "next_node",
            "quiz_config",
            "confirmed_topics",
            "retriever",
        ]

        for key in required_keys:
            assert key in state


class TestPrepareStateForPersistence:
    @pytest.fixture
    def quiz_session(self):
        session = QuizSession(
            session_id="test-session-123",
            topics=[
                WeightedTopic(topic="Test", weight=1.0),
            ],
            total_questions=5,
            questions_per_topic={"Test": 5},
            user_id="user123",
        )
        session.status = "active"
        return session

    @pytest.fixture
    def quiz_state_with_session(self, quiz_session):
        return {
            "quiz_session": quiz_session,
            "quiz_complete": False,
            "questions_to_generate": {"Test": 3},
            "current_topic_batch": "Test",
        }

    def test_prepare_state_for_persistence_success(
        self, quiz_state_with_session, quiz_session
    ):
        result = prepare_state_for_persistence(quiz_state_with_session)

        assert result["session_id"] == "test-session-123"
        assert result["user_id"] == "user123"
        assert "quiz_data" in result
        assert result["status"] == "active"

        # Check snapshot
        snapshot = result["snapshot"]
        assert snapshot["quiz_complete"] == False
        assert snapshot["questions_to_generate"] == {"Test": 3}
        assert snapshot["current_topic_batch"] == "Test"

    def test_prepare_state_no_session(self):
        state = {"quiz_session": None}

        result = prepare_state_for_persistence(state)

        assert result == {}

    def test_prepare_state_partial_data(self, quiz_session):
        state = {
            "quiz_session": quiz_session,
            "quiz_complete": True,
            # Missing some optional fields
        }

        result = prepare_state_for_persistence(state)

        assert result["session_id"] == quiz_session.session_id
        snapshot = result["snapshot"]
        assert snapshot["quiz_complete"] == True
        assert snapshot["questions_to_generate"] == {}


class TestRestoreStateFromPersistence:
    @pytest.fixture
    def sample_question(self):
        return Question(
            topic="Test",
            question_text="Sample question?",
            choices=[
                QuestionChoice(text="A", is_correct=True),
                QuestionChoice(text="B", is_correct=False),
            ],
            explanation="A is correct",
        )

    @pytest.fixture
    def db_data(self, sample_question):
        quiz_session_data = {
            "session_id": "restored-session",
            "topics": [WeightedTopic(topic="Test", weight=1.0)],
            "total_questions": 5,
            "difficulty": "medium",
            "batch_size": 5,
            "max_incorrect_recycles": 2,
            "quiz_mode": "fresh",
            "questions_per_topic": {"Test": 5},
            "all_generated_questions": [sample_question.model_dump()],
            "active_question_pool": [sample_question.id],
            "incorrect_recycle_count": {},
            "current_question_index": 0,
            "user_answers": [],
            "status": "active",
            "created_at": datetime.now().isoformat(),
            "last_activity": datetime.now().isoformat(),
            "user_id": "user123",
        }

        return {
            "quiz_data": quiz_session_data,
            "snapshot": {
                "quiz_complete": False,
                "questions_to_generate": {"Test": 2},
                "current_topic_batch": "Test",
                "rag_enabled": False,
            },
            "last_activity": datetime.now().isoformat(),
            "status": "active",
        }

    def test_restore_state_from_persistence(self, db_data):
        state = restore_state_from_persistence(db_data)

        assert state["quiz_session"] is not None
        assert state["quiz_session"].session_id == "restored-session"
        assert state["quiz_session"].user_id == "user123"
        assert state["quiz_complete"] == False
        assert state["questions_to_generate"] == {"Test": 2}
        assert state["current_topic_batch"] == "Test"
        assert state["next_node"] == "present_question"

    def test_restore_state_completed_quiz(self, db_data):
        db_data["snapshot"]["quiz_complete"] = True

        state = restore_state_from_persistence(db_data)

        assert state["quiz_complete"] == True
        assert state["next_node"] == "finalize_results"

    def test_restore_state_missing_snapshot(self, db_data):
        del db_data["snapshot"]

        state = restore_state_from_persistence(db_data)

        # Should handle missing snapshot gracefully
        assert state["quiz_session"] is not None
        assert state["quiz_complete"] == False  # Default
        assert state["questions_to_generate"] is None

    def test_restore_state_partial_snapshot(self, db_data):
        db_data["snapshot"] = {"quiz_complete": True}  # Only partial data

        state = restore_state_from_persistence(db_data)

        assert state["quiz_complete"] == True
        assert state["questions_to_generate"] is None
        assert state["current_topic_batch"] is None


class TestQuizStateIntegration:
    """Integration tests for the complete state lifecycle"""

    def test_full_state_lifecycle(self):
        # 1. Create initial state
        topics = [
            WeightedTopic(topic="Algorithms", weight=1.0),
        ]
        initial_state = create_initial_quiz_state(
            topics, total_questions=3, user_id="test-user"
        )

        assert initial_state["next_node"] == "initialize_quiz"
        assert initial_state["quiz_session"] is None

        # 2. Simulate quiz session creation (normally done in initialize_quiz node)
        quiz_session = QuizSession(
            topics=topics,
            total_questions=3,
            questions_per_topic={"Algorithms": 3},
            user_id="test-user",
        )

        # Add a question
        question = Question(
            topic="Algorithms",
            question_text="What is Big O?",
            choices=[
                QuestionChoice(text="Time complexity", is_correct=True),
                QuestionChoice(text="Space complexity", is_correct=False),
            ],
            explanation="Big O notation describes time complexity",
        )
        quiz_session.all_generated_questions.append(question)
        quiz_session.active_question_pool.append(question.id)

        # Update state
        active_state = {
            **initial_state,
            "quiz_session": quiz_session,
            "current_question": question,
            "quiz_complete": False,
            "questions_to_generate": {"Algorithms": 2},
        }

        # 3. Prepare for persistence
        persistence_data = prepare_state_for_persistence(active_state)

        assert persistence_data["session_id"] == quiz_session.session_id
        assert persistence_data["user_id"] == "test-user"
        assert "quiz_data" in persistence_data

        # 4. Restore from persistence
        restored_state = restore_state_from_persistence(persistence_data)

        assert restored_state["quiz_session"].session_id == quiz_session.session_id
        assert restored_state["quiz_session"].user_id == "test-user"
        assert len(restored_state["quiz_session"].all_generated_questions) == 1
        assert restored_state["quiz_complete"] == False

    def test_state_validation_requirements(self):
        """Test that state meets QuizState type requirements"""
        topics = [
            WeightedTopic(topic="Test", weight=1.0),
        ]
        state = create_initial_quiz_state(topics)

        # Type checking - these should not raise TypeErrors if types are correct
        session: QuizSession = state.get("quiz_session")  # Can be None
        complete: bool = state["quiz_complete"]
        next_node: str = state["next_node"]
        config: QuizConfiguration = state["quiz_config"]

        assert isinstance(complete, bool)
        assert isinstance(next_node, str)
        assert isinstance(config, QuizConfiguration)

    def test_state_immutability_patterns(self):
        """Test that state updates follow immutable patterns"""
        topics = [
            WeightedTopic(topic="Test", weight=1.0),
        ]
        original_state = create_initial_quiz_state(topics)

        # Simulate state update (how it should be done in nodes)
        updated_state = {
            **original_state,
            "quiz_complete": True,
            "next_node": "finalize_results",
        }

        # Original state should be unchanged
        assert original_state["quiz_complete"] == False
        assert original_state["next_node"] == "initialize_quiz"

        # Updated state should have new values
        assert updated_state["quiz_complete"] == True
        assert updated_state["next_node"] == "finalize_results"

        # Shared references should still work
        assert updated_state["quiz_config"] is original_state["quiz_config"]


if __name__ == "__main__":
    pytest.main([__file__])
