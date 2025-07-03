import pytest
from unittest.mock import Mock, patch, AsyncMock
from src.Testaiownik.Backend.services.quiz_service import QuizService


class TestQuizService:
    """Test QuizService functionality - only real methods"""

    @pytest.fixture
    def quiz_service(self):
        return QuizService()

    # def test_start_topic_analysis_success(
    #     self, quiz_service, mock_db_session, mock_quiz
    # ):
    #     """Test successful topic analysis start"""
    #     quiz_id = "quiz_456"
    #     user_id = "user_123"
    #     desired_topic_count = 10

    #     with patch(
    #         "src.Testaiownik.Backend.services.quiz_service.get_quiz"
    #     ) as mock_get_quiz:
    #         with patch(
    #             "src.Testaiownik.Backend.services.quiz_service.RAGRetriever"
    #         ) as mock_rag:
    #             with patch(
    #                 "src.Testaiownik.Backend.services.quiz_service.create_agent_graph"
    #             ) as mock_graph:
    #                 mock_get_quiz.return_value = mock_quiz
    #                 mock_retriever = Mock()
    #                 mock_rag.return_value = mock_retriever
    #                 mock_agent_graph = Mock()
    #                 mock_graph.return_value = mock_agent_graph

    #                 result = quiz_service.start_topic_analysis(
    #                     quiz_id, user_id, mock_db_session, desired_topic_count
    #                 )

    #                 assert result["quiz_id"] == quiz_id
    #                 assert result["status"] == "analyzing"

    def test_confirm_topics_success(self, quiz_service, mock_db_session, mock_quiz):
        """Test successful topic confirmation"""
        quiz_id = "quiz_456"
        user_id = "user_123"

        with patch(
            "src.Testaiownik.Backend.services.quiz_service.get_quiz"
        ) as mock_get_quiz:
            with patch(
                "src.Testaiownik.Backend.services.quiz_service.confirm_quiz_topics"
            ) as mock_confirm:
                with patch(
                    "src.Testaiownik.Backend.services.quiz_service.log_activity"
                ):
                    mock_get_quiz.return_value = mock_quiz
                    mock_confirm.return_value = True

                    result = quiz_service.confirm_topics(
                        quiz_id, user_id, mock_db_session
                    )

                    assert result["quiz_id"] == quiz_id
                    assert result["ready_for_quiz"] is True
                    assert len(result["confirmed_topics"]) == 2

    def test_confirm_topics_no_suggested_topics(self, quiz_service, mock_db_session):
        """Test topic confirmation with no suggested topics"""
        quiz_id = "quiz_456"
        user_id = "user_123"

        with patch(
            "src.Testaiownik.Backend.services.quiz_service.get_quiz"
        ) as mock_get_quiz:
            mock_quiz = Mock()
            mock_quiz.suggested_topics = None
            mock_get_quiz.return_value = mock_quiz

            with pytest.raises(ValueError, match="No topics available to confirm"):
                quiz_service.confirm_topics(quiz_id, user_id, mock_db_session)

    @pytest.mark.asyncio
    async def test_start_quiz_success(self, quiz_service, mock_db_session, mock_quiz):
        """Test successful quiz start"""
        quiz_id = "quiz_456"
        confirmed_topics = [{"topic": "Algorithms", "weight": 0.5}]
        total_questions = 10
        difficulty = "medium"
        user_questions = ["What is recursion?"]
        user_id = "user_123"

        with patch(
            "src.Testaiownik.Backend.services.quiz_service.get_quiz"
        ) as mock_get_quiz:
            with patch(
                "src.Testaiownik.Backend.services.quiz_service.RAGRetriever"
            ) as mock_rag:
                with patch(
                    "src.Testaiownik.Backend.services.quiz_service.create_quiz_graph"
                ) as mock_graph:
                    with patch(
                        "src.Testaiownik.Backend.services.quiz_service.start_quiz_execution"
                    ) as mock_start:
                        mock_get_quiz.return_value = mock_quiz
                        mock_retriever = Mock()
                        mock_rag.return_value = mock_retriever
                        mock_quiz_graph = Mock()
                        mock_graph.return_value = mock_quiz_graph
                        mock_start.return_value = True

                        result = await quiz_service.start_quiz(
                            quiz_id,
                            confirmed_topics,
                            total_questions,
                            difficulty,
                            user_questions,
                            user_id,
                            mock_db_session,
                        )

                        assert result is True

    def test_get_quiz_results_not_completed(
        self, quiz_service, mock_db_session, mock_quiz
    ):
        """Test getting results from incomplete quiz"""
        quiz_id = "quiz_456"

        with patch(
            "src.Testaiownik.Backend.services.quiz_service.get_quiz"
        ) as mock_get_quiz:
            mock_quiz.status = "quiz_active"
            mock_quiz.quiz_results = None
            mock_get_quiz.return_value = mock_quiz

            result = quiz_service.get_quiz_results(quiz_id, mock_db_session)

            assert result is None

    # def test_get_quiz_preview_success(self, quiz_service, mock_db_session, mock_quiz):
    #     """Test getting quiz preview"""
    #     quiz_id = "quiz_456"

    #     with patch(
    #         "src.Testaiownik.Backend.services.quiz_service.get_quiz"
    #     ) as mock_get_quiz:
    #         mock_quiz.difficulty = "medium"
    #         mock_get_quiz.return_value = mock_quiz

    #         result = quiz_service.get_quiz_preview(quiz_id, mock_db_session)

    #         assert len(result["topics"]) == 2

    def test_pause_quiz_success(self, quiz_service, mock_db_session):
        """Test pausing quiz"""
        quiz_id = "quiz_456"

        with patch(
            "src.Testaiownik.Backend.services.quiz_service.update_quiz"
        ) as mock_update:
            mock_update.return_value = True

            result = quiz_service.pause_quiz(quiz_id, mock_db_session)

            assert result is True
            mock_update.assert_called_once_with(
                mock_db_session, quiz_id, status="paused"
            )

    def test_resume_quiz_success(self, quiz_service, mock_db_session):
        """Test resuming quiz"""
        quiz_id = "quiz_456"

        with patch(
            "src.Testaiownik.Backend.services.quiz_service.update_quiz"
        ) as mock_update:
            mock_update.return_value = True

            result = quiz_service.resume_quiz(quiz_id, mock_db_session)

            assert result is True
            mock_update.assert_called_once_with(
                mock_db_session, quiz_id, status="quiz_active"
            )

    def test_restore_topic_session_success(
        self, quiz_service, mock_db_session, mock_quiz
    ):
        """Test restoring topic session"""
        quiz_id = "quiz_456"

        with patch(
            "src.Testaiownik.Backend.services.quiz_service.get_quiz"
        ) as mock_get_quiz:
            with patch(
                "src.Testaiownik.Backend.services.quiz_service.RAGRetriever"
            ) as mock_rag:
                with patch(
                    "src.Testaiownik.Backend.services.quiz_service.create_agent_graph"
                ) as mock_graph:
                    mock_quiz.langgraph_topic_state = {"some": "state"}
                    mock_get_quiz.return_value = mock_quiz
                    mock_retriever = Mock()
                    mock_rag.return_value = mock_retriever
                    mock_agent_graph = Mock()
                    mock_graph.return_value = mock_agent_graph

                    result = quiz_service._restore_topic_session(
                        quiz_id, mock_db_session
                    )

                    assert result is True
                    assert quiz_id in quiz_service.active_topic_graphs
