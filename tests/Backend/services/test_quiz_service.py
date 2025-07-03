import pytest
from unittest.mock import Mock, patch, MagicMock
from src.Testaiownik.Backend.services.quiz_service import QuizService


class TestQuizService:
    """Test QuizService functionality"""

    @pytest.fixture
    def quiz_service(self):
        return QuizService()

    @pytest.fixture
    def mock_quiz_runner(self):
        with patch("src.Testaiownik.Backend.services.quiz_service.QuizRunner") as mock:
            runner = Mock()
            mock.return_value = runner
            yield runner

    def test_start_quiz_success(self, quiz_service, mock_quiz_runner):
        """Test successful quiz start"""
        quiz_id = "quiz_456"
        request_data = {
            "total_questions": 10,
            "difficulty": "medium",
            "topics": ["Algorithms", "Data Structures"],
        }

        # Mock the runner's quiz start response
        mock_quiz_runner.start_quiz.return_value = {
            "status": "started",
            "current_question": {
                "question_id": "q1",
                "question_text": "What is the time complexity of binary search?",
                "choices": ["O(1)", "O(log n)", "O(n)", "O(n²)"],
                "question_number": 1,
                "total_questions": 10,
            },
        }

        result = quiz_service.start_quiz(quiz_id, request_data)

        assert result["status"] == "started"
        assert "current_question" in result
        assert result["current_question"]["question_number"] == 1
        mock_quiz_runner.start_quiz.assert_called_once()

    def test_answer_question_correct(self, quiz_service, mock_quiz_runner):
        """Test correct answer submission"""
        quiz_id = "quiz_456"
        answer_data = {"question_id": "q1", "selected_choice": "O(log n)"}

        mock_quiz_runner.answer_question.return_value = {
            "correct": True,
            "explanation": "Binary search has O(log n) time complexity because it divides the search space in half with each iteration.",
            "score": 1,
            "next_question": {
                "question_id": "q2",
                "question_text": "Which data structure uses LIFO?",
                "choices": ["Queue", "Stack", "Array", "Tree"],
                "question_number": 2,
                "total_questions": 10,
            },
        }

        result = quiz_service.answer_question(quiz_id, answer_data)

        assert result["correct"] is True
        assert "explanation" in result
        assert result["next_question"]["question_number"] == 2
        mock_quiz_runner.answer_question.assert_called_once()

    def test_answer_question_incorrect(self, quiz_service, mock_quiz_runner):
        """Test incorrect answer submission"""
        quiz_id = "quiz_456"
        answer_data = {"question_id": "q1", "selected_choice": "O(n)"}

        mock_quiz_runner.answer_question.return_value = {
            "correct": False,
            "explanation": "Incorrect. Binary search has O(log n) time complexity, not O(n).",
            "score": 0,
            "correct_answer": "O(log n)",
            "next_question": None,  # Last question
        }

        result = quiz_service.answer_question(quiz_id, answer_data)

        assert result["correct"] is False
        assert "correct_answer" in result
        assert result["next_question"] is None

    def test_get_quiz_results(self, quiz_service, mock_quiz_runner):
        """Test quiz results retrieval"""
        quiz_id = "quiz_456"

        mock_quiz_runner.get_quiz_results.return_value = {
            "quiz_id": quiz_id,
            "total_questions": 10,
            "correct_answers": 8,
            "score": 8,
            "percentage": 80.0,
            "questions": [
                {
                    "question_id": "q1",
                    "question_text": "What is binary search complexity?",
                    "user_answer": "O(log n)",
                    "correct_answer": "O(log n)",
                    "is_correct": True,
                }
            ],
            "completion_time": "2025-01-15T10:30:00Z",
        }

        result = quiz_service.get_quiz_results(quiz_id)

        assert result["score"] == 8
        assert result["percentage"] == 80.0
        assert len(result["questions"]) == 1
        mock_quiz_runner.get_quiz_results.assert_called_once_with(quiz_id)

    def test_get_explanation(self, quiz_service, mock_quiz_runner):
        """Test explanation retrieval for a question"""
        question_id = "q1"

        mock_quiz_runner.get_explanation.return_value = {
            "question_id": question_id,
            "explanation": "Binary search works by repeatedly dividing the search interval in half.",
            "source_chunks": [
                {
                    "text": "Binary search algorithm explanation...",
                    "source": "algorithms.pdf",
                    "page": 42,
                    "relevance_score": 0.95,
                }
            ],
            "additional_context": "Related topics: Divide and Conquer, Logarithmic Time",
        }

        result = quiz_service.get_explanation(question_id)

        assert result["question_id"] == question_id
        assert "explanation" in result
        assert "source_chunks" in result
        assert len(result["source_chunks"]) == 1

    def test_quiz_service_error_handling(self, quiz_service, mock_quiz_runner):
        """Test error handling in quiz service"""
        quiz_id = "quiz_456"

        mock_quiz_runner.start_quiz.side_effect = Exception("Quiz start failed")

        with pytest.raises(Exception) as exc_info:
            quiz_service.start_quiz(quiz_id, {})

        assert "Quiz start failed" in str(exc_info.value)
