# tests/Agent/Quiz/test_models.py
import pytest
from datetime import datetime
from unittest.mock import Mock

from src.Testaiownik.Agent.Quiz.models import (
    QuestionChoice,
    Question,
    UserAnswer,
    QuizSession,
    QuizResults,
    QuestionGeneration,
    QuizConfiguration,
    UserQuestionResponse,
)


class TestQuestionChoice:
    def test_creation(self):
        choice = QuestionChoice(text="Test answer", is_correct=True)
        assert choice.text == "Test answer"
        assert choice.is_correct == True

    def test_creation_false(self):
        choice = QuestionChoice(text="Wrong answer", is_correct=False)
        assert choice.text == "Wrong answer"
        assert choice.is_correct == False


class TestQuestion:
    @pytest.fixture
    def sample_question(self):
        return Question(
            topic="Algorithms",
            question_text="What is the time complexity of QuickSort?",
            choices=[
                QuestionChoice(text="O(n)", is_correct=False),
                QuestionChoice(text="O(n log n)", is_correct=True),
                QuestionChoice(text="O(n²)", is_correct=False),
            ],
            explanation="QuickSort has average case O(n log n) complexity",
            difficulty="medium",
        )

    @pytest.fixture
    def multi_choice_question(self):
        return Question(
            topic="Data Structures",
            question_text="Which are linear data structures?",
            choices=[
                QuestionChoice(text="Array", is_correct=True),
                QuestionChoice(text="Tree", is_correct=False),
                QuestionChoice(text="Stack", is_correct=True),
                QuestionChoice(text="Graph", is_correct=False),
            ],
            explanation="Arrays and stacks are linear data structures",
            difficulty="easy",
            is_multi_choice=True,
        )

    def test_question_creation(self, sample_question):
        assert sample_question.topic == "Algorithms"
        assert (
            sample_question.question_text == "What is the time complexity of QuickSort?"
        )
        assert len(sample_question.choices) == 3
        assert sample_question.difficulty == "medium"
        assert sample_question.is_multi_choice == False

    def test_get_correct_indices_single(self, sample_question):
        correct_indices = sample_question.get_correct_indices()
        assert correct_indices == [1]

    def test_get_correct_indices_multiple(self, multi_choice_question):
        correct_indices = multi_choice_question.get_correct_indices()
        assert correct_indices == [0, 2]

    def test_is_answer_correct_single_choice_correct(self, sample_question):
        assert sample_question.is_answer_correct([1]) == True

    def test_is_answer_correct_single_choice_incorrect(self, sample_question):
        assert sample_question.is_answer_correct([0]) == False
        assert sample_question.is_answer_correct([2]) == False

    def test_is_answer_correct_multi_choice_correct(self, multi_choice_question):
        assert multi_choice_question.is_answer_correct([0, 2]) == True
        assert (
            multi_choice_question.is_answer_correct([2, 0]) == True
        )  # Order doesn't matter

    def test_is_answer_correct_multi_choice_incorrect(self, multi_choice_question):
        assert multi_choice_question.is_answer_correct([0]) == False  # Partial correct
        assert multi_choice_question.is_answer_correct([1, 3]) == False  # All wrong
        assert (
            multi_choice_question.is_answer_correct([0, 1, 2]) == False
        )  # Extra wrong

    def test_question_has_id(self, sample_question):
        assert sample_question.id is not None
        assert len(sample_question.id) > 0

    def test_question_has_timestamp(self, sample_question):
        assert isinstance(sample_question.generated_at, datetime)


class TestUserAnswer:
    def test_creation(self):
        answer = UserAnswer(
            question_id="test-id",
            selected_choice_indices=[1, 2],
            is_correct=True,
            attempt_number=1,
        )

        assert answer.question_id == "test-id"
        assert answer.selected_choice_indices == [1, 2]
        assert answer.is_correct == True
        assert answer.attempt_number == 1
        assert isinstance(answer.answered_at, datetime)

    def test_default_attempt_number(self):
        answer = UserAnswer(
            question_id="test-id",
            selected_choice_indices=[0],
            is_correct=False,
        )
        assert answer.attempt_number == 1


