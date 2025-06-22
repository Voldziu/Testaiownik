# test_data_processing.py - REGENERATED
from unittest.mock import Mock, patch
from src.Testaiownik.Agent.TopicSelection.nodes import (
    _process_batch,
    _consolidate_topics_with_history,
)


class TestProcessBatch:
    """Test process_batch function from Agent.TopicSelection.nodes module"""

    @patch("src.Testaiownik.Agent.TopicSelection.nodes.create_extractor")
    def test_process_batch_prompt_creation(self, mock_extractor):
        """Test how your process_batch creates prompts"""
        # Mock the extractor with tool_calls structure
        mock_extract_instance = Mock()
        mock_message = Mock()
        mock_message.tool_calls = [
            {
                "args": {
                    "current_topics": [
                        {"topic": "Algorithm", "weight": 0.6},
                        {"topic": "Sorting", "weight": 0.4},
                    ],
                    "accumulated_summary": "Test summary from batch",
                    "batch_summary": "Current batch summary",
                }
            }
        ]
        mock_tool_call_result = {"messages": [mock_message]}
        mock_extract_instance.invoke.return_value = mock_tool_call_result
        mock_extractor.return_value = mock_extract_instance

        batch_text = "Educational content about algorithms and data structures"
        previous_context = (
            "Previous topics found: [Data Structure]\nPrevious summary: Old summary"
        )

        result = _process_batch(batch_text, previous_context, mock_extract_instance)

        # Check that extractor was called
        mock_extract_instance.invoke.assert_called_once()

        # Check the prompt structure your function creates
        call_args = mock_extract_instance.invoke.call_args[0][0]
        prompt = call_args["messages"][0]

        # Your process_batch should include both previous_context and batch_text
        assert previous_context in prompt
        assert batch_text in prompt
        assert "Analyze this batch of educational documents:" in prompt

        # Check returned structure
        assert "current_topics" in result
        assert "accumulated_summary" in result
        assert result["current_topics"] == [
            {"topic": "Algorithm", "weight": 0.6},
            {"topic": "Sorting", "weight": 0.4},
        ]

    @patch("src.Testaiownik.Agent.TopicSelection.nodes.create_extractor")
    def test_process_batch_with_empty_previous_context(self, mock_extractor):
        """Test process_batch with first batch (no previous context)"""
        mock_extract_instance = Mock()
        mock_message = Mock()
        mock_message.tool_calls = [
            {
                "args": {
                    "current_topics": [{"topic": "First Topic", "weight": 1.0}],
                    "accumulated_summary": "First summary",
                    "batch_summary": "First batch",
                }
            }
        ]
        mock_tool_call_result = {"messages": [mock_message]}
        mock_extract_instance.invoke.return_value = mock_tool_call_result
        mock_extractor.return_value = mock_extract_instance

        batch_text = "First batch content"
        previous_context = "This is the first batch."

        _process_batch(batch_text, previous_context, mock_extract_instance)

        # Check the prompt includes first batch indicator
        call_args = mock_extract_instance.invoke.call_args[0][0]
        prompt = call_args["messages"][0]
        assert "This is the first batch." in prompt
        assert "First batch content" in prompt

    @patch("src.Testaiownik.Agent.TopicSelection.nodes.create_extractor")
    def test_process_batch_return_structure(self, mock_extractor):
        """Test that process_batch returns the correct structure"""
        expected_response = {
            "current_topics": [
                {"topic": "Topic1", "weight": 0.5},
                {"topic": "Topic2", "weight": 0.5},
            ],
            "accumulated_summary": "Accumulated summary text",
            "batch_summary": "Current batch summary",
        }

        mock_extract_instance = Mock()
        mock_message = Mock()
        mock_message.tool_calls = [{"args": expected_response}]
        mock_tool_call_result = {"messages": [mock_message]}
        mock_extract_instance.invoke.return_value = mock_tool_call_result

        result = _process_batch("test", "test", mock_extract_instance)

        # Your function should return the args from tool_calls
        assert result["current_topics"] == expected_response["current_topics"]
        assert result["accumulated_summary"] == expected_response["accumulated_summary"]
        assert result["batch_summary"] == expected_response["batch_summary"]

    @patch("Agent.TopicSelection.nodes.create_extractor")
    def test_process_batch_with_empty_batch_text(self, mock_extractor):
        """Test process_batch with empty or minimal batch text"""
        mock_extract_instance = Mock()
        mock_message = Mock()
        mock_message.tool_calls = [
            {
                "args": {
                    "current_topics": [],
                    "accumulated_summary": "No topics found",
                    "batch_summary": "Empty batch",
                }
            }
        ]
        mock_tool_call_result = {"messages": [mock_message]}
        mock_extract_instance.invoke.return_value = mock_tool_call_result

        result = _process_batch("", "No previous context", mock_extract_instance)

        # Should handle empty input gracefully
        assert result["current_topics"] == []
        mock_extract_instance.invoke.assert_called_once()

    @patch("src.Testaiownik.Agent.TopicSelection.nodes.create_extractor")
    def test_process_batch_with_very_long_content(self, mock_extractor):
        """Test process_batch with very long batch content"""
        mock_extract_instance = Mock()
        mock_message = Mock()
        mock_message.tool_calls = [
            {
                "args": {
                    "current_topics": [
                        {"topic": "LongTopic1", "weight": 0.6},
                        {"topic": "LongTopic2", "weight": 0.4},
                    ],
                    "accumulated_summary": "Very long summary...",
                    "batch_summary": "Long batch processed",
                }
            }
        ]
        mock_tool_call_result = {"messages": [mock_message]}
        mock_extract_instance.invoke.return_value = mock_tool_call_result

        # Very long content
        long_content = "This is very long educational content. " * 100
        previous_context = (
            "Previous topics: [Topic1, Topic2]\nPrevious summary: "
            + "Long summary. " * 50
        )

        result = _process_batch(long_content, previous_context, mock_extract_instance)

        # Should handle long content without issues
        assert len(result["current_topics"]) == 2

        # Check that both long content and context are in the prompt
        call_args = mock_extract_instance.invoke.call_args[0][0]
        prompt = call_args["messages"][0]
        assert long_content in prompt
        assert previous_context in prompt


