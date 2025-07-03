import pytest
from unittest.mock import Mock, patch
from src.Testaiownik.Backend.services.topic_service import TopicService


class TestTopicService:
    """Test TopicService functionality"""

    @pytest.fixture
    def topic_service(self):
        return TopicService()

    @pytest.fixture
    def mock_testaiownik_runner(self):
        with patch(
            "src.Testaiownik.Backend.services.topic_service.TestaiownikRunner"
        ) as mock:
            runner = Mock()
            mock.return_value = runner
            yield runner

    def test_start_topic_analysis_success(self, topic_service, mock_testaiownik_runner):
        """Test successful topic analysis start"""
        quiz_id = "quiz_456"
        config = {"desired_topic_count": 10, "batch_size": 40}

        mock_testaiownik_runner.start_topic_analysis.return_value = {
            "topic_session_id": "topic_789",
            "status": "analyzing",
            "estimated_completion": "2025-01-15T10:35:00Z",
        }

        result = topic_service.start_topic_analysis(quiz_id, config)

        assert result["topic_session_id"] == "topic_789"
        assert result["status"] == "analyzing"
        mock_testaiownik_runner.start_topic_analysis.assert_called_once()

    def test_get_topic_session_awaiting_feedback(
        self, topic_service, mock_testaiownik_runner
    ):
        """Test topic session in awaiting feedback state"""
        topic_session_id = "topic_789"

        mock_testaiownik_runner.get_topic_session.return_value = {
            "topic_session_id": topic_session_id,
            "status": "awaiting_feedback",
            "suggested_topics": [
                {"topic": "Algorithmic Complexity", "weight": 0.25},
                {"topic": "Data Structures", "weight": 0.20},
                {"topic": "Sorting Algorithms", "weight": 0.18},
                {"topic": "Search Algorithms", "weight": 0.15},
                {"topic": "Graph Algorithms", "weight": 0.12},
                {"topic": "Dynamic Programming", "weight": 0.10},
            ],
            "feedback_request": "I found these topics in your documents. Would you like to modify or add any topics?",
            "conversation_history": [],
        }

        result = topic_service.get_topic_session(topic_session_id)

        assert result["status"] == "awaiting_feedback"
        assert len(result["suggested_topics"]) == 6
        assert result["suggested_topics"][0]["topic"] == "Algorithmic Complexity"
        assert result["suggested_topics"][0]["weight"] == 0.25

    def test_submit_feedback_success(self, topic_service, mock_testaiownik_runner):
        """Test successful feedback submission"""
        topic_session_id = "topic_789"
        feedback_data = {
            "feedback_text": "Add more advanced algorithms and remove basic topics",
            "confirmed_topics": [
                "Advanced Sorting Algorithms",
                "Graph Algorithms",
                "Dynamic Programming",
                "Greedy Algorithms",
            ],
        }

        mock_testaiownik_runner.submit_feedback.return_value = {
            "topic_session_id": topic_session_id,
            "status": "completed",
            "confirmed_topics": feedback_data["confirmed_topics"],
            "feedback_applied": True,
        }

        result = topic_service.submit_feedback(topic_session_id, feedback_data)

        assert result["status"] == "completed"
        assert result["confirmed_topics"] == feedback_data["confirmed_topics"]
        assert result["feedback_applied"] is True
        mock_testaiownik_runner.submit_feedback.assert_called_once()

    def test_submit_feedback_continue_iteration(
        self, topic_service, mock_testaiownik_runner
    ):
        """Test feedback submission that continues iteration"""
        topic_session_id = "topic_789"
        feedback_data = {
            "feedback_text": "Need more specific computer science topics",
            "confirmed_topics": None,
        }

        mock_testaiownik_runner.submit_feedback.return_value = {
            "topic_session_id": topic_session_id,
            "status": "awaiting_feedback",
            "suggested_topics": [
                {"topic": "Computer Networks", "weight": 0.20},
                {"topic": "Operating Systems", "weight": 0.18},
                {"topic": "Database Systems", "weight": 0.16},
                {"topic": "Software Engineering", "weight": 0.14},
                {"topic": "Machine Learning", "weight": 0.12},
            ],
            "feedback_request": "I've refined the topics based on your feedback. How do these look?",
            "conversation_history": [
                {
                    "user": "Need more specific computer science topics",
                    "assistant": "I've refined...",
                }
            ],
        }

        result = topic_service.submit_feedback(topic_session_id, feedback_data)

        assert result["status"] == "awaiting_feedback"
        assert len(result["suggested_topics"]) == 5
        assert len(result["conversation_history"]) == 1

    def test_get_topic_session_not_found(self, topic_service, mock_testaiownik_runner):
        """Test topic session not found"""
        topic_session_id = "nonexistent"

        mock_testaiownik_runner.get_topic_session.side_effect = Exception(
            "Topic session not found"
        )

        with pytest.raises(Exception) as exc_info:
            topic_service.get_topic_session(topic_session_id)

        assert "Topic session not found" in str(exc_info.value)

    def test_get_topic_session_completed(self, topic_service, mock_testaiownik_runner):
        """Test completed topic session"""
        topic_session_id = "topic_789"

        mock_testaiownik_runner.get_topic_session.return_value = {
            "topic_session_id": topic_session_id,
            "status": "completed",
            "confirmed_topics": [
                "Advanced Algorithms",
                "Data Structures",
                "Complexity Analysis",
            ],
            "final_weights": {
                "Advanced Algorithms": 0.4,
                "Data Structures": 0.35,
                "Complexity Analysis": 0.25,
            },
            "completion_time": "2025-01-15T10:45:00Z",
        }

        result = topic_service.get_topic_session(topic_session_id)

        assert result["status"] == "completed"
        assert len(result["confirmed_topics"]) == 3
        assert "final_weights" in result
        assert result["final_weights"]["Advanced Algorithms"] == 0.4