class TestQuizSession:
    @pytest.fixture
    def sample_topics(self):
        return [
            {"topic": "Algorithms", "weight": 0.6},
            {"topic": "Data Structures", "weight": 0.4},
        ]

    @pytest.fixture
    def quiz_session(self, sample_topics):
        return QuizSession(
            topics=sample_topics,
            total_questions=10,
            difficulty="medium",
            questions_per_topic={"Algorithms": 6, "Data Structures": 4},
        )

    def test_quiz_session_creation(self, quiz_session, sample_topics):
        assert quiz_session.topics == sample_topics
        assert quiz_session.total_questions == 10
        assert quiz_session.difficulty == "medium"
        assert quiz_session.questions_per_topic == {
            "Algorithms": 6,
            "Data Structures": 4,
        }
        assert quiz_session.current_question_index == 0
        assert quiz_session.status == "generating"
        assert len(quiz_session.user_answers) == 0
        assert len(quiz_session.all_generated_questions) == 0

    def test_get_current_question_empty_pool(self, quiz_session):
        # No questions in pool yet
        assert quiz_session.get_current_question() is None

    def test_get_current_question_with_questions(self, quiz_session):
        # Add a question and set it in the pool
        question = Question(
            topic="Algorithms",
            question_text="Test question",
            choices=[
                QuestionChoice(text="A", is_correct=True),
                QuestionChoice(text="B", is_correct=False),
            ],
            explanation="Test explanation",
        )
        quiz_session.all_generated_questions.append(question)
        quiz_session.active_question_pool.append(question.id)

        current = quiz_session.get_current_question()
        assert current is not None
        assert current.id == question.id

    def test_add_answer_correct(self, quiz_session):
        answer = UserAnswer(
            question_id="test-id",
            selected_choice_indices=[1],
            is_correct=True,
        )

        initial_time = quiz_session.last_activity
        quiz_session.add_answer(answer)

        assert len(quiz_session.user_answers) == 1
        assert quiz_session.user_answers[0] == answer
        assert quiz_session.last_activity > initial_time

    def test_add_answer_incorrect_recycle(self, quiz_session):
        answer = UserAnswer(
            question_id="test-id",
            selected_choice_indices=[0],
            is_correct=False,
        )

        quiz_session.active_question_pool = ["other-id"]  # Start with something
        quiz_session.add_answer(answer)

        # Should add question to end for recycling
        assert "test-id" in quiz_session.active_question_pool
        assert quiz_session.incorrect_recycle_count["test-id"] == 1

    def test_add_answer_max_recycles_reached(self, quiz_session):
        quiz_session.max_incorrect_recycles = 2
        quiz_session.incorrect_recycle_count["test-id"] = 2  # Already at max

        answer = UserAnswer(
            question_id="test-id",
            selected_choice_indices=[0],
            is_correct=False,
        )

        initial_pool = quiz_session.active_question_pool.copy()
        quiz_session.add_answer(answer)

        # Should NOT add question again
        assert quiz_session.active_question_pool == initial_pool
        assert quiz_session.incorrect_recycle_count["test-id"] == 2

    def test_is_completed_true(self, quiz_session):
        quiz_session.active_question_pool = ["q1", "q2"]
        quiz_session.current_question_index = 2  # Past the end

        assert quiz_session.is_completed() == True

    def test_is_completed_false(self, quiz_session):
        quiz_session.active_question_pool = ["q1", "q2"]
        quiz_session.current_question_index = 1  # Still has questions

        assert quiz_session.is_completed() == False

    def test_get_next_question(self, quiz_session):
        question1 = Question(
            topic="Test",
            question_text="Q1",
            choices=[QuestionChoice(text="A", is_correct=True)],
            explanation="Exp1",
        )
        question2 = Question(
            topic="Test",
            question_text="Q2",
            choices=[QuestionChoice(text="B", is_correct=True)],
            explanation="Exp2",
        )

        quiz_session.all_generated_questions.extend([question1, question2])
        quiz_session.active_question_pool.extend([question1.id, question2.id])

        # Should start at index 0, advance to 1
        next_q = quiz_session.get_next_question()
        assert quiz_session.current_question_index == 1
        assert next_q.id == question2.id

    def test_get_next_question_at_end(self, quiz_session):
        quiz_session.active_question_pool = ["q1"]
        quiz_session.current_question_index = 1  # Already past end

        next_q = quiz_session.get_next_question()
        assert next_q is None
        assert quiz_session.current_question_index == 1  # Stays the same


