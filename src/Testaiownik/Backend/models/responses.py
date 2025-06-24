# src/Testaiownik/Backend/models/responses.py
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime


# Base response models
class BaseResponse(BaseModel):
    success: bool = True
    timestamp: datetime = Field(default_factory=datetime.now)


class ErrorResponse(BaseModel):
    error: str
    message: str
    details: Optional[Dict[str, Any]] = None


# Quiz responses
class QuizCreateResponse(BaseResponse):
    quiz_id: str
    created_at: datetime
    status: str


class QuizListItem(BaseModel):
    quiz_id: str
    created_at: datetime
    status: str
    document_count: int
    topic_count: int


class QuizListResponse(BaseResponse):
    quizzes: List[QuizListItem]
    total: int


# Document responses
class DocumentItem(BaseModel):
    doc_id: str
    filename: str
    size_bytes: int
    type: str
    uploaded_at: datetime
    indexed: bool


class DocumentUploadResponse(BaseResponse):
    uploaded_files: List[DocumentItem]
    quiz_id: str


class DocumentListResponse(BaseResponse):
    documents: List[DocumentItem]
    quiz_id: str
    total_documents: int


class DocumentStatusResponse(BaseResponse):
    quiz_id: str
    indexing_status: Literal["pending", "processing", "completed", "failed"]
    indexed_documents: int
    total_documents: int
    collection_name: Optional[str]
    chunk_count: Optional[int]


class DocumentDeleteResponse(BaseResponse):
    message: str
    doc_id: str
    reindexing_required: bool


class DocumentIndexResponse(BaseResponse):
    collection_name: str
    indexed_documents: int
    total_chunks: int
    indexing_time_seconds: float


# Topic Selection responses
class WeightedTopicResponse(BaseModel):
    topic: str
    weight: float


class TopicAnalysisStartResponse(BaseResponse):
    topic_session_id: str
    quiz_id: str
    status: str
    estimated_completion: Optional[datetime]


class TopicSessionStatusResponse(BaseResponse):
    topic_session_id: str
    status: str
    suggested_topics: List[WeightedTopicResponse]
    feedback_request: Optional[str]
    conversation_history: List[Dict[str, Any]]


class TopicFeedbackResponse(BaseResponse):
    feedback_processed: bool
    action_taken: str
    next_step: str
    message: str


class TopicConfirmResponse(BaseResponse):
    confirmed_topics: List[WeightedTopicResponse]
    total_topics: int
    ready_for_quiz: bool
    quiz_id: str


class TopicDeleteResponse(BaseResponse):
    deleted_topic: str
    remaining_topics: int
    weights_redistributed: bool


class TopicAddResponse(BaseResponse):
    added_topic: WeightedTopicResponse
    total_topics: int
    weights_normalized: bool


class TopicUpdateResponse(BaseResponse):
    old_topic: str
    new_topic: WeightedTopicResponse
    weights_normalized: bool


class TopicSuggestionsResponse(BaseResponse):
    suggestions: List[Dict[str, Any]]
    total_suggestions: int


# Quiz execution responses
class QuestionChoice(BaseModel):
    text: str
    is_correct: bool


class QuestionResponse(BaseModel):
    id: str
    topic: str
    question_text: str
    choices: List[QuestionChoice]
    is_multi_choice: bool
    difficulty: str


class QuizProgressResponse(BaseModel):
    current_question_number: int
    total_questions: int
    answered: int
    correct: int


class QuizStartResponse(BaseResponse):
    quiz_session_id: str
    status: str
    estimated_generation_time: int
    total_questions: int


class QuizCurrentResponse(BaseResponse):
    current_question: Optional[QuestionResponse]
    progress: QuizProgressResponse
    status: str


class QuizAnswerResponse(BaseResponse):
    correct: bool
    explanation: str
    selected_answers: List[str]
    correct_answers: List[str]
    next_question_available: bool
    progress: QuizProgressResponse


class TopicScore(BaseModel):
    correct: int
    total: int
    percentage: float


class QuizResults(BaseModel):
    session_id: str
    total_questions: int
    correct_answers: int
    score_percentage: float
    topic_scores: Dict[str, TopicScore]
    completed_at: datetime


class QuizResultsResponse(BaseResponse):
    quiz_results: QuizResults
    status: str


# Session responses
class SessionItem(BaseModel):
    session_id: str
    created_at: datetime
    last_activity: datetime
    quiz_count: int


class SessionListResponse(BaseResponse):
    current_session: str
    sessions: List[SessionItem]


class SessionDetailResponse(BaseResponse):
    session_id: str
    created_at: datetime
    last_activity: datetime
    quizzes: List[str]
    activity_log: List[Dict[str, Any]]


class SessionDeleteResponse(BaseResponse):
    message: str
    deleted_quizzes: int


# Statistics responses
class SystemStats(BaseModel):
    total_quizzes: int
    total_documents: int
    total_questions_generated: int
    active_sessions: int


class UserStats(BaseModel):
    quizzes_created: int
    documents_uploaded: int
    questions_answered: int


class StatsResponse(BaseResponse):
    system_stats: SystemStats
    user_stats: UserStats


# Collections responses
class CollectionItem(BaseModel):
    name: str
    vector_count: int
    created_at: datetime
    quiz_id: str


class CollectionsResponse(BaseResponse):
    collections: List[CollectionItem]
    total_collections: int


class CollectionDeleteResponse(BaseResponse):
    deleted_collection: str
    vector_count_deleted: int


# Search responses
class SearchResultItem(BaseModel):
    text: str
    source: str
    page: Optional[int]
    relevance_score: float
    quiz_id: str


class SearchResponse(BaseResponse):
    query: str
    results: List[SearchResultItem]
    total_results: int
    search_time_ms: int
