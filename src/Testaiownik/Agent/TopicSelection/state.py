from typing import List, Dict, Optional, TypedDict, Any
from .models import WeightedTopic


class AgentState(TypedDict):
    suggested_topics: List[WeightedTopic]
    rejected_topics: List[str]
    confirmed_topics: List[WeightedTopic]
    subtopics: Dict[str, List[str]]
    user_input: Optional[str]
    feedback_request: Optional[str]
    conversation_history: List[Dict[str, Any]]
    next_node: str
    messages: List[str]
    desired_topic_count: int  
