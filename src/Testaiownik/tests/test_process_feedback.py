# test_process_feedback.py - REGENERATED
from unittest.mock import Mock, patch
from Agent.TopicSelection.nodes import process_feedback


class TestProcessFeedbackStateLogic:
    """Test process_feedback state management - MOCK LLM responses"""

    def test_returns_request_feedback_when_no_user_input(self):
        """Test handling of missing user input"""
        state = {"suggested_topics": [{"topic": "Topic1", "weight": 1.0}]}
        result = process_feedback(state)

        assert result["next_node"] == "request_feedback"

    def test_returns_request_feedback_when_empty_user_input(self):
        """Test handling of empty string user input"""
        state = {
            "suggested_topics": [{"topic": "Topic1", "weight": 1.0}],
            "user_input": "",
        }
        result = process_feedback(state)

        assert result["next_node"] == "request_feedback"

    def test_builds_conversation_history_correctly(self):
        """Test conversation history accumulation logic"""
        existing_history = [
            {
                "suggested_topics": [{"topic": "Old1", "weight": 1.0}],
                "user_feedback": "Old feedback",
            }
        ]

        state = {
            "suggested_topics": [
                {"topic": "New1", "weight": 0.5},
                {"topic": "New2", "weight": 0.5},
            ],
            "user_input": "New feedback",
            "conversation_history": existing_history,
        }

        # Mock LLM to return accept action
        with patch("Agent.TopicSelection.nodes.get_llm") as mock_get_llm:
            mock_llm = Mock()
            mock_interpretation = Mock()
            mock_interpretation.user_feedback = Mock(
                action="accept",
                accepted_topics=["New1", "New2"],
                rejected_topics=[],
                modification_request="",
            )
            mock_llm.invoke.return_value = mock_interpretation
            mock_get_llm.return_value.with_structured_output.return_value = mock_llm

            result = process_feedback(state)

            # Should have both old and new history
            assert len(result["conversation_history"]) == 2
            assert result["conversation_history"][0]["user_feedback"] == "Old feedback"
            assert result["conversation_history"][1]["user_feedback"] == "New feedback"
            assert result["conversation_history"][1]["suggested_topics"] == [
                {"topic": "New1", "weight": 0.5},
                {"topic": "New2", "weight": 0.5},
            ]

    def test_handles_accept_action_response(self):
        """Test accept action leads to END state"""
        state = {
            "suggested_topics": [
                {"topic": "Topic1", "weight": 0.6},
                {"topic": "Topic2", "weight": 0.4},
            ],
            "user_input": "I accept these topics",
        }

        with patch("Agent.TopicSelection.nodes.get_llm") as mock_get_llm:
            mock_llm = Mock()
            mock_interpretation = Mock()
            mock_interpretation.user_feedback = Mock(
                action="accept",
                accepted_topics=["Topic1", "Topic2"],
                rejected_topics=[],
                modification_request="",
            )
            mock_llm.invoke.return_value = mock_interpretation
            mock_get_llm.return_value.with_structured_output.return_value = mock_llm

            result = process_feedback(state)

            assert result["next_node"] == "END"
            assert result["confirmed_topics"] == [
                {"topic": "Topic1", "weight": 0.6},
                {"topic": "Topic2", "weight": 0.4},
            ]

    def test_handles_modify_action_response(self):

        state = {
            "suggested_topics": [{"topic": "Topic1", "weight": 1.0}],
            "user_input": "Please modify these topics",
        }

        with patch("Agent.TopicSelection.nodes.get_llm") as mock_get_llm:
            mock_llm = Mock()
            mock_interpretation = Mock()
            mock_interpretation.user_feedback = Mock(
                action="modify",
                accepted_topics=["Topic1"],
                rejected_topics=[],
                want_to_add_topics=[],
                modification_request="Add more specific topics",
            )
            mock_llm.invoke.return_value = mock_interpretation
            mock_get_llm.return_value.with_structured_output.return_value = mock_llm

            result = process_feedback(state)

            assert result["next_node"] == "analyze_documents"
            assert result["feedback_request"] == "Add more specific topics"

    def test_fallback_to_suggested_topics_when_accepted_empty(self):
        """Test fallback logic when LLM returns empty accepted_topics"""
        state = {
            "suggested_topics": [
                {"topic": "Original1", "weight": 0.5},
                {"topic": "Original2", "weight": 0.5},
            ],
            "user_input": "I accept",
        }

        with patch("Agent.TopicSelection.nodes.get_llm") as mock_get_llm:
            mock_llm = Mock()
            mock_interpretation = Mock()
            mock_interpretation.user_feedback = Mock(
                action="accept",
                accepted_topics=None,  # Empty response from LLM
                rejected_topics=[],
                modification_request="",
            )
            mock_llm.invoke.return_value = mock_interpretation
            mock_get_llm.return_value.with_structured_output.return_value = mock_llm

            result = process_feedback(state)

            # Should fallback to suggested_topics
            expected_topics = [
                {"topic": "Original1", "weight": 0.5},
                {"topic": "Original2", "weight": 0.5},
            ]
            assert result["confirmed_topics"] == expected_topics

    def test_handles_unknown_action_gracefully(self):
        """Test error handling for invalid LLM action response"""
        state = {
            "suggested_topics": [{"topic": "Topic1", "weight": 1.0}],
            "user_input": "Confusing input",
        }

        with patch("Agent.TopicSelection.nodes.get_llm") as mock_get_llm:
            mock_llm = Mock()
            mock_interpretation = Mock()
            mock_interpretation.user_feedback = Mock(
                action="unknown_action",  # Invalid action
                accepted_topics=[],
                rejected_topics=[],
                modification_request="",
            )
            mock_llm.invoke.return_value = mock_interpretation
            mock_get_llm.return_value.with_structured_output.return_value = mock_llm

            result = process_feedback(state)

            # Should route back to request_feedback for unknown actions
            assert result["next_node"] == "request_feedback"
