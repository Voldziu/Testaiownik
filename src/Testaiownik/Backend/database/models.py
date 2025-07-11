# src/Backend/database/models.py
from sqlalchemy import (
    Column,
    String,
    Integer,
    DateTime,
    Text,
    Boolean,
    JSON,
    ForeignKey,
)
from sqlalchemy.orm import relationship
from datetime import datetime

from .sql_database_connector import Base


class User(Base):
    """User tracking"""

    __tablename__ = "users"

    user_id = Column(String(50), primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.now)
    last_activity = Column(DateTime, default=datetime.now)

    quizzes = relationship("Quiz", back_populates="user", cascade="all, delete-orphan")


class Quiz(Base):
    """Quiz instances with embedded topic selection and quiz execution"""

    __tablename__ = "quizzes"

    quiz_id = Column(String(100), primary_key=True, index=True)
    user_id = Column(String(50), ForeignKey("users.user_id"), index=True)

    status = Column(String(20), default="created")
   
    collection_name = Column(String(100), nullable=True)

    desired_topic_count = Column(Integer, default=10)
    suggested_topics = Column(JSON, nullable=True) 
    confirmed_topics = Column(JSON, nullable=True) 
    topic_feedback_request = Column(Text, nullable=True)
    topic_conversation_history = Column(JSON, default=list)
    langgraph_topic_state = Column(
        JSON, nullable=True
    )  

    
    total_questions = Column(Integer, nullable=True)
    difficulty = Column(String(20), nullable=True)  
    current_question_index = Column(Integer, default=0)
    questions_data = Column(JSON, nullable=True)  
    user_answers = Column(JSON, default=list) 
    langgraph_quiz_state = Column(JSON, nullable=True) 

    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    topic_analysis_started_at = Column(DateTime, nullable=True)
    topic_analysis_completed_at = Column(DateTime, nullable=True)
    quiz_started_at = Column(DateTime, nullable=True)
    quiz_completed_at = Column(DateTime, nullable=True)

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
    file_type = Column(String(10))  
    uploaded_at = Column(DateTime, default=datetime.now)
    indexed = Column(Boolean, default=False)

    quiz = relationship("Quiz", back_populates="documents")


class ActivityLog(Base):
    """User activity tracking"""

    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(50), index=True)
    action = Column(
        String(50)
    )  
    details = Column(JSON, nullable=True)
    timestamp = Column(DateTime, default=datetime.now)
