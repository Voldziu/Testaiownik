# src/testaiownik/agent/models.py
from pydantic import BaseModel, Field
from typing import List, Optional, Literal


class UserFeedback(BaseModel):
    action: Literal["accept", "modify"] = Field(
        description="User's chosen action for the topics"
    )
    accepted_topics: List[str] = Field(description="Topics user wants to keep")
    rejected_topics: List[str] = Field(description="Topics user wants to remove")
    modification_request: str = Field(description="User's request for changes")
    desired_topic_count: Optional[int] = Field(
        default=None, description="Number of topics user wants"
    )


class FeedbackInterpretation(BaseModel):
    user_feedback: UserFeedback = Field(
        description="Structured interpretation of user input"
    )
    reasoning: str = Field(description="LLM's reasoning for the interpretation")


class BatchAnalysis(BaseModel):
    current_topics: List[str] = Field(description="Topics found in current batch")
    accumulated_summary: str = Field(
        description="Summary of all content processed so far"
    )
    batch_summary: str = Field(description="Summary of current batch only")
