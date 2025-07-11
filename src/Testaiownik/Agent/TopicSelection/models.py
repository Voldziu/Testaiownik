# src/testaiownik/agent/models.py
from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from Agent.Shared import WeightedTopic


class UserFeedback(BaseModel):
    action: Literal["accept", "modify"] = Field(
        description="User's chosen action for the topics"
    )
    accepted_topics: List[str] = Field(description="Topics user wants to keep")
    want_to_add_topics: List[str] = Field(description="Topics user wants to add")
    rejected_topics: List[str] = Field(description="Topics user wants to remove")
    modification_request: str = Field(description="User's request for changes")


class FeedbackInterpretation(BaseModel):
    user_feedback: UserFeedback = Field(
        description="Structured interpretation of user input"
    )
    reasoning: str = Field(description="LLM's reasoning for the interpretation")


class BatchAnalysis(BaseModel):
    current_topics: List[WeightedTopic] = Field(
        description="Topics found in current batch with weights"
    )
    accumulated_summary: str = Field(
        description="Summary of all content processed so far"
    )
    batch_summary: str = Field(description="Summary of current batch only")


class TopicConsolidation(BaseModel):
    consolidated_topics: List[WeightedTopic] = Field(
        description="Final consolidated topic list with weights"
    )
    reasoning: str = Field(description="How topics were consolidated")
    desired_topic_count: Optional[int] = Field("Number of topics")

