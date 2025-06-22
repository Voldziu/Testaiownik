# tests/Agent/Quiz/test_nodes.py
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from src.Testaiownik.Agent.Quiz.nodes import (
    initialize_quiz,
    load_or_generate_questions,
    generate_all_questions,
    present_question,
    process_answer,
    check_completion,
    finalize_results,
    route_next,
    _process_user_questions,
    _generate_questions_for_topic,
    _remove_duplicate_questions,
    _create_fallback_questions,
    _format_question_for_user,
    _create_answer_feedback,
    _format_quiz_results,
)
from src.Testaiownik.Agent.Quiz.models import (
    QuizConfiguration,
    QuizSession,
    Question,
    QuestionChoice,
    UserAnswer,
    QuizResults,
    UserQuestionResponse,
    WeightedTopic,  # TO ENSURE COMPATIBILITY WITH CODE
)
from src.Testaiownik.Agent.Quiz.state import QuizState


class TestInitializeQuiz:
    @pytest.fixture
    def quiz_config(self):
        return QuizConfiguration(
            topics=[
                WeightedTopic(topic="Algorithms", weight=0.6),
                WeightedTopic(topic="Data Structures", weight=0.4),
            ],
            total_questions=10,
            difficulty="medium",
        )

    @pytest.fixture
    def quiz_state(self, quiz_config):
        return {
            "quiz_config": quiz_config,
            "quiz_session": None,
            "questions_to_generate": None,
        }

    def test_initialize_quiz_success(self, quiz_state, quiz_config):
        result = initialize_quiz(quiz_state)

        assert "quiz_session" in result
        assert result["quiz_session"] is not None
        assert result["quiz_session"].total_questions == 10
        assert result["quiz_session"].difficulty == "medium"
        assert result["next_node"] == "load_or_generate_questions"

        # Check questions per topic calculation
        questions_per_topic = result["quiz_session"].questions_per_topic
        assert questions_per_topic["Algorithms"] == 6  # 0.6 * 10 = 6
        assert questions_per_topic["Data Structures"] == 4  # 0.4 * 10 = 4

    def test_initialize_quiz_no_config(self):
        state = {"quiz_config": None}

        with pytest.raises(ValueError, match="Quiz configuration is required"):
            initialize_quiz(state)

    def test_initialize_quiz_weight_distribution(self):
        config = QuizConfiguration(
            topics=[
                WeightedTopic(topic="Topic1", weight=0.6),
                WeightedTopic(topic="Topic2", weight=0.4),
            ],
            total_questions=20,
            difficulty="medium",
            batch_size=5,
            max_incorrect_recycles=2,
            quiz_mode="fresh",
            user_questions=[],
            user_id=None,
            previous_session_id=None,
        )
        state = {"quiz_config": config}

        result = initialize_quiz(state)
        questions_per_topic = result["quiz_session"].questions_per_topic

        # Minimum 1 question per topic
        assert questions_per_topic["Topic1"] >= 1
        assert questions_per_topic["Topic2"] >= 1
        # Topic1 should get most questions
        assert questions_per_topic["Topic1"] > questions_per_topic["Topic2"]


class TestLoadOrGenerateQuestions:
    @pytest.fixture
    def quiz_session(self):
        return QuizSession(
            topics=[WeightedTopic(topic="Test", weight=1.0)],
            total_questions=5,
            questions_per_topic={"Test": 5},
        )

    def test_load_fresh_mode(self, quiz_session):
        quiz_session.quiz_mode = "fresh"
        state = {"quiz_session": quiz_session}

        result = load_or_generate_questions(state)

        assert result["next_node"] == "generate_all_questions"

    def test_load_retry_modes(self, quiz_session):
        for mode in ["retry_same", "retry_failed"]:
            quiz_session.quiz_mode = mode
            state = {"quiz_session": quiz_session}

            result = load_or_generate_questions(state)

            # Currently falls back to fresh generation
            assert result["next_node"] == "generate_all_questions"

    def test_load_invalid_mode(self, quiz_session):
        quiz_session.quiz_mode = "invalid_mode"
        state = {"quiz_session": quiz_session}

        with pytest.raises(ValueError, match="Unknown quiz mode"):
            load_or_generate_questions(state)

    def test_load_no_session(self):
        state = {"quiz_session": None}

        with pytest.raises(ValueError, match="Quiz session not initialized"):
            load_or_generate_questions(state)


