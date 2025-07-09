from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal
import uuid
from datetime import datetime

from Agent.Shared import WeightedTopic


class QuestionChoice(BaseModel):
    text: str = Field(description="Choice text")
    is_correct: bool = Field(description="Whether this choice is correct")


class SourceMetadata(BaseModel):
    """Metadata about the source document/chunk used for question generation"""

    source: str = Field(description="Source document name")
    page: Optional[int] = Field(default=None, description="Page number (for PDFs)")
    slide: Optional[int] = Field(default=None, description="Slide number (for PPTX)")
    chunk_text: Optional[str] = Field(
        default=None, description="Original chunk text used"
    )


class Question(BaseModel):
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()), description="Unique question ID"
    )
    topic: str = Field(description="Topic this question belongs to")
    question_text: str = Field(description="The actual question")
    choices: List[QuestionChoice] = Field(
        description="All possible choices (2+ options)"
    )
    explanation: str = Field(description="Explanation of correct answer(s)")
    difficulty: Literal["easy", "medium", "hard", "very-hard"] = Field(
        default="medium", description="Question difficulty"
    )
    is_multi_choice: bool = Field(
        default=False, description="Whether multiple choices can be selected"
    )
    generated_at: datetime = Field(
        default_factory=datetime.now, description="When question was generated"
    )
    source_metadata: Optional[SourceMetadata] = Field(
        default=None, description="Metadata about source document/chunk"
    )

    def get_correct_indices(self) -> List[int]:
        """Get indices of all correct choices"""
        return [i for i, choice in enumerate(self.choices) if choice.is_correct]

    def is_answer_correct(self, selected_indices: List[int]) -> bool:
        """Check if selected indices match exactly the correct answers"""
        correct_indices = set(self.get_correct_indices())
        selected_set = set(selected_indices)
        return correct_indices == selected_set


class UserAnswer(BaseModel):
    question_id: str = Field(description="ID of answered question")
    selected_choice_indices: List[int] = Field(
        description="Indices of selected choices"
    )
    is_correct: bool = Field(description="Whether answer was correct")
    answered_at: datetime = Field(
        default_factory=datetime.now, description="When answered"
    )
    attempt_number: int = Field(
        default=1, description="Which attempt (for recycled questions)"
    )


class QuizSession(BaseModel):
    session_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()), description="Unique session ID"
    )
    topics: List[WeightedTopic] = Field(
        description="Topics with weights from previous graph"
    )
    total_questions: int = Field(description="Total number of questions for this quiz")
    difficulty: Literal["easy", "medium", "hard", "very-hard"] = Field(
        default="medium", description="Global quiz difficulty"
    )
    copies_per_incorrect_answer: int = Field(
        default=2,
        description="Number of copies to add when question is answered incorrectly",
    )
    batch_size: int = Field(default=5, description="Questions generated per batch")

    quiz_mode: Literal["fresh", "retry_same", "retry_failed"] = Field(
        default="fresh", description="Quiz generation mode"
    )

    questions_per_topic: Dict[str, int] = Field(
        description="Question distribution per topic"
    )
    all_generated_questions: List[Question] = Field(
        default_factory=list, description="All questions ever generated in this session"
    )
    active_question_pool: List[str] = Field(
        default_factory=list, description="Question IDs in current quiz"
    )
    incorrect_recycle_count: Dict[str, int] = Field(
        default_factory=dict, description="Question ID -> recycle count"
    )

    current_question_index: int = Field(
        default=0, description="Current position in active_question_pool"
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
    last_activity: datetime = Field(
        default_factory=datetime.now, description="Last user activity"
    )
    user_id: Optional[str] = Field(default=None, description="User ID for persistence")

    def get_current_question(self) -> Optional[Question]:
        """Get the current question object"""
        if self.current_question_index >= len(self.active_question_pool):
            return None

        question_id = self.active_question_pool[self.current_question_index]
        return next(
            (q for q in self.all_generated_questions if q.id == question_id), None
        )

    def add_answer(self, answer: UserAnswer) -> None:
        """Add user answer and handle incorrect question recycling"""
        self.user_answers.append(answer)
        self.last_activity = datetime.now()

        if not answer.is_correct:
            for _ in range(self.copies_per_incorrect_answer):
                self.active_question_pool.append(answer.question_id)

    def is_completed(self) -> bool:
        """Check if quiz is completed"""
        return self.current_question_index >= len(self.active_question_pool)

    def get_next_question(self) -> Optional[Question]:
        """Advance to next question and return it"""
        if not self.is_completed():
            self.current_question_index += 1
        return self.get_current_question()


class QuizResults(BaseModel):
    session_id: str = Field(description="Quiz session ID")
    total_questions: int = Field(description="Total questions answered")
    correct_answers: int = Field(description="Number of correct answers")
    score_percentage: float = Field(description="Score as percentage")
    topic_scores: Dict[str, Dict[str, Any]] = Field(description="Per-topic performance")
    time_taken: Optional[float] = Field(
        default=None, description="Total time in minutes"
    )
    completed_at: datetime = Field(
        default_factory=datetime.now, description="When quiz was completed"
    )


class QuestionGeneration(BaseModel):
    """Model for LLM question generation output"""

    topic: str = Field(description="Topic these questions belong to")
    questions: List[Question] = Field(description="Generated questions for this topic")
    reasoning: str = Field(description="LLM reasoning for question generation")


class QuizConfiguration(BaseModel):
    """Configuration for quiz initialization"""

    topics: List[WeightedTopic] = Field(description="Topics with weights")
    total_questions: int = Field(default=20, description="Total questions to generate")
    difficulty: Literal["easy", "medium", "hard", "very-hard"] = Field(
        default="medium", description="Global difficulty"
    )
    batch_size: int = Field(default=5, description="Questions per generation batch")
    copies_per_incorrect_answer: int = Field(
        default=2,
        description="Number of copies to add when question is answered incorrectly",
    )

    quiz_mode: Literal["fresh", "retry_same", "retry_failed"] = Field(
        default="fresh", description="Quiz mode"
    )
    user_questions: List[str] = Field(
        default_factory=list, description="User-provided questions to include in quiz"
    )
    user_id: Optional[str] = Field(default=None, description="User ID")
    previous_session_id: Optional[str] = Field(
        default=None, description="Previous session for retry modes"
    )


class UserQuestionResponse(BaseModel):
    correct_answers: List[str] = Field(description="The correct answer(s)")
    wrong_options: List[str] = Field(
        default_factory=list, description="Wrong answer options"
    )
    explanation: str = Field(description="Detailed explanation of the answer")
    assigned_topic: str = Field(description="Most relevant topic for this question")
    is_multi_choice: bool = Field(
        default=False, description="Whether multiple answers can be selected"
    )
