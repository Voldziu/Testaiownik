import pytest
from unittest.mock import patch, Mock
from fastapi import HTTPException


class TestTopicsAPI:
    """Test Topics API endpoints"""

    def test_start_topic_analysis_success(
        self, client, mock_user_id, mock_topic_service
    ):
        """Test successful topic analysis start"""
        with patch(
            "src.Testaiownik.Backend.api.topics.get_user_id", return_value=mock_user_id
        ):
            with patch("src.Testaiownik.Backend.api.topics.validate_quiz_access"):
                request_data = {"desired_topic_count": 10, "batch_size": 40}

                response = client.post("/api/topics/quiz_456/start", json=request_data)

                assert response.status_code == 200
                data = response.json()
                assert data["topic_session_id"] == "topic_789"
                assert data["status"] == "analyzing"

    def test_get_topic_session_success(self, client, mock_user_id, mock_topic_service):
        """Test successful topic session retrieval"""
        with patch(
            "src.Testaiownik.Backend.api.topics.get_user_id", return_value=mock_user_id
        ):
            response = client.get("/api/topics/session/topic_789")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "awaiting_feedback"
            assert "suggested_topics" in data

    def test_submit_feedback_success(self, client, mock_user_id, mock_topic_service):
        """Test successful feedback submission"""
        with patch(
            "src.Testaiownik.Backend.api.topics.get_user_id", return_value=mock_user_id
        ):
            request_data = {
                "feedback_text": "Add more advanced algorithms topics",
                "confirmed_topics": ["Algorithms", "Data Structures"],
            }

            response = client.post(
                "/api/topics/session/topic_789/feedback", json=request_data
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "completed"

    def test_topic_session_not_found(self, client, mock_user_id, mock_topic_service):
        """Test topic session not found"""
        with patch(
            "src.Testaiownik.Backend.api.topics.get_user_id", return_value=mock_user_id
        ):
            mock_topic_service.get_topic_session.side_effect = HTTPException(
                status_code=404, detail="Topic session not found"
            )

            response = client.get("/api/topics/session/nonexistent")
            assert response.status_code == 404