class TestGenerateAllQuestions:
    @pytest.fixture
    def quiz_session(self):
        return QuizSession(
            topics=[WeightedTopic(topic="Algorithms", weight=1.0)],
            total_questions=5,
            questions_per_topic={"Algorithms": 5},
            batch_size=2,
        )

    @pytest.fixture
    def quiz_config(self):
        return QuizConfiguration(
            topics=[WeightedTopic(topic="Algorithms", weight=1.0)],
            user_questions=["What is recursion?"],
        )

    @pytest.fixture
    def mock_retriever(self):
        retriever = Mock()
        retriever.search_in_collection.return_value = [
            Mock(payload={"text": "Algorithm content..."})
        ]
        return retriever

    @patch("src.Testaiownik.Agent.Quiz.nodes._process_user_questions")
    @patch("src.Testaiownik.Agent.Quiz.nodes._generate_questions_for_topic")
    def test_generate_all_questions_with_user_questions(
        self, mock_generate, mock_process_user, quiz_session, quiz_config
    ):
        # Mock user question processing
        user_question = Question(
            topic="Algorithms",
            question_text="What is recursion?",
            choices=[
                QuestionChoice(text="A function calling itself", is_correct=True),
                QuestionChoice(text="A loop", is_correct=False),
            ],
            explanation="Recursion is when a function calls itself",
        )
        mock_process_user.return_value = [user_question]

        # Mock LLM question generation
        llm_questions = [
            Question(
                topic="Algorithms",
                question_text="What is the time complexity of binary search?",
                choices=[
                    QuestionChoice(text="O(log n)", is_correct=True),
                    QuestionChoice(text="O(n)", is_correct=False),
                ],
                explanation="Binary search divides the search space in half",
            )
        ]
        mock_generate.return_value = llm_questions

        state = {
            "quiz_session": quiz_session,
            "questions_to_generate": {"Algorithms": 1},  # 1 LLM question needed
            "quiz_config": quiz_config,
        }

        result = generate_all_questions(state)

        # Should process user questions
        mock_process_user.assert_called_once_with(
            ["What is recursion?"], quiz_session.topics, quiz_session.difficulty
        )

        # Should generate 1 LLM question
        mock_generate.assert_called_once()

        # Should have both questions in session
        session = result["quiz_session"]
        assert len(session.all_generated_questions) == 2
        assert len(session.active_question_pool) == 2
        assert result["next_node"] == "present_question"

    @patch("src.Testaiownik.Agent.Quiz.nodes._generate_questions_for_topic")
    def test_generate_all_questions_batching(self, mock_generate, quiz_session):
        # Need 5 questions, batch size 2, so should make 3 calls (2+2+1)
        quiz_session.batch_size = 2

        mock_generate.side_effect = [
            [Mock(), Mock()],  # First batch: 2 questions
            [Mock(), Mock()],  # Second batch: 2 questions
            [Mock()],  # Third batch: 1 question
        ]
        mock_generate.return_value = [
            Question(
                topic="Algorithms", question_text="Q1", choices=[], explanation=""
            ),
            Question(
                topic="Algorithms", question_text="Q2", choices=[], explanation=""
            ),
            Question(
                topic="Algorithms", question_text="Q3", choices=[], explanation=""
            ),
        ]

        state = {
            "quiz_session": quiz_session,
            "questions_to_generate": {"Algorithms": 5},
            "quiz_config": None,
        }

        generate_all_questions(state)

        # Should call generate 3 times for batching
        assert mock_generate.call_count == 3

        # Check batch sizes
        call_args = [call[1]["count"] for call in mock_generate.call_args_list]
        assert call_args == [2, 2, 1]

    def test_generate_all_questions_no_questions_needed(self, quiz_session):
        state = {
            "quiz_session": quiz_session,
            "questions_to_generate": {},  # No questions to generate
            "quiz_config": None,
        }

        result = generate_all_questions(state)

        assert result["next_node"] == "present_question"
        assert result["questions_to_generate"] == {}