class TestQuizResults:
    def test_creation(self):
        topic_scores = {
            "Algorithms": {"correct": 8, "total": 10, "percentage": 80.0},
            "Data Structures": {"correct": 6, "total": 8, "percentage": 75.0},
        }

        results = QuizResults(
            session_id="test-session",
            total_questions=18,
            correct_answers=14,
            score_percentage=77.8,
            topic_scores=topic_scores,
            time_taken=25.5,
        )

        assert results.session_id == "test-session"
        assert results.total_questions == 18
        assert results.correct_answers == 14
        assert results.score_percentage == 77.8
        assert results.topic_scores == topic_scores
        assert results.time_taken == 25.5
        assert isinstance(results.completed_at, datetime)


class TestQuizConfiguration:
    def test_creation_with_defaults(self):
        topics = [{"topic": "Algorithms", "weight": 1.0}]

        config = QuizConfiguration(topics=topics)

        assert config.topics == topics
        assert config.total_questions == 20
        assert config.difficulty == "medium"
        assert config.batch_size == 5
        assert config.max_incorrect_recycles == 2
        assert config.quiz_mode == "fresh"
        assert config.user_questions == []
        assert config.user_id is None

    def test_creation_with_custom_values(self):
        topics = [{"topic": "Advanced", "weight": 1.0}]
        user_questions = ["What is recursion?", "Explain Big O notation"]

        config = QuizConfiguration(
            topics=topics,
            total_questions=50,
            difficulty="hard",
            batch_size=10,
            max_incorrect_recycles=3,
            quiz_mode="retry_failed",
            user_questions=user_questions,
            user_id="user123",
            previous_session_id="prev-session",
        )

        assert config.total_questions == 50
        assert config.difficulty == "hard"
        assert config.batch_size == 10
        assert config.max_incorrect_recycles == 3
        assert config.quiz_mode == "retry_failed"
        assert config.user_questions == user_questions
        assert config.user_id == "user123"
        assert config.previous_session_id == "prev-session"


class TestQuestionGeneration:
    def test_creation(self):
        questions = [
            Question(
                topic="Test",
                question_text="Q1",
                choices=[QuestionChoice(text="A", is_correct=True)],
                explanation="Explanation",
            )
        ]

        generation = QuestionGeneration(
            topic="Test Topic",
            questions=questions,
            reasoning="Generated based on topic analysis",
        )

        assert generation.topic == "Test Topic"
        assert generation.questions == questions
        assert generation.reasoning == "Generated based on topic analysis"


class TestUserQuestionResponse:
    def test_creation(self):
        response = UserQuestionResponse(
            correct_answers=["Option A", "Option C"],
            wrong_options=["Option B", "Option D"],
            explanation="A and C are correct because...",
            assigned_topic="Data Structures",
            is_multi_choice=True,
        )

        assert response.correct_answers == ["Option A", "Option C"]
        assert response.wrong_options == ["Option B", "Option D"]
        assert response.explanation == "A and C are correct because..."
        assert response.assigned_topic == "Data Structures"
        assert response.is_multi_choice == True

    def test_creation_with_defaults(self):
        response = UserQuestionResponse(
            correct_answers=["True"],
            explanation="This is correct",
            assigned_topic="General",
        )

        assert response.wrong_options == []
        assert response.is_multi_choice == False


if __name__ == "__main__":
    pytest.main([__file__])
