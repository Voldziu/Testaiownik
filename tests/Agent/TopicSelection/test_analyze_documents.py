from unittest.mock import Mock, patch
from src.Testaiownik.Agent.TopicSelection.nodes import analyze_documents


class TestAnalyzeDocumentsWithHelpers:
    """Test how your analyze_documents uses the helper functions"""

    @patch(
        "src.Testaiownik.Agent.TopicSelection.nodes._consolidate_topics_with_history"
    )
    @patch("src.Testaiownik.Agent.TopicSelection.nodes._process_batch")
    @patch("src.Testaiownik.Agent.TopicSelection.nodes.get_llm")
    @patch("src.Testaiownik.Agent.TopicSelection.nodes.create_extractor")
    def test_analyze_calls_process_batch_correctly(
        self, mock_extractor, mock_get_llm, mock_process_batch, mock_consolidate
    ):
        """Test that analyze_documents calls process_batch with correct arguments"""
        mock_get_llm.return_value = Mock()
        mock_extractor.return_value = Mock()

        mock_process_batch.side_effect = [
            {
                "current_topics": [{"topic": "Topic1", "weight": 1.0}],
                "accumulated_summary": "Summary1",
            },
            {
                "current_topics": [{"topic": "Topic2", "weight": 1.0}],
                "accumulated_summary": "Summary2",
            },
        ]
        mock_consolidate.return_value = [
            {"topic": "Final1", "weight": 0.5},
            {"topic": "Final2", "weight": 0.5},
        ]

        mock_retriever = Mock()
        chunks = [
            {"text": "chunk1", "source": "test"},
            {"text": "chunk2", "source": "test"},
            {"text": "chunk3", "source": "test"},
            {"text": "chunk4", "source": "test"},
        ]
        mock_retriever.get_all_chunks.return_value = chunks
        mock_retriever.get_chunk_count.return_value = 4

        state = {"conversation_history": []}

        analyze_documents(state, mock_retriever, batch_size=2)

        assert mock_process_batch.call_count == 2

        first_call = mock_process_batch.call_args_list[0]
        batch_text_1 = first_call[0][0]  
        previous_context_1 = first_call[0][1]  

        assert "chunk1\n---\nchunk2" == batch_text_1  
        assert "This is the first batch." == previous_context_1 

        second_call = mock_process_batch.call_args_list[1]
        batch_text_2 = second_call[0][0]
        previous_context_2 = second_call[0][1]

        assert "chunk3\n---\nchunk4" == batch_text_2


    @patch(
        "src.Testaiownik.Agent.TopicSelection.nodes._consolidate_topics_with_history"
    )
    @patch("src.Testaiownik.Agent.TopicSelection.nodes._process_batch")
    @patch("src.Testaiownik.Agent.TopicSelection.nodes.get_llm")
    @patch("src.Testaiownik.Agent.TopicSelection.nodes.create_extractor")
    def test_analyze_accumulates_topics_correctly(
        self, mock_extractor, mock_get_llm, mock_process_batch, mock_consolidate
    ):
        """Test that analyze_documents accumulates topics across batches"""
        mock_get_llm.return_value = Mock()
        mock_extractor.return_value = Mock()

        mock_process_batch.side_effect = [
            {
                "current_topics": [
                    {"topic": "Algorithm", "weight": 0.6},
                    {"topic": "Sorting", "weight": 0.4},
                ],
                "accumulated_summary": "Summary1",
            },
            {
                "current_topics": [
                    {"topic": "Algorithm", "weight": 0.5},
                    {"topic": "Trees", "weight": 0.5},
                ],
                "accumulated_summary": "Summary2",
            }, 
        ]
        mock_consolidate.return_value = [{"topic": "Final Topics", "weight": 1.0}]

        mock_retriever = Mock()
        mock_retriever.get_all_chunks.return_value = [
            {"text": "chunk1", "source": "test"},
            {"text": "chunk2", "source": "test"},
        ]
        mock_retriever.get_chunk_count.return_value = 2

        state = {"conversation_history": []}

        analyze_documents(state, mock_retriever, batch_size=1)

        mock_consolidate.assert_called_once()
        topics_passed = mock_consolidate.call_args[0][0] 

        assert len(topics_passed) == 4  
        topic_names = [t["topic"] for t in topics_passed]
        assert topic_names.count("Algorithm") == 2  
        assert "Sorting" in topic_names
        assert "Trees" in topic_names

    @patch(
        "src.Testaiownik.Agent.TopicSelection.nodes._consolidate_topics_with_history"
    )
    @patch("src.Testaiownik.Agent.TopicSelection.nodes._process_batch")
    @patch("src.Testaiownik.Agent.TopicSelection.nodes.get_llm")
    @patch("src.Testaiownik.Agent.TopicSelection.nodes.create_extractor")
    def test_analyze_passes_history_to_consolidate(
        self, mock_extractor, mock_get_llm, mock_process_batch, mock_consolidate
    ):
        """Test that analyze_documents passes conversation history to consolidate"""
        mock_get_llm.return_value = Mock()
        mock_extractor.return_value = Mock()

        mock_process_batch.return_value = {
            "current_topics": [{"topic": "Topic", "weight": 1.0}],
            "accumulated_summary": "Summary",
        }
        mock_consolidate.return_value = [{"topic": "Consolidated Topic", "weight": 1.0}]

        mock_retriever = Mock()
        mock_retriever.get_all_chunks.return_value = [
            {"text": "chunk", "source": "test"}
        ]
        mock_retriever.get_chunk_count.return_value = 1

        test_history = [
            {
                "suggested_topics": [{"topic": "Old", "weight": 1.0}],
                "user_feedback": "Old feedback",
            }
        ]
        state = {"conversation_history": test_history}

        analyze_documents(state, mock_retriever)

        mock_consolidate.assert_called_once()
        history_passed = mock_consolidate.call_args[0][2]  
        assert history_passed == test_history

    @patch("src.Testaiownik.Agent.TopicSelection.nodes.get_llm")
    @patch("src.Testaiownik.Agent.TopicSelection.nodes.create_extractor")
    @patch("src.Testaiownik.Agent.TopicSelection.nodes.MockRetriever")
    def test_mock_retriever_fallback(
        self, mock_retriever_class, mock_extractor, mock_get_llm
    ):
        """Test your MockRetriever fallback logic"""
        mock_llm = Mock()
        mock_get_llm.return_value = mock_llm

        mock_extract_instance = Mock()
        mock_message = Mock()
        mock_message.tool_calls = [
            {
                "args": {
                    "current_topics": [{"topic": "Test Topic", "weight": 1.0}],
                    "accumulated_summary": "Test summary",
                    "batch_summary": "Test batch",
                }
            }
        ]
        mock_tool_call_result = {"messages": [mock_message]}
        mock_extract_instance.invoke.return_value = mock_tool_call_result
        mock_extractor.return_value = mock_extract_instance

        mock_retriever_instance = Mock()
        mock_retriever_instance.get_chunk_count.return_value = 2
        mock_retriever_instance.get_all_chunks.return_value = [
            {"text": "chunk1", "source": "mock"},
            {"text": "chunk2", "source": "mock"},
        ]
        mock_retriever_class.return_value = mock_retriever_instance

        state = {"conversation_history": []}

        result = analyze_documents(state, retriever=None)

        mock_retriever_class.assert_called_once()
        assert result["next_node"] == "request_feedback"

    @patch("src.Testaiownik.Agent.TopicSelection.nodes.get_llm")
    @patch("src.Testaiownik.Agent.TopicSelection.nodes.create_extractor")
    def test_user_input_clearing(self, mock_extractor, mock_get_llm):
        """Test that your code clears user_input"""
        mock_llm = Mock()
        mock_get_llm.return_value = mock_llm

        mock_extract_instance = Mock()
        mock_message = Mock()
        mock_message.tool_calls = [
            {
                "args": {
                    "current_topics": [],
                    "accumulated_summary": "summary",
                    "batch_summary": "batch summary",
                }
            }
        ]
        mock_tool_call_result = {"messages": [mock_message]}
        mock_extract_instance.invoke.return_value = mock_tool_call_result
        mock_extractor.return_value = mock_extract_instance

        mock_retriever = Mock()
        mock_retriever.get_chunk_count.return_value = 1
        mock_retriever.get_all_chunks.return_value = [
            {"text": "chunk", "source": "test"}
        ]

        state = {"user_input": "Should be cleared", "conversation_history": []}

        result = analyze_documents(state, mock_retriever)

        assert result["user_input"] is None

    @patch("src.Testaiownik.Agent.TopicSelection.nodes.get_llm")
    @patch("src.Testaiownik.Agent.TopicSelection.nodes.create_extractor")
    def test_documents_storage(self, mock_extractor, mock_get_llm):
        """Test that your code stores chunks as documents"""
        mock_llm = Mock()
        mock_get_llm.return_value = mock_llm

        mock_extract_instance = Mock()
        mock_message = Mock()
        mock_message.tool_calls = [
            {
                "args": {
                    "current_topics": [],
                    "accumulated_summary": "summary",
                    "batch_summary": "batch summary",
                }
            }
        ]
        mock_tool_call_result = {"messages": [mock_message]}
        mock_extract_instance.invoke.return_value = mock_tool_call_result
        mock_extractor.return_value = mock_extract_instance

        test_chunks = [
            {"text": "chunk1", "source": "test"},
            {"text": "chunk2", "source": "test"},
            {"text": "chunk3", "source": "test"},
        ]
        mock_retriever = Mock()
        mock_retriever.get_chunk_count.return_value = len(test_chunks)
        mock_retriever.get_all_chunks.return_value = test_chunks

        state = {"conversation_history": []}

        result = analyze_documents(state, mock_retriever)

        mock_retriever.get_all_chunks.assert_called_once()

    @patch("src.Testaiownik.Agent.TopicSelection.nodes.get_llm")
    @patch("src.Testaiownik.Agent.TopicSelection.nodes.create_extractor")
    def test_batch_size_usage(self, mock_extractor, mock_get_llm):
        """Test that your code uses batch_size parameter"""
        mock_llm = Mock()
        mock_get_llm.return_value = mock_llm

        mock_extract_instance = Mock()
        mock_message = Mock()
        mock_message.tool_calls = [
            {
                "args": {
                    "current_topics": [{"topic": "Topic", "weight": 1.0}],
                    "accumulated_summary": "summary",
                    "batch_summary": "batch summary",
                }
            }
        ]
        mock_tool_call_result = {"messages": [mock_message]}
        mock_extract_instance.invoke.return_value = mock_tool_call_result
        mock_extractor.return_value = mock_extract_instance

        mock_retriever = Mock()
        chunks = [
            {"text": "chunk1", "source": "test"},
            {"text": "chunk2", "source": "test"},
            {"text": "chunk3", "source": "test"},
            {"text": "chunk4", "source": "test"},
        ]
        mock_retriever.get_all_chunks.return_value = chunks
        mock_retriever.get_chunk_count.return_value = 4

        state = {"conversation_history": []}

        analyze_documents(state, mock_retriever, batch_size=2)

        assert mock_extract_instance.invoke.call_count == 2

    @patch("src.Testaiownik.Agent.TopicSelection.nodes.get_llm")
    @patch("src.Testaiownik.Agent.TopicSelection.nodes.create_extractor")
    def test_batch_text_joining(self, mock_extractor, mock_get_llm):
        """Test your batch text joining logic"""
        mock_llm = Mock()
        mock_get_llm.return_value = mock_llm

        mock_extract_instance = Mock()
        mock_message = Mock()
        mock_message.tool_calls = [
            {
                "args": {
                    "current_topics": [],
                    "accumulated_summary": "summary",
                    "batch_summary": "batch summary",
                }
            }
        ]
        mock_tool_call_result = {"messages": [mock_message]}
        mock_extract_instance.invoke.return_value = mock_tool_call_result
        mock_extractor.return_value = mock_extract_instance

        chunks = [
            {"text": "First chunk", "source": "test"},
            {"text": "Second chunk", "source": "test"},
        ]
        mock_retriever = Mock()
        mock_retriever.get_all_chunks.return_value = chunks
        mock_retriever.get_chunk_count.return_value = 2

        state = {"conversation_history": []}

        analyze_documents(state, mock_retriever, batch_size=2)

        call_args = mock_extract_instance.invoke.call_args[0][0]
        prompt = call_args["messages"][0]

        expected_joined = "First chunk\n---\nSecond chunk"
        assert expected_joined in prompt