class TestPresentQuestion:
    @pytest.fixture
    def quiz_session_with_questions(self):
        question = Question(
            topic="Test",
            question_text="Sample question?",
            choices=[
                QuestionChoice(text="A", is_correct=True),
                QuestionChoice(text="B", is_correct=False),
            ],
            explanation="A is correct",
        )

        session = QuizSession(
            topics=[WeightedTopic(topic="Test", weight=1.0)],
            total_questions=1,
            difficulty="medium",
            batch_size=5,
            max_incorrect_recycles=2,
            quiz_mode="fresh",
            questions_per_topic={"Test": 1},
        )
        session.all_generated_questions = [question]
        session.active_question_pool = [question.id]

        return session

    def test_present_question_success(self, quiz_session_with_questions):
        state = {"quiz_session": quiz_session_with_questions}

        result = present_question(state)

        assert result["current_question"] is not None
        assert result["next_node"] == "process_answer"
        assert "feedback_request" in result
        assert "Sample question?" in result["feedback_request"]

    def test_present_question_no_more_questions(self):
        session = QuizSession(
            topics=[WeightedTopic(topic="Test", weight=1.0)],
            total_questions=1,
            difficulty="medium",
            batch_size=5,
            max_incorrect_recycles=2,
            quiz_mode="fresh",
            questions_per_topic={"Test": 1},
        )

        # No questions in pool
        session.active_question_pool = []

        state = {"quiz_session": session}

        result = present_question(state)

        assert result["next_node"] == "finalize_results"

    def test_present_question_no_session(self):
        state = {"quiz_session": None}

        with pytest.raises(ValueError, match="Quiz session not initialized"):
            present_question(state)


class TestProcessAnswer:
    @pytest.fixture
    def question_and_session(self):
        question = Question(
            topic="Test",
            question_text="Test question?",
            choices=[
                QuestionChoice(text="A", is_correct=True),
                QuestionChoice(text="B", is_correct=False),
                QuestionChoice(text="C", is_correct=True),
            ],
            explanation="A and C are correct",
            is_multi_choice=True,
        )

        session = QuizSession(
            topics=[WeightedTopic(topic="Test", weight=1.0)],
            total_questions=1,
            difficulty="medium",
            batch_size=5,
            max_incorrect_recycles=2,
            quiz_mode="fresh",
            questions_per_topic={"Test": 1},
        )
        session.all_generated_questions = [question]
        session.active_question_pool = [question.id, "next-question-id"]

        return question, session

    def test_process_answer_correct(self, question_and_session):
        question, session = question_and_session

        state = {
            "quiz_session": session,
            "current_question": question,
            "user_input": [0, 2],  # Correct answer indices
        }

        result = process_answer(state)

        assert len(session.user_answers) == 1
        assert session.user_answers[0].is_correct == True
        assert session.current_question_index == 1  # Advanced
        assert "✓ Correct!" in result["feedback_request"]
        assert result["next_node"] == "check_completion"

    def test_process_answer_incorrect(self, question_and_session):
        question, session = question_and_session

        state = {
            "quiz_session": session,
            "current_question": question,
            "user_input": [1],  # Incorrect answer
        }

        result = process_answer(state)

        assert session.user_answers[0].is_correct == False
        assert "✗ Incorrect" in result["feedback_request"]
        # Question should be added for recycling
        assert question.id in session.active_question_pool[2:]  # Added to end

    def test_process_answer_no_input(self, question_and_session):
        question, session = question_and_session

        state = {
            "quiz_session": session,
            "current_question": question,
            "user_input": None,
        }

        result = process_answer(state)

        assert result["next_node"] == "present_question"
        assert len(session.user_answers) == 0

    def test_process_answer_invalid_indices(self, question_and_session):
        question, session = question_and_session

        state = {
            "quiz_session": session,
            "current_question": question,
            "user_input": [5],  # Out of range
        }

        with pytest.raises(ValueError, match="Index 5 out of range"):
            process_answer(state)

    def test_process_answer_empty_list(self, question_and_session):
        question, session = question_and_session

        state = {
            "quiz_session": session,
            "current_question": question,
            "user_input": [],
            "feedback_request": None,
            "next_node": None,
        }

        result = process_answer(state)

        assert "feedback_request" in result


