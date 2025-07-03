import pytest
from unittest.mock import patch, Mock
from fastapi import HTTPException


class TestQuizAPI:
    """Test Quiz API endpoints"""

    def test_create_quiz_success(self, client, mock_user_id):
        """Test successful quiz creation"""
        with patch(
            "src.Testaiownik.Backend.api.quiz.get_user_id", return_value=mock_user_id
        ):
            with patch("src.Testaiownik.Backend.api.quiz.create_quiz") as mock_create:
                mock_quiz = Mock()
                mock_quiz.quiz_id = "quiz_456"
                mock_quiz.created_at = "2025-01-15T10:00:00Z"
                mock_quiz.status = "created"
                mock_create.return_value = mock_quiz

                response = client.post("/api/quiz/create")

                assert response.status_code == 200
                data = response.json()
                assert data["quiz_id"] == "quiz_456"
                assert data["status"] == "created"

    def test_create_quiz_unauthorized(self, client):
        """Test quiz creation without user ID"""
        response = client.post("/api/quiz/create")
        assert response.status_code == 401

    def test_list_quizzes_success(self, client, mock_user_id):
        """Test successful quiz listing"""
        with patch(
            "src.Testaiownik.Backend.api.quiz.get_user_id", return_value=mock_user_id
        ):
            with patch(
                "src.Testaiownik.Backend.api.quiz.get_quizzes_by_user"
            ) as mock_get:
                mock_quizzes = [
                    Mock(
                        quiz_id="quiz_1",
                        status="created",
                        created_at="2025-01-15T10:00:00Z",
                    ),
                    Mock(
                        quiz_id="quiz_2",
                        status="in_progress",
                        created_at="2025-01-15T11:00:00Z",
                    ),
                ]
                # Add document_count attribute
                for quiz in mock_quizzes:
                    quiz.documents = [Mock(), Mock()]  # 2 documents each

                mock_get.return_value = mock_quizzes

                response = client.get("/api/quiz/list")

                assert response.status_code == 200
                data = response.json()
                assert len(data["quizzes"]) == 2
                assert data["quizzes"][0]["quiz_id"] == "quiz_1"

    def test_start_quiz_success(self, client, mock_user_id):
        """Test successful quiz start"""
        with patch(
            "src.Testaiownik.Backend.api.quiz.get_user_id", return_value=mock_user_id
        ):
            with patch("src.Testaiownik.Backend.api.quiz.validate_quiz_access"):
                with patch(
                    "src.Testaiownik.Backend.api.quiz.quiz_service"
                ) as mock_service:
                    mock_service.start_quiz.return_value = {
                        "status": "started",
                        "current_question": {
                            "question_id": "q1",
                            "question_text": "What is 2+2?",
                            "choices": ["2", "3", "4", "5"],
                            "question_number": 1,
                            "total_questions": 10,
                        },
                    }

                    request_data = {"total_questions": 10, "difficulty": "medium"}

                    response = client.post(
                        "/api/quiz/quiz_456/start", json=request_data
                    )

                    assert response.status_code == 200
                    data = response.json()
                    assert data["status"] == "started"
                    assert "current_question" in data

    def test_answer_question_correct(self, client, mock_user_id):
        """Test correct answer submission"""
        with patch(
            "src.Testaiownik.Backend.api.quiz.get_user_id", return_value=mock_user_id
        ):
            with patch("src.Testaiownik.Backend.api.quiz.validate_quiz_access"):
                with patch(
                    "src.Testaiownik.Backend.api.quiz.quiz_service"
                ) as mock_service:
                    mock_service.answer_question.return_value = {
                        "correct": True,
                        "explanation": "2+2=4",
                        "next_question": {"question_id": "q2"},
                    }

                    request_data = {"question_id": "q1", "selected_choice": "4"}

                    response = client.post(
                        "/api/quiz/quiz_456/answer", json=request_data
                    )

                    assert response.status_code == 200
                    data = response.json()
                    assert data["correct"] is True
                    assert "explanation" in data

    def test_get_quiz_results(self, client, mock_user_id):
        """Test quiz results retrieval"""
        with patch(
            "src.Testaiownik.Backend.api.quiz.get_user_id", return_value=mock_user_id
        ):
            with patch("src.Testaiownik.Backend.api.quiz.validate_quiz_access"):
                with patch(
                    "src.Testaiownik.Backend.api.quiz.quiz_service"
                ) as mock_service:
                    mock_service.get_quiz_results.return_value = {
                        "score": 8,
                        "total_questions": 10,
                        "percentage": 80.0,
                    }

                    response = client.get("/api/quiz/quiz_456/results")

                    assert response.status_code == 200
                    data = response.json()
                    assert "score" in data
                    assert "percentage" in data

    def test_quiz_not_found(self, client, mock_user_id):
        """Test quiz not found error"""
        with patch(
            "src.Testaiownik.Backend.api.quiz.get_user_id", return_value=mock_user_id
        ):
            with patch(
                "src.Testaiownik.Backend.api.quiz.validate_quiz_access"
            ) as mock_validate:
                mock_validate.side_effect = HTTPException(
                    status_code=404, detail="Quiz not found"
                )

                response = client.get("/api/quiz/nonexistent/results")
                assert response.status_code == 404
