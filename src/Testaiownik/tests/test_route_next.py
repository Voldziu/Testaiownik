# test_route_next.py - REGENERATED
from Agent.TopicSelection.nodes import route_next


class TestRouteNext:
    """Test routing logic - pure function testing"""

    def test_route_next_routing_logic(self):
        """Test exact routing implementation"""

        assert route_next({"next_node": "request_feedback"}) == "request_feedback"
        assert route_next({"next_node": "process_feedback"}) == "process_feedback"
        assert route_next({"next_node": "analyze_documents"}) == "analyze_documents"

        assert route_next({"next_node": "END"}) == "__end__"

        assert route_next({}) == "__end__"
        assert route_next({"other_key": "value"}) == "__end__"

    def test_route_next_end_condition(self):
        """Test exact END condition logic"""
        result = route_next({"next_node": "END"})
        assert result == "__end__"
