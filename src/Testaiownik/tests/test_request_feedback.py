# test_request_feedback.py - REGENERATED
from Agent.TopicSelection.nodes import request_feedback


class TestRequestFeedback:
    """Test edge cases for  helper functions"""

    def test_request_feedback_message_format(self):
        """Test the exact format your request_feedback produces"""
        state = {
            "suggested_topics": [
                {"topic": "Algorithm", "weight": 0.6},
                {"topic": "Data Structure", "weight": 0.4},
            ]
        }
        result = request_feedback(state)

        # Test format from your code
        expected_in_message = [
            "Found topics:",
            "0: {'topic': 'Algorithm', 'weight': 0.6}",
            "1: {'topic': 'Data Structure', 'weight': 0.4}",
            "Provide feedback on given topics please.",
        ]

        feedback = result["feedback_request"]
        for expected_part in expected_in_message:
            assert expected_part in feedback

        assert result["next_node"] == "process_feedback"

    def test_request_feedback_empty_topics_behavior(self):
        """Test how code handles empty suggested_topics"""
        state = {"suggested_topics": []}
        result = request_feedback(state)

        # Your code should still create a feedback_request
        assert "feedback_request" in result
        assert "Found topics:" in result["feedback_request"]
        assert result["next_node"] == "process_feedback"

    def test_request_feedback_state_preservation(self):
        """Test that function preserves state using spread operator"""
        original_state = {
            "suggested_topics": [{"topic": "Topic1", "weight": 1.0}],
            "documents": ["doc1"],
            "user_input": "test_input",
        }

        result = request_feedback(original_state)

        # Your code uses {**state, ...} so original fields should be preserved
        assert result["suggested_topics"] == [{"topic": "Topic1", "weight": 1.0}]
        assert result["documents"] == ["doc1"]
        assert result["user_input"] == "test_input"

    def test_request_feedback_with_consolidated_topics(self):
        """Test request_feedback works correctly with output from consolidate"""
        # Topics that might come from consolidate_topics_with_history
        consolidated_topics = [
            {
                "topic": "Advanced Sorting Algorithms (QuickSort, MergeSort, HeapSort)",
                "weight": 0.3,
            },
            {
                "topic": "Tree Data Structures (BST, AVL, Red-Black Trees)",
                "weight": 0.25,
            },
            {
                "topic": "Graph Algorithms (DFS, BFS, Dijkstra's Algorithm)",
                "weight": 0.25,
            },
            {"topic": "Dynamic Programming Techniques", "weight": 0.2},
        ]

        state = {"suggested_topics": consolidated_topics}

        result = request_feedback(state)

        # Should format all topics correctly
        feedback = result["feedback_request"]
        assert "Found topics:" in feedback
        assert "Provide feedback on given topics please." in feedback
        # Check that all topics are present
        for i, topic_data in enumerate(consolidated_topics):
            assert f"{i}: {topic_data}" in feedback