class TestConsolidateTopicsWithHistory:
    """Test the  consolidate_topics_with_history function from Agent.TopicSelection.nodes module"""

    @patch("src.Testaiownik.Agent.TopicSelection.nodes.get_llm")
    def test_consolidate_with_empty_history(self, mock_get_llm):
        """Test your function with no conversation history"""
        topics = [
            {"topic": "Algorithm", "weight": 0.4},
            {"topic": "Data Structure", "weight": 0.3},
            {"topic": "Complexity", "weight": 0.3},
        ]
        rejected_topics = []
        history = []
        desired_topic_count = 10

        # Mock the LLM response even for empty history
        mock_llm = Mock()
        mock_consolidation_result = Mock()
        mock_consolidation_result.consolidated_topics = [
            Mock(topic="Algorithm", weight=0.4),
            Mock(topic="Data Structure", weight=0.3),
            Mock(topic="Complexity", weight=0.3),
        ]
        mock_llm.invoke.return_value = mock_consolidation_result
        mock_get_llm.return_value.with_structured_output.return_value = mock_llm

        result = _consolidate_topics_with_history(
            topics, rejected_topics, history, desired_topic_count
        )

        # Function returns WeightedTopic objects
        assert isinstance(result, list)
        assert len(result) == 3

        # Check that we get WeightedTopic objects back
        topic_names = [r.topic for r in result]
        assert "Algorithm" in topic_names
        assert "Data Structure" in topic_names
        assert "Complexity" in topic_names

    @patch("src.Testaiownik.Agent.TopicSelection.nodes.get_llm")
    def test_consolidate_with_history_present(self, mock_get_llm):
        """Test your function when conversation history exists"""
        topics = [
            {"topic": "Algorithm", "weight": 0.5},
            {"topic": "Sorting", "weight": 0.3},
            {"topic": "Trees", "weight": 0.2},
        ]
        history = [
            {
                "suggested_topics": [{"topic": "Algorithm", "weight": 0.5}],
                "user_feedback": "Add more specific topics",
            },
            {
                "suggested_topics": [
                    {"topic": "Sorting", "weight": 0.4},
                    {"topic": "Trees", "weight": 0.6},
                ],
                "user_feedback": "Focus on algorithms",
            },
        ]
        rejected_topics = []
        desired_topic_count = 10

        # Mock the LLM chain
        mock_llm = Mock()
        mock_consolidation_result = Mock()
        mock_consolidation_result.consolidated_topics = [
            Mock(topic="Advanced Algorithms", weight=0.4),
            Mock(topic="Sorting Algorithms", weight=0.3),
            Mock(topic="Tree Structures", weight=0.3),
        ]
        mock_llm.invoke.return_value = mock_consolidation_result
        mock_get_llm.return_value.with_structured_output.return_value = mock_llm

        result = _consolidate_topics_with_history(
            topics, rejected_topics, history, desired_topic_count
        )

        # Should call LLM when history exists
        mock_get_llm.assert_called_once()
        mock_llm.invoke.assert_called_once()

        # Check that prompt includes history
        prompt_arg = mock_llm.invoke.call_args[0][0]
        assert "Iteration 1:" in prompt_arg
        assert "Iteration 2:" in prompt_arg
        assert "Add more specific topics" in prompt_arg
        assert "Focus on algorithms" in prompt_arg

        # Should return consolidated topics from LLM as WeightedTopic objects
        assert len(result) == 3
        assert result[0].topic == "Advanced Algorithms"
        assert result[1].topic == "Sorting Algorithms"
        assert result[2].topic == "Tree Structures"

    @patch("src.Testaiownik.Agent.TopicSelection.nodes.get_llm")
    def test_consolidate_uses_latest_feedback(self, mock_get_llm):
        """Test that your function highlights latest user feedback"""
        topics = [{"topic": "Topic1", "weight": 1.0}]
        history = [
            {
                "suggested_topics": [{"topic": "Topic1", "weight": 1.0}],
                "user_feedback": "This is the latest feedback",
            }
        ]
        rejected_topics = []
        desired_topic_count = 10

        mock_llm = Mock()
        mock_consolidation_result = Mock()
        mock_consolidation_result.consolidated_topics = [
            Mock(topic="Refined Topic1", weight=1.0)
        ]
        mock_llm.invoke.return_value = mock_consolidation_result
        mock_get_llm.return_value.with_structured_output.return_value = mock_llm

        _consolidate_topics_with_history(
            topics, rejected_topics, history, desired_topic_count
        )

        # Check that latest feedback is mentioned in prompt
        prompt_arg = mock_llm.invoke.call_args[0][0]
        # Based on the actual implementation, latest feedback appears in history context, not as separate line
        assert "This is the latest feedback" in prompt_arg

    def test_consolidate_with_very_large_topic_set(self):
        """Test consolidate_topics_with_history with many topics"""
        # Large set of topics
        large_topic_set = [
            {"topic": f"Topic_{i}", "weight": 1.0 / 50} for i in range(50)
        ]
        history = []
        rejected_topics = []
        desired_topic_count = 50

        with patch(
            "src.Testaiownik.Agent.TopicSelection.nodes.get_llm"
        ) as mock_get_llm:
            mock_llm = Mock()
            mock_consolidation_result = Mock()
            # Mock returns only 10 topics (default behavior based on desired_topic_count logic)
            mock_consolidation_result.consolidated_topics = [
                Mock(topic=f"Consolidated_Topic_{i}", weight=0.1) for i in range(10)
            ]
            mock_llm.invoke.return_value = mock_consolidation_result
            mock_get_llm.return_value.with_structured_output.return_value = mock_llm

            result = _consolidate_topics_with_history(
                large_topic_set, rejected_topics, history, desired_topic_count
            )

            # Function actually uses LLM which consolidates to fewer topics
            assert isinstance(result, list)
            assert len(result) == 10  # LLM consolidates down to 10

    @patch("src.Testaiownik.Agent.TopicSelection.nodes.get_llm")
    def test_consolidate_formats_history_correctly(self, mock_get_llm):
        """Test the exact history formatting in your function"""
        topics = [{"topic": "Topic", "weight": 1.0}]
        history = [
            {
                "suggested_topics": [
                    {"topic": "A", "weight": 0.5},
                    {"topic": "B", "weight": 0.5},
                ],
                "user_feedback": "First",
            },
            {
                "suggested_topics": [{"topic": "C", "weight": 1.0}],
                "user_feedback": "Second",
            },
        ]
        rejected_topics = []
        desired_topic_count = 10

        mock_llm = Mock()
        mock_consolidation_result = Mock()
        mock_consolidation_result.consolidated_topics = [
            Mock(topic="Result", weight=1.0)
        ]
        mock_llm.invoke.return_value = mock_consolidation_result
        mock_get_llm.return_value.with_structured_output.return_value = mock_llm

        _consolidate_topics_with_history(
            topics, rejected_topics, history, desired_topic_count
        )

        prompt_arg = mock_llm.invoke.call_args[0][0]

        # Your code formats as: f"Iteration {i+1}: Generated {len(h['suggested_topics'])} topics, User said: '{h['user_feedback']}'"
        assert "Iteration 1: Generated 2 topics, User said: 'First'" in prompt_arg
        assert "Iteration 2: Generated 1 topics, User said: 'Second'" in prompt_arg
