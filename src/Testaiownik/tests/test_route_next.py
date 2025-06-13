# src/Testaiownik/tests/test_route_next.py
from Agent.TopicSelection.nodes import route_next


class TestRouteNext:
    """Test routing logic - pure function testing"""

    def test_route_next_routing_logic(self):
        """Test your exact routing implementation"""
        # Your code: next_node = state.get("next_node", "END")
        assert route_next({"next_node": "request_feedback"}) == "request_feedback"
        assert route_next({"next_node": "process_feedback"}) == "process_feedback"
        assert route_next({"next_node": "analyze_documents"}) == "analyze_documents"

        # Your code maps "END" to "__end__"
        assert route_next({"next_node": "END"}) == "__end__"

        # Your code defaults to "END" then maps to "__end__"
        assert route_next({}) == "__end__"
        assert route_next({"other_key": "value"}) == "__end__"

    def test_route_next_end_condition(self):
        """Test your exact END condition logic"""
        # Your code: return next_node if next_node != "END" else "__end__"
        result = route_next({"next_node": "END"})
        assert result == "__end__"