class TestCheckCompletion:
    def test_check_completion_not_done(self):
        session = QuizSession(
            topics=[WeightedTopic(topic="Test", weight=1.0)],
            total_questions=1,
            difficulty="medium",
            batch_size=5,
            max_incorrect_recycles=2,
            quiz_mode="fresh",
            questions_per_topic={"Test": 1},
        )
        session.active_question_pool = ["q1", "q2"]
        session.current_question_index = 1  # Still has questions

        state = {"quiz_session": session}

        result = check_completion(state)

        assert result["next_node"] == "present_question"

    def test_check_completion_done(self):
        session = QuizSession(
            topics=[WeightedTopic(topic="Test", weight=1.0)],
            total_questions=2,
            questions_per_topic={"Test": 2},
        )
        session.active_question_pool = ["q1", "q2"]
        session.current_question_index = 2  # Past the end

        state = {"quiz_session": session}

        result = check_completion(state)

        assert result["next_node"] == "finalize_results"

    def test_check_completion_no_session(self):
        state = {"quiz_session": None}

        result = check_completion(state)

        assert result["next_node"] == "finalize_results"


class TestFinalizeResults:
    @pytest.fixture
    def completed_session(self):
        session = QuizSession(
            topics=[
                WeightedTopic(topic="Algorithms", weight=0.5),
                WeightedTopic(topic="Data Structures", weight=0.5),
            ],
            total_questions=2,
            difficulty="medium",
            batch_size=5,
            max_incorrect_recycles=2,
            quiz_mode="fresh",
            questions_per_topic={"Algorithms": 1, "Data Structures": 1},
        )

        # Add some questions
        q1 = Question(
            topic="Algorithms",
            question_text="Q1",
            choices=[QuestionChoice(text="A", is_correct=True)],
            explanation="Exp1",
        )
        q2 = Question(
            topic="Data Structures",
            question_text="Q2",
            choices=[QuestionChoice(text="B", is_correct=True)],
            explanation="Exp2",
        )
        session.all_generated_questions = [q1, q2]

        # Add answers
        session.user_answers = [
            UserAnswer(question_id=q1.id, selected_choice_indices=[0], is_correct=True),
            UserAnswer(
                question_id=q2.id, selected_choice_indices=[0], is_correct=False
            ),
        ]

        return session

    def test_finalize_results(self, completed_session):
        state = {"quiz_session": completed_session}

        result = finalize_results(state)

        assert "quiz_results" in result
        quiz_results = result["quiz_results"]
        assert quiz_results.total_questions == 2
        assert quiz_results.correct_answers == 1
        assert quiz_results.score_percentage == 50.0
        assert result["quiz_complete"] == True
        assert result["next_node"] == "END"
        assert "Quiz Complete!" in result["feedback_request"]

    def test_finalize_results_topic_scores(self, completed_session):
        state = {"quiz_session": completed_session}

        result = finalize_results(state)

        topic_scores = result["quiz_results"].topic_scores
        assert "Algorithms" in topic_scores
        assert "Data Structures" in topic_scores
        assert topic_scores["Algorithms"]["correct"] == 1
        assert topic_scores["Algorithms"]["total"] == 1
        assert topic_scores["Data Structures"]["correct"] == 0
        assert topic_scores["Data Structures"]["total"] == 1

    def test_finalize_results_no_session(self):
        state = {"quiz_session": None}

        with pytest.raises(ValueError, match="Quiz session not initialized"):
            finalize_results(state)


class TestRouteNext:
    def test_route_next_valid_nodes(self):
        test_cases = [
            ("initialize_quiz", "initialize_quiz"),
            ("present_question", "present_question"),
            ("process_answer", "process_answer"),
            ("END", "__end__"),
        ]

        for input_node, expected in test_cases:
            state = {"next_node": input_node}
            result = route_next(state)
            assert result == expected

    def test_route_next_missing_node(self):
        state = {}
        result = route_next(state)
        assert result == "__end__"

    def test_route_next_default_end(self):
        state = {"next_node": "some_invalid_node"}
        result = route_next(state)
        assert result == "some_invalid_node"  # Passes through unknown nodes


