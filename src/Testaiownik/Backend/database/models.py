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


class Session(Base):
    """Browser session tracking"""

    __tablename__ = "sessions"

    session_id = Column(String(50), primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.now)
    last_activity = Column(DateTime, default=datetime.now)

    # Relationships
    quizzes = relationship(
        "Quiz", back_populates="session", cascade="all, delete-orphan"
    )


class Quiz(Base):
    """Quiz instances"""

    __tablename__ = "quizzes"

    quiz_id = Column(String(50), primary_key=True, index=True)
    session_id = Column(String(50), ForeignKey("sessions.session_id"), index=True)
    status = Column(
        String(20), default="created"
    )  # created, analyzing, ready, active, completed
    collection_name = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # Relationships
    session = relationship("Session", back_populates="quizzes")
    documents = relationship(
        "Document", back_populates="quiz", cascade="all, delete-orphan"
    )
    topic_sessions = relationship(
        "TopicSession", back_populates="quiz", cascade="all, delete-orphan"
    )
    quiz_sessions = relationship(
        "QuizSession", back_populates="quiz", cascade="all, delete-orphan"
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


class TopicSession(Base):
    """Topic selection workflow state"""

    __tablename__ = "topic_sessions"

    topic_session_id = Column(String(50), primary_key=True, index=True)
    quiz_id = Column(String(50), ForeignKey("quizzes.quiz_id"), index=True)
    status = Column(
        String(20), default="analyzing"
    )  # analyzing, awaiting_feedback, completed
    desired_topic_count = Column(Integer, default=10)
    suggested_topics = Column(JSON, nullable=True)  # List of WeightedTopic
    confirmed_topics = Column(JSON, nullable=True)  # Final topics
    conversation_history = Column(JSON, default=list)
    feedback_request = Column(Text, nullable=True)
    langgraph_state = Column(JSON, nullable=True)  # Complete LangGraph state
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # Relationships
    quiz = relationship("Quiz", back_populates="topic_sessions")


class QuizSession(Base):
    """Quiz execution state"""

    __tablename__ = "quiz_sessions"

    quiz_session_id = Column(String(50), primary_key=True, index=True)
    quiz_id = Column(String(50), ForeignKey("quizzes.quiz_id"), index=True)
    status = Column(
        String(20), default="generating"
    )  # generating, active, paused, completed
    total_questions = Column(Integer)
    difficulty = Column(String(20))
    current_question_index = Column(Integer, default=0)
    questions_data = Column(JSON, nullable=True)  # All generated questions
    user_answers = Column(JSON, default=list)  # User's answers
    langgraph_state = Column(JSON, nullable=True)  # Complete quiz state
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    quiz = relationship("Quiz", back_populates="quiz_sessions")


class ActivityLog(Base):
    """User activity tracking"""

    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(50), index=True)
    action = Column(String(50))  # quiz_created, document_uploaded, etc.
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
