# src/testaiownik/agent/models.py
from pydantic import BaseModel, Field, model_validator
from typing import List, Optional, Literal, Self
from Agent.Shared import WeightedTopic


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
    current_topics: List[WeightedTopic] = Field(
        description="Topics found in current batch with weights"
    )
    accumulated_summary: str = Field(
        description="Summary of all content processed so far"
    )
    batch_summary: str = Field(description="Summary of current batch only")

    @model_validator(mode="after")
    def validate_weights_sum_to_one(self) -> Self:
        if self.current_topics:
            total_weight = sum(topic.weight for topic in self.current_topics)
            if abs(total_weight - 1.0) > 0.01:  # Allow small floating point errors
                raise ValueError(
                    f"Consolidated topic weights must sum to 1.0, got {total_weight}"
                )
        return self


class TopicConsolidation(BaseModel):
    consolidated_topics: List[WeightedTopic] = Field(
        description="Final consolidated topic list with weights"
    )
    reasoning: str = Field(description="How topics were consolidated")

    # @model_validator(mode="after")
    # def validate_weights_sum_to_one(self) -> Self:
    #     if self.consolidated_topics:
    #         total_weight = sum(topic.weight for topic in self.consolidated_topics)
    #         if abs(total_weight - 1.0) > 0.01:  # Allow small floating point errors
    #             raise ValueError(
    #                 f"Consolidated topic weights must sum to 1.0, got {total_weight}"
    #             )
    #     return self
