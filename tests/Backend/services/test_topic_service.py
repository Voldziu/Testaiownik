# tests/Backend/services/test_topic_service.py
import pytest
from unittest.mock import Mock, patch
from src.Testaiownik.Backend.services.topic_service import TopicService


class TestTopicService:
    """Test TopicService functionality - only real methods"""

    @pytest.fixture
    def topic_service(self):
        return TopicService()

    def test_normalize_weights_empty_list(self, topic_service):
        """Test normalizing weights with empty list"""
        topics = []
        result = topic_service.normalize_weights(topics)
        assert result == []

    def test_normalize_weights_equal_distribution(self, topic_service):
        """Test normalizing weights with zero weights"""
        topics = [
            {"topic": "Topic1", "weight": 0},
            {"topic": "Topic2", "weight": 0},
            {"topic": "Topic3", "weight": 0},
        ]
        result = topic_service.normalize_weights(topics)

        for topic in result:
            assert abs(topic["weight"] - 0.33) < 0.1

    def test_normalize_weights_already_normalized(self, topic_service):
        """Test normalizing already normalized weights"""
        topics = [
            {"topic": "Topic1", "weight": 0.4},
            {"topic": "Topic2", "weight": 0.6},
        ]
        result = topic_service.normalize_weights(topics)

        assert result[0]["weight"] == 0.4
        assert result[1]["weight"] == 0.6

    def test_normalize_weights_needs_normalization(self, topic_service):
        """Test normalizing weights that need adjustment"""
        topics = [
            {"topic": "Topic1", "weight": 0.8},
            {"topic": "Topic2", "weight": 0.4},
        ]
        result = topic_service.normalize_weights(topics)

        total_weight = sum(topic["weight"] for topic in result)
        assert abs(total_weight - 1.0) < 0.01

    def test_add_topic_success(self, topic_service, mock_db_session, mock_quiz):
        """Test successful topic addition"""
        quiz_id = "quiz_456"
        topic_name = "New Topic"
        weight = 0.2
        user_id = "user_123"

        with patch(
            "src.Testaiownik.Backend.services.topic_service.get_quiz"
        ) as mock_get_quiz:
            with patch(
                "src.Testaiownik.Backend.services.topic_service.update_topic_data"
            ) as mock_update:
                with patch(
                    "src.Testaiownik.Backend.services.topic_service.log_activity"
                ):
                    mock_get_quiz.return_value = mock_quiz
                    mock_update.return_value = True

                    result = topic_service.add_topic(
                        quiz_id, topic_name, weight, user_id, mock_db_session
                    )

                    assert result["success"] is True
                    assert result["added_topic"]["topic"] == topic_name
                    assert result["total_topics"] == 3  

    def test_add_topic_already_exists(self, topic_service, mock_db_session, mock_quiz):
        """Test adding topic that already exists"""
        quiz_id = "quiz_456"
        topic_name = "Algorithms"  
        weight = 0.2
        user_id = "user_123"

        with patch(
            "src.Testaiownik.Backend.services.topic_service.get_quiz"
        ) as mock_get_quiz:
            mock_get_quiz.return_value = mock_quiz

            with pytest.raises(ValueError, match="Topic already exists"):
                topic_service.add_topic(
                    quiz_id, topic_name, weight, user_id, mock_db_session
                )

    def test_add_topic_quiz_not_found(self, topic_service, mock_db_session):
        """Test adding topic to non-existent quiz"""
        quiz_id = "quiz_456"
        topic_name = "New Topic"
        weight = 0.2
        user_id = "user_123"

        with patch(
            "src.Testaiownik.Backend.services.topic_service.get_quiz"
        ) as mock_get_quiz:
            mock_get_quiz.return_value = None

            with pytest.raises(ValueError, match="Quiz not found"):
                topic_service.add_topic(
                    quiz_id, topic_name, weight, user_id, mock_db_session
                )

    def test_delete_topic_success(self, topic_service, mock_db_session, mock_quiz):
        """Test successful topic deletion"""
        quiz_id = "quiz_456"
        topic_name = "Algorithms"
        user_id = "user_123"

        with patch(
            "src.Testaiownik.Backend.services.topic_service.get_quiz"
        ) as mock_get_quiz:
            with patch(
                "src.Testaiownik.Backend.services.topic_service.update_topic_data"
            ) as mock_update:
                with patch(
                    "src.Testaiownik.Backend.services.topic_service.log_activity"
                ):
                    mock_get_quiz.return_value = mock_quiz
                    mock_update.return_value = True

                    result = topic_service.delete_topic(
                        quiz_id, topic_name, user_id, mock_db_session
                    )

                    assert result["success"] is True
                    assert result["deleted_topic"] == topic_name
                    assert result["remaining_topics"] == 1  

    def test_delete_topic_not_found(self, topic_service, mock_db_session, mock_quiz):
        """Test deleting topic that doesn't exist"""
        quiz_id = "quiz_456"
        topic_name = "NonExistent Topic"
        user_id = "user_123"

        with patch(
            "src.Testaiownik.Backend.services.topic_service.get_quiz"
        ) as mock_get_quiz:
            mock_get_quiz.return_value = mock_quiz

            with pytest.raises(ValueError, match="Topic not found"):
                topic_service.delete_topic(
                    quiz_id, topic_name, user_id, mock_db_session
                )

    def test_delete_topic_all_topics(self, topic_service, mock_db_session):
        """Test deleting all topics (should fail)"""
        quiz_id = "quiz_456"
        topic_name = "Only Topic"
        user_id = "user_123"

        with patch(
            "src.Testaiownik.Backend.services.topic_service.get_quiz"
        ) as mock_get_quiz:
            mock_quiz = Mock()
            mock_quiz.suggested_topics = [{"topic": "Only Topic", "weight": 1.0}]
            mock_get_quiz.return_value = mock_quiz

            with pytest.raises(ValueError, match="Cannot delete all topics"):
                topic_service.delete_topic(
                    quiz_id, topic_name, user_id, mock_db_session
                )

    def test_update_topic_name_success(self, topic_service, mock_db_session, mock_quiz):
        """Test successful topic name update"""
        quiz_id = "quiz_456"
        current_topic_name = "Algorithms"
        new_name = "Advanced Algorithms"
        user_id = "user_123"

        with patch(
            "src.Testaiownik.Backend.services.topic_service.get_quiz"
        ) as mock_get_quiz:
            with patch(
                "src.Testaiownik.Backend.services.topic_service.update_topic_data"
            ) as mock_update:
                with patch(
                    "src.Testaiownik.Backend.services.topic_service.log_activity"
                ):
                    mock_get_quiz.return_value = mock_quiz
                    mock_update.return_value = True

                    result = topic_service.update_topic(
                        quiz_id,
                        current_topic_name,
                        mock_db_session,
                        new_name=new_name,
                        user_id=user_id,
                    )

                    assert result.success is True
                    assert result.new_topic.topic == new_name

    def test_update_topic_weight_success(
        self, topic_service, mock_db_session, mock_quiz
    ):
        """Test successful topic weight update"""
        quiz_id = "quiz_456"
        current_topic_name = "Algorithms"
        new_weight = 0.8
        user_id = "user_123"

        with patch(
            "src.Testaiownik.Backend.services.topic_service.get_quiz"
        ) as mock_get_quiz:
            with patch(
                "src.Testaiownik.Backend.services.topic_service.update_topic_data"
            ) as mock_update:
                with patch(
                    "src.Testaiownik.Backend.services.topic_service.log_activity"
                ):
                    mock_get_quiz.return_value = mock_quiz
                    mock_update.return_value = True

                    result = topic_service.update_topic(
                        quiz_id,
                        current_topic_name,
                        mock_db_session,
                        new_weight=new_weight,
                        user_id=user_id,
                    )

                    assert result.success is True
                    assert result.new_topic.weight == 0.73

    def test_update_topic_not_found(self, topic_service, mock_db_session, mock_quiz):
        """Test updating topic that doesn't exist"""
        quiz_id = "quiz_456"
        current_topic_name = "NonExistent Topic"
        new_name = "Updated Topic"
        user_id = "user_123"

        with patch(
            "src.Testaiownik.Backend.services.topic_service.get_quiz"
        ) as mock_get_quiz:
            mock_get_quiz.return_value = mock_quiz

            with pytest.raises(ValueError, match="Topic not found"):
                topic_service.update_topic(
                    quiz_id,
                    current_topic_name,
                    mock_db_session,
                    new_name=new_name,
                    user_id=user_id,
                )

    def test_validate_topics_success(self, topic_service):
        """Test successful topic validation"""
        topics = [
            {"topic": "Topic1", "weight": 0.4},
            {"topic": "Topic2", "weight": 0.6},
        ]

        result = topic_service.validate_topics(topics)
        assert result is True

    def test_validate_topics_invalid_format(self, topic_service):
        """Test topic validation with invalid format"""
        topics = [
            {"name": "Topic1", "weight": 0.4},  
            {"topic": "Topic2", "weight": 0.6},
        ]

        result = topic_service.validate_topics(topics)
        assert result is False

    def test_validate_topics_invalid_weights(self, topic_service):
        """Test topic validation with invalid weights"""
        topics = [
            {"topic": "Topic1", "weight": -0.1},  
            {"topic": "Topic2", "weight": 0.6},
        ]

        result = topic_service.validate_topics(topics)
        assert result is False

    def test_export_topics_success(self, topic_service, mock_db_session, mock_quiz):
        """Test successful topic export"""
        quiz_id = "quiz_456"

        with patch(
            "src.Testaiownik.Backend.services.topic_service.get_quiz"
        ) as mock_get_quiz:
            mock_get_quiz.return_value = mock_quiz

            result = topic_service.export_topics(quiz_id, mock_db_session)

            assert result["success"] is True
            assert "export_data" in result
            assert len(result["export_data"]["suggested_topics"]) == 2

    def test_import_topics_success(self, topic_service, mock_db_session, mock_quiz):
        """Test successful topic import"""
        quiz_id = "quiz_456"
        user_id = "user_123"
        topics_data = {
            "suggested_topics": [
                {"topic": "Imported Topic 1", "weight": 0.5},
                {"topic": "Imported Topic 2", "weight": 0.5},
            ],
            "desired_topic_count": 2,
        }

        with patch(
            "src.Testaiownik.Backend.services.topic_service.update_topic_data"
        ) as mock_update:
            with patch("src.Testaiownik.Backend.services.topic_service.log_activity"):
                mock_update.return_value = True

                result = topic_service.import_topics(
                    quiz_id, topics_data, user_id, mock_db_session
                )

                assert result["success"] is True
                assert result["imported_topics"] == 2

    def test_import_topics_invalid_data(self, topic_service, mock_db_session):
        """Test importing topics with invalid data"""
        quiz_id = "quiz_456"
        user_id = "user_123"
        topics_data = {"invalid": "data"}  

        with pytest.raises(ValueError, match="Invalid topics data"):
            topic_service.import_topics(quiz_id, topics_data, user_id, mock_db_session)

    def test_reset_topic_analysis_success(self, topic_service, mock_db_session):
        """Test successful topic analysis reset"""
        quiz_id = "quiz_456"
        user_id = "user_123"

        with patch(
            "src.Testaiownik.Backend.services.topic_service.update_topic_data"
        ) as mock_update:
            with patch("src.Testaiownik.Backend.services.topic_service.log_activity"):
                mock_update.return_value = True

                result = topic_service.reset_topic_analysis(
                    quiz_id, user_id, mock_db_session
                )

                assert result["success"] is True
                assert result["new_status"] == "documents_indexed"
