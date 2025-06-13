# Import the helper functions
from unittest.mock import Mock, patch
from Agent.nodes import (
    _process_batch,
    _consolidate_topics_with_history,
)


class TestProcessBatch:
    """Test the REAL process_batch function from your code"""

    @patch("Agent.nodes.create_extractor")
    def test_process_batch_prompt_creation(self, mock_extractor):
        """Test how your process_batch creates prompts"""
        # Mock the extractor
        mock_extract_instance = Mock()
        mock_response = Mock()
        mock_response.current_topics = ["Algorithm", "Sorting"]
        mock_response.accumulated_summary = "Test summary from batch"
        mock_response.batch_summary = "Current batch summary"
        mock_extract_instance.invoke.return_value = {"responses": [mock_response]}

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
        assert result["current_topics"] == ["Algorithm", "Sorting"]

    @patch("Agent.nodes.create_extractor")
    def test_process_batch_with_empty_previous_context(self, mock_extractor):
        """Test process_batch with first batch (no previous context)"""
        mock_extract_instance = Mock()
        mock_response = Mock()
        mock_response.current_topics = ["First Topic"]
        mock_response.accumulated_summary = "First summary"
        mock_response.batch_summary = "First batch"
        mock_extract_instance.invoke.return_value = {"responses": [mock_response]}
        mock_extractor.return_value = mock_extract_instance

        batch_text = "First batch content"
        previous_context = "This is the first batch."

        _process_batch(batch_text, previous_context, mock_extract_instance)

        # Check the prompt includes first batch indicator
        call_args = mock_extract_instance.invoke.call_args[0][0]
        prompt = call_args["messages"][0]
        assert "This is the first batch." in prompt
        assert "First batch content" in prompt

    @patch("Agent.nodes.create_extractor")
    def test_process_batch_return_structure(self, mock_extractor):
        """Test that process_batch returns the correct structure"""
        expected_response = {
            "current_topics": ["Topic1", "Topic2"],
            "accumulated_summary": "Accumulated summary text",
            "batch_summary": "Current batch summary",
        }

        mock_extract_instance = Mock()
        mock_response = Mock()
        mock_response.current_topics = ["Topic1", "Topic2"]
        mock_response.accumulated_summary = "Accumulated summary text"
        mock_response.batch_summary = "Current batch summary"
        mock_extract_instance.invoke.return_value = {"responses": [mock_response]}

        result = _process_batch("test", "test", mock_extract_instance)

        # Your function should return the __dict__ from the response
        assert result["current_topics"] == expected_response["current_topics"]
        assert result["accumulated_summary"] == expected_response["accumulated_summary"]
        assert result["batch_summary"] == expected_response["batch_summary"]

    @patch("Agent.nodes.create_extractor")
    def test_process_batch_with_empty_batch_text(self, mock_extractor):
        """Test process_batch with empty or minimal batch text"""
        mock_extract_instance = Mock()
        mock_response = Mock()
        mock_response.current_topics = []
        mock_response.accumulated_summary = "No topics found"
        mock_response.batch_summary = "Empty batch"
        mock_extract_instance.invoke.return_value = {"responses": [mock_response]}

        result = _process_batch("", "No previous context", mock_extract_instance)

        # Should handle empty input gracefully
        assert result["current_topics"] == []
        mock_extract_instance.invoke.assert_called_once()

    @patch("Agent.nodes.create_extractor")
    def test_process_batch_with_very_long_content(self, mock_extractor):
        """Test process_batch with very long batch content"""
        mock_extract_instance = Mock()
        mock_response = Mock()
        mock_response.current_topics = ["LongTopic1", "LongTopic2"]
        mock_response.accumulated_summary = "Very long summary..."
        mock_response.batch_summary = "Long batch processed"
        mock_extract_instance.invoke.return_value = {"responses": [mock_response]}

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
    """Test the REAL consolidate_topics_with_history function from your code"""

    def test_consolidate_with_empty_history(self):
        """Test your function with no conversation history"""
        topics = {"Algorithm", "Data Structure", "Complexity"}
        history = []

        result = _consolidate_topics_with_history(topics, history)

        # Your code: if not history: return list(all_topics)
        assert isinstance(result, list)
        assert set(result) == topics
        assert len(result) == 3

    @patch("Agent.nodes.get_llm")
    def test_consolidate_with_history_present(self, mock_get_llm):
        """Test your function when conversation history exists"""
        topics = {"Algorithm", "Sorting", "Trees"}
        history = [
            {
                "suggested_topics": ["Algorithm"],
                "user_feedback": "Add more specific topics",
            },
            {
                "suggested_topics": ["Sorting", "Trees"],
                "user_feedback": "Focus on algorithms",
            },
        ]

        # Mock the LLM chain
        mock_llm = Mock()
        mock_consolidation_result = Mock()
        mock_consolidation_result.consolidated_topics = [
            "Advanced Algorithms",
            "Sorting Algorithms",
            "Tree Structures",
        ]
        mock_llm.invoke.return_value = mock_consolidation_result
        mock_get_llm.return_value.with_structured_output.return_value = mock_llm

        result = _consolidate_topics_with_history(topics, history)

        # Should call LLM when history exists
        mock_get_llm.assert_called_once()
        mock_llm.invoke.assert_called_once()

        # Check that prompt includes history
        prompt_arg = mock_llm.invoke.call_args[0][0]
        assert "CONVERSATION HISTORY:" in prompt_arg
        assert "Iteration 1:" in prompt_arg
        assert "Iteration 2:" in prompt_arg
        assert "Add more specific topics" in prompt_arg
        assert "Focus on algorithms" in prompt_arg

        # Should return consolidated topics from LLM
        assert result == [
            "Advanced Algorithms",
            "Sorting Algorithms",
            "Tree Structures",
        ]

    @patch("Agent.nodes.get_llm")
    def test_consolidate_uses_latest_feedback(self, mock_get_llm):
        """Test that your function highlights latest user feedback"""
        topics = {"Topic1"}
        history = [
            {
                "suggested_topics": ["Topic1"],
                "user_feedback": "This is the latest feedback",
            }
        ]

        mock_llm = Mock()
        mock_consolidation_result = Mock()
        mock_consolidation_result.consolidated_topics = ["Refined Topic1"]
        mock_llm.invoke.return_value = mock_consolidation_result
        mock_get_llm.return_value.with_structured_output.return_value = mock_llm

        _consolidate_topics_with_history(topics, history)

        # Check that latest feedback is specially mentioned in prompt
        prompt_arg = mock_llm.invoke.call_args[0][0]
        assert 'Latest user feedback: "This is the latest feedback"' in prompt_arg

    @patch("Agent.nodes.get_llm")
    def test_consolidate_formats_history_correctly(self, mock_get_llm):
        """Test the exact history formatting in your function"""
        topics = {"Topic"}
        history = [
            {"suggested_topics": ["A", "B"], "user_feedback": "First"},
            {"suggested_topics": ["C"], "user_feedback": "Second"},
        ]

        mock_llm = Mock()
        mock_consolidation_result = Mock()
        mock_consolidation_result.consolidated_topics = ["Result"]
        mock_llm.invoke.return_value = mock_consolidation_result
        mock_get_llm.return_value.with_structured_output.return_value = mock_llm

        _consolidate_topics_with_history(topics, history)

        prompt_arg = mock_llm.invoke.call_args[0][0]

        # Your code formats as: f"Iteration {i+1}: Generated {len(h['suggested_topics'])} topics, User said: '{h['user_feedback']}'"
        assert "Iteration 1: Generated 2 topics, User said: 'First'" in prompt_arg
        assert "Iteration 2: Generated 1 topics, User said: 'Second'" in prompt_arg

    def test_consolidate_with_very_large_topic_set(self):
        """Test consolidate_topics_with_history with many topics"""
        # Large set of topics
        large_topic_set = {f"Topic_{i}" for i in range(50)}
        history = []

        result = _consolidate_topics_with_history(large_topic_set, history)

        # Should return all topics as list when no history
        assert isinstance(result, list)
        assert len(result) == 50
        assert set(result) == large_topic_set
