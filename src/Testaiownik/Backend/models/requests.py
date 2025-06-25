# src/Testaiownik/Backend/models/requests.py
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime


# Topic Selection Requests
class TopicAnalysisRequest(BaseModel):
    desired_topic_count: int = Field(default=10, ge=1, le=50)


class TopicFeedbackRequest(BaseModel):
    user_input: str = Field(..., min_length=1, max_length=1000)


class AddTopicRequest(BaseModel):
    topic_name: str = Field(..., min_length=1, max_length=200)
    weight: float = Field(..., ge=0.0, le=1.0)


class UpdateTopicRequest(BaseModel):
    new_name: Optional[str] = Field(None, min_length=1, max_length=200)
    new_weight: Optional[float] = Field(None, ge=0.0, le=1.0)


# Quiz Requests
class StartQuizRequest(BaseModel):
    confirmed_topics: List[Dict[str, Any]]  # WeightedTopic format
    total_questions: int = Field(default=20, ge=1)
    difficulty: Literal["easy", "medium", "hard", "very-hard"] = "very-hard"
    user_questions: List[str] = Field(default_factory=list)


class AnswerQuestionRequest(BaseModel):
    selected_choices: List[int] = Field(..., min_items=1)
    question_id: str


class QuizDifficultyRequest(BaseModel):
    difficulty: Literal["easy", "medium", "hard", "very-hard"]


class QuizQuestionsRequest(BaseModel):
    total_questions: int = Field(..., ge=1)


class UserQuestionsRequest(BaseModel):
    user_questions: List[str] = Field(..., min_items=1, max_items=20)


# Document Requests
class IndexDocumentsRequest(BaseModel):
    chunk_size: int = Field(default=500, ge=100)
    batch_size: int = Field(default=50, ge=10)
