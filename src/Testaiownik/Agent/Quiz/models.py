from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal
from Agent.Shared import WeightedTopic
import uuid
from datetime import datetime


class QuestionChoice(BaseModel):
    text: str = Field(description="Choice text")
    is_correct: bool = Field(description="Whether this choice is correct")


class Question(BaseModel):
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()), description="Unique question ID"
    )
    topic: str = Field(description="Topic this question belongs to")
    question_text: str = Field(description="The actual question")
    choices: List[QuestionChoice] = Field(description="Multiple choice options")
    explanation: str = Field(description="Explanation of correct answer")
    difficulty: Literal["easy", "medium", "hard"] = Field(
        default="medium", description="Question difficulty"
    )


class UserAnswer(BaseModel):
    question_id: str = Field(description="ID of answered question")
    selected_choice_index: int = Field(description="Index of selected choice")
    is_correct: bool = Field(description="Whether answer was correct")
    answered_at: datetime = Field(
        default_factory=datetime.now, description="When answered"
    )


class QuizSession(BaseModel):
    session_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()), description="Unique session ID"
    )
    topics: List[WeightedTopic] = Field(
        description="Topics with weights from previous graph"
    )
    total_questions: int = Field(description="Total number of questions for this quiz")
    questions_per_topic: Dict[str, int] = Field(
        description="Question distribution per topic"
    )
    generated_questions: List[Question] = Field(
        default_factory=list, description="All generated questions"
    )
    current_question_index: int = Field(
        default=0, description="Current position in quiz"
    )
    user_answers: List[UserAnswer] = Field(
        default_factory=list, description="User's answers so far"
    )
    status: Literal["generating", "active", "completed", "paused"] = Field(
        default="generating", description="Quiz status"
    )
    created_at: datetime = Field(
        default_factory=datetime.now, description="Session creation time"
    )

    # Future persistence fields
    user_id: Optional[str] = Field(default=None, description="User ID for persistence")
    last_activity: datetime = Field(
        default_factory=datetime.now, description="Last user activity"
    )


class QuizResults(BaseModel):
    session_id: str = Field(description="Quiz session ID")
    total_questions: int = Field(description="Total questions in quiz")
    correct_answers: int = Field(description="Number of correct answers")
    score_percentage: float = Field(description="Score as percentage")
    topic_scores: Dict[str, Dict[str, Any]] = Field(description="Per-topic performance")
    time_taken: Optional[float] = Field(
        default=None, description="Total time in minutes"
    )


class QuestionGeneration(BaseModel):
    topic: str = Field(description="Topic to generate questions for")
    questions: List[Question] = Field(description="Generated questions for this topic")
    reasoning: str = Field(description="LLM reasoning for question generation")
