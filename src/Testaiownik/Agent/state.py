from typing import List, Dict, Optional, TypedDict


class AgentState(TypedDict):
    documents: List[str]
    suggested_topics: List[str]
    confirmed_topics: List[str]
    subtopics: Dict[str, List[str]]
    user_input: Optional[str]
    feedback_request: Optional[str]
    next_node: str
    messages: List[str]