class TestHelperFunctions:

    @patch("Agent.Quiz.nodes.get_llm")
    def test_process_user_questions(self, mock_get_llm):
        mock_llm = Mock()
        mock_response = UserQuestionResponse(
            correct_answers=["Recursion"],
            wrong_options=["Iteration", "Loop"],
            explanation="Recursion is when a function calls itself",
            assigned_topic="Algorithms",
            is_multi_choice=False,
        )
        mock_llm.invoke.return_value = mock_response
        mock_get_llm.return_value.with_structured_output.return_value = mock_llm

        topics = [WeightedTopic(topic="Algorithms", weight=1.0)]
        user_questions = ["What is recursion?"]

        result = _process_user_questions(user_questions, topics, "medium")

        assert len(result) == 1
        assert result[0].question_text == "What is recursion?"
        assert result[0].topic == "Algorithms"
        assert len(result[0].choices) >= 2  # 1 correct + 2 wrong

    def test_remove_duplicate_questions(self):
        q1 = Question(
            topic="Test",
            question_text="What is an algorithm?",
            choices=[QuestionChoice(text="A", is_correct=True)],
            explanation="Test",
        )
        q2 = Question(
            topic="Test",
            question_text="What is an algorithm exactly?",  # Very similar
            choices=[QuestionChoice(text="B", is_correct=True)],
            explanation="Test",
        )
        q3 = Question(
            topic="Test",
            question_text="What is a data structure?",  # Different
            choices=[QuestionChoice(text="C", is_correct=True)],
            explanation="Test",
        )

        questions = [q1, q2, q3]
        result = _remove_duplicate_questions(questions)

        # Should remove q2 as duplicate of q1
        assert len(result) == 2
        question_texts = [q.question_text for q in result]
        assert "What is an algorithm?" in question_texts
        assert "What is a data structure?" in question_texts

    def test_create_fallback_questions(self):
        questions = _create_fallback_questions("Algorithms", 3, "medium")

        assert len(questions) == 3
        for q in questions:
            assert q.topic == "Algorithms"
            assert q.difficulty == "medium"
            assert len(q.choices) >= 2

    def test_format_question_for_user(self):
        question = Question(
            topic="Test",
            question_text="Sample question?",
            choices=[
                QuestionChoice(text="Option A", is_correct=True),
                QuestionChoice(text="Option B", is_correct=False),
            ],
            explanation="A is correct",
            is_multi_choice=False,
        )

        result = _format_question_for_user(question)

        assert "Sample question?" in result
        assert "1. Option A" in result
        assert "2. Option B" in result
        assert "(Select one answer)" in result

    def test_create_answer_feedback_correct(self):
        question = Question(
            topic="Test",
            question_text="Test?",
            choices=[
                QuestionChoice(text="Right", is_correct=True),
                QuestionChoice(text="Wrong", is_correct=False),
            ],
            explanation="Because it's right",
        )

        feedback = _create_answer_feedback(question, [0], True)

        assert "✓ Correct!" in feedback
        assert "Right" in feedback
        assert "Because it's right" in feedback

    def test_create_answer_feedback_incorrect(self):
        question = Question(
            topic="Test",
            question_text="Test?",
            choices=[
                QuestionChoice(text="Right", is_correct=True),
                QuestionChoice(text="Wrong", is_correct=False),
            ],
            explanation="Because it's right",
        )

        feedback = _create_answer_feedback(question, [1], False)

        assert "✗ Incorrect" in feedback
        assert "Wrong" in feedback
        assert "Correct answer(s): Right" in feedback

    def test_format_quiz_results(self):
        results = QuizResults(
            session_id="test",
            total_questions=10,
            correct_answers=8,
            score_percentage=80.0,
            topic_scores={
                "Algorithms": {"correct": 5, "total": 6, "percentage": 83.3},
                "Data Structures": {"correct": 3, "total": 4, "percentage": 75.0},
            },
        )

        formatted = _format_quiz_results(results)

        assert "Quiz Complete!" in formatted
        assert "8/10 (80.0%)" in formatted
        assert "Algorithms: 5/6" in formatted
        assert "🌟 Excellent work!" in formatted  # Score >= 80


if __name__ == "__main__":
    pytest.main([__file__])
