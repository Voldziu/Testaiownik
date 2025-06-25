# src/Testaiownik/Backend/database/models.py
from sqlalchemy import (
    create_engine,
    Column,
    String,
    Integer,
    DateTime,
    Text,
    Boolean,
    Float,
    JSON,
    ForeignKey,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./testaiownik.db")
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    """User tracking"""

    __tablename__ = "users"

    user_id = Column(String(50), primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.now)
    last_activity = Column(DateTime, default=datetime.now)

    # Relationships
    quizzes = relationship("Quiz", back_populates="user", cascade="all, delete-orphan")


class Quiz(Base):
    """Quiz instances with embedded topic selection and quiz execution"""

    __tablename__ = "quizzes"

    quiz_id = Column(String(50), primary_key=True, index=True)
    user_id = Column(String(50), ForeignKey("users.user_id"), index=True)

    # Status tracking - single status for entire quiz lifecycle
    status = Column(String(20), default="created")
    # Possible statuses: created, documents_uploaded, documents_indexed,
    # topic_analysis, topic_feedback, topic_ready, quiz_active, quiz_completed, failed

    # Document management
    collection_name = Column(String(100), nullable=True)

    # Topic selection data (previously topic_sessions)
    desired_topic_count = Column(Integer, default=10)
    suggested_topics = Column(JSON, nullable=True)  # List of WeightedTopic dicts
    confirmed_topics = Column(JSON, nullable=True)  # Final confirmed topics
    topic_feedback_request = Column(Text, nullable=True)
    topic_conversation_history = Column(JSON, default=list)
    langgraph_topic_state = Column(
        JSON, nullable=True
    )  # Complete LangGraph state for topic selection

    # Quiz execution data (previously quiz_sessions)
    total_questions = Column(Integer, nullable=True)
    difficulty = Column(String(20), nullable=True)  # easy, medium, hard
    current_question_index = Column(Integer, default=0)
    questions_data = Column(JSON, nullable=True)  # All generated questions
    user_answers = Column(JSON, default=list)  # User's answers with timestamps
    langgraph_quiz_state = Column(JSON, nullable=True)  # Complete quiz state

    # Timestamps
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    topic_analysis_started_at = Column(DateTime, nullable=True)
    topic_analysis_completed_at = Column(DateTime, nullable=True)
    quiz_started_at = Column(DateTime, nullable=True)
    quiz_completed_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="quizzes")
    documents = relationship(
        "Document", back_populates="quiz", cascade="all, delete-orphan"
    )


class Document(Base):
    """Uploaded documents"""

    __tablename__ = "documents"

    doc_id = Column(String(50), primary_key=True, index=True)
    quiz_id = Column(String(50), ForeignKey("quizzes.quiz_id"), index=True)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    size_bytes = Column(Integer)
    file_type = Column(String(10))  # pdf, docx, txt, pptx
    uploaded_at = Column(DateTime, default=datetime.now)
    indexed = Column(Boolean, default=False)

    # Relationships
    quiz = relationship("Quiz", back_populates="documents")


class ActivityLog(Base):
    """User activity tracking"""

    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(50), index=True)
    action = Column(
        String(50)
    )  # quiz_created, document_uploaded, topic_confirmed, quiz_completed, etc.
    details = Column(JSON, nullable=True)
    timestamp = Column(DateTime, default=datetime.now)


def init_db():
    """Initialize database tables"""
    Base.metadata.create_all(bind=engine)


def get_db():
    """Database session dependency"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
