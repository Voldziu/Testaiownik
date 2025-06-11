from typing import List, Dict, Optional, TypedDict, Any


class AgentState(TypedDict):
    documents: List[str]
    suggested_topics: List[str]
    confirmed_topics: List[str]
    subtopics: Dict[str, List[str]]
    user_input: Optional[str]
    feedback_request: Optional[str]
    conversation_history: List[Dict[str, Any]]
    next_node: str
    messages: List[str]
