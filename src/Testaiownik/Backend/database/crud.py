# src/Backend/database/crud.py
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import uuid

from .models import User, Quiz, Document, ActivityLog


# User Operations
def create_user(db: Session, user_id: str) -> User:
    """Create new user"""
    user = User(user_id=user_id)
    db.add(user)
    db.commit()
    db.refresh(user)

    _ = (
        user.user_id,
        user.created_at,
        user.last_activity,
        user.quizzes,
    )  ## Unpack to avoid weird 500 errors
    log_activity(db, user_id, "user_created")
    db.expunge(user)  # Remove from session to avoid stale data issues
    return user


def get_user(db: Session, user_id: str) -> Optional[User]:
    """Get user by ID"""
    return db.query(User).filter(User.user_id == user_id).first()


def update_user_activity(db: Session, user_id: str):
    """Update user last activity"""
    user = db.query(User).filter(User.user_id == user_id).first()
    if user:
        user.last_activity = datetime.now()
        db.commit()


def delete_user(db: Session, user_id: str) -> bool:
    """Delete user and all associated data"""
    user = db.query(User).filter(User.user_id == user_id).first()
    if user:
        db.delete(user)
        db.commit()
        log_activity(db, user_id, "user_deleted")
        return True
    return False


# Quiz Operations
def create_quiz(db: Session, user_id: str) -> Quiz:
    """Create new quiz"""
    quiz_id = f"quiz_{uuid.uuid4()}"
    quiz = Quiz(quiz_id=quiz_id, user_id=user_id)
    db.add(quiz)
    db.commit()
    db.refresh(quiz)

    _ = (
        quiz.quiz_id,
        quiz.user_id,
        quiz.status,
        quiz.collection_name,
        quiz.desired_topic_count,
        quiz.suggested_topics,
        quiz.confirmed_topics,
        quiz.topic_feedback_request,
        quiz.topic_conversation_history,
        quiz.langgraph_topic_state,
        quiz.total_questions,
        quiz.difficulty,
        quiz.current_question_index,
        quiz.questions_data,
        quiz.user_answers,
        quiz.langgraph_quiz_state,
    )  ## Unpack to avoid weird 500 errors
    # Log activity for creating a new quiz
    log_activity(db, user_id, "quiz_created", {"quiz_id": quiz_id})
    # db.expunge(quiz)  # Remove from session to avoid stale data issues
    return quiz


def get_quiz(db: Session, quiz_id: str) -> Optional[Quiz]:
    """Get quiz by ID"""
    return db.query(Quiz).filter(Quiz.quiz_id == quiz_id).first()


def get_quizzes_by_user(
    db: Session, user_id: str, limit: int = 10, offset: int = 0
) -> List[Quiz]:
    """Get quizzes for user"""
    return (
        db.query(Quiz)
        .filter(Quiz.user_id == user_id)
        .order_by(desc(Quiz.created_at))
        .offset(offset)
        .limit(limit)
        .all()
    )


def update_quiz(db: Session, quiz_id: str, **kwargs):
    """Update quiz fields"""
    quiz = db.query(Quiz).filter(Quiz.quiz_id == quiz_id).first()
    if quiz:
        for key, value in kwargs.items():
            if hasattr(quiz, key):
                setattr(quiz, key, value)
        quiz.updated_at = datetime.now()
        db.commit()


def update_quiz_status(db: Session, quiz_id: str, status: str):
    """Update quiz status"""
    quiz = db.query(Quiz).filter(Quiz.quiz_id == quiz_id).first()
    if quiz:
        quiz.status = status
        quiz.updated_at = datetime.now()
        db.commit()


def update_quiz_collection(db: Session, quiz_id: str, collection_name: str):
    """Update quiz collection name"""
    quiz = db.query(Quiz).filter(Quiz.quiz_id == quiz_id).first()
    if quiz:
        quiz.collection_name = collection_name
        quiz.updated_at = datetime.now()
        db.commit()


# Topic Selection Operations
def start_topic_analysis(db: Session, quiz_id: str, desired_topic_count: int = 10):
    """Start topic analysis for quiz"""
    quiz = db.query(Quiz).filter(Quiz.quiz_id == quiz_id).first()
    if quiz:
        quiz.status = "topic_analysis"
        quiz.desired_topic_count = desired_topic_count
        quiz.topic_analysis_started_at = datetime.now()
        quiz.suggested_topics = []
        quiz.topic_conversation_history = []
        quiz.updated_at = datetime.now()
        db.commit()
        return True
    return False


def update_topic_data(db: Session, quiz_id: str, **kwargs):
    """Update topic-related data for quiz"""
    quiz = db.query(Quiz).filter(Quiz.quiz_id == quiz_id).first()
    if quiz:
        topic_fields = [
            "suggested_topics",
            "confirmed_topics",
            "topic_feedback_request",
            "topic_conversation_history",
            "langgraph_topic_state",
            "desired_topic_count",
        ]

        for key, value in kwargs.items():
            if key in topic_fields and hasattr(quiz, key):
                setattr(quiz, key, value)

        quiz.updated_at = datetime.now()

        if "confirmed_topics" in kwargs and kwargs["confirmed_topics"]:
            quiz.topic_analysis_completed_at = datetime.now()
            quiz.status = "topic_ready"

        db.commit()
        return True
    return False


def confirm_quiz_topics(db: Session, quiz_id: str, confirmed_topics: List[Dict]):
    """Confirm final topics for quiz"""
    quiz = db.query(Quiz).filter(Quiz.quiz_id == quiz_id).first()
    if quiz:
        quiz.confirmed_topics = confirmed_topics
        quiz.status = "topic_ready"
        quiz.topic_analysis_completed_at = datetime.now()
        quiz.updated_at = datetime.now()
        db.commit()
        return True
    return False


# Quiz Execution Operations
def start_quiz_execution(
    db: Session, quiz_id: str, total_questions: int, difficulty: str
):
    """Start quiz execution"""
    quiz = db.query(Quiz).filter(Quiz.quiz_id == quiz_id).first()
    if quiz:
        quiz.status = "quiz_active"
        quiz.total_questions = total_questions
        quiz.difficulty = difficulty
        quiz.current_question_index = 0
        quiz.user_answers = []
        quiz.quiz_started_at = datetime.now()
        quiz.updated_at = datetime.now()
        db.commit()
        return True
    return False


def update_quiz_progress(db: Session, quiz_id: str, **kwargs):
    """Update quiz execution progress"""
    quiz = db.query(Quiz).filter(Quiz.quiz_id == quiz_id).first()
    if quiz:
        execution_fields = [
            "current_question_index",
            "questions_data",
            "user_answers",
            "langgraph_quiz_state",
        ]

        for key, value in kwargs.items():
            if key in execution_fields and hasattr(quiz, key):
                setattr(quiz, key, value)

        quiz.updated_at = datetime.now()
        db.commit()
        return True
    return False


def complete_quiz(db: Session, quiz_id: str):
    """Mark quiz as completed"""
    quiz = db.query(Quiz).filter(Quiz.quiz_id == quiz_id).first()
    if quiz:
        quiz.status = "quiz_completed"
        quiz.quiz_completed_at = datetime.now()
        quiz.updated_at = datetime.now()
        db.commit()
        return True
    return False


def reset_quiz_execution(db: Session, quiz_id: str):
    """Reset just the quiz execution, keep topics"""
    quiz = db.query(Quiz).filter(Quiz.quiz_id == quiz_id).first()
    if quiz:
        quiz.status = "topic_ready"
        quiz.total_questions = None
        quiz.difficulty = None
        quiz.current_question_index = 0
        quiz.questions_data = None
        quiz.user_answers = []
        quiz.langgraph_quiz_state = None
        quiz.quiz_started_at = None
        quiz.quiz_completed_at = None
        quiz.updated_at = datetime.now()
        db.commit()
        return True
    return False


# Document Operations
def create_document(
    db: Session,
    quiz_id: str,
    filename: str,
    file_path: str,
    size_bytes: int,
    file_type: str,
) -> Document:
    """Create document record"""
    doc_id = f"doc_{uuid.uuid4()}"
    document = Document(
        doc_id=doc_id,
        quiz_id=quiz_id,
        filename=filename,
        file_path=file_path,
        size_bytes=size_bytes,
        file_type=file_type,
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    # Update quiz status if this is the first document
    quiz = db.query(Quiz).filter(Quiz.quiz_id == quiz_id).first()
    if quiz and quiz.status == "created":
        quiz.status = "documents_uploaded"
        db.commit()

    # Access all attributes to load them into memory before expunge
    _ = (
        document.doc_id,
        document.filename,
        document.file_path,
        document.size_bytes,
        document.file_type,
        document.uploaded_at,
        document.indexed,
    )
    db.expunge(document)  # Remove from session to avoid stale data issues
    return document


def get_documents_by_quiz(db: Session, quiz_id: str) -> List[Document]:
    """Get all documents for quiz"""
    return db.query(Document).filter(Document.quiz_id == quiz_id).all()


def update_document_indexed(db: Session, doc_id: str, indexed: bool):
    """Update document indexing status"""
    document = db.query(Document).filter(Document.doc_id == doc_id).first()
    if document:
        document.indexed = indexed
        db.commit()

        # If all documents are indexed, update quiz status
        if indexed:
            quiz_docs = (
                db.query(Document).filter(Document.quiz_id == document.quiz_id).all()
            )
            if all(doc.indexed for doc in quiz_docs):
                quiz = db.query(Quiz).filter(Quiz.quiz_id == document.quiz_id).first()
                if quiz and quiz.status == "documents_uploaded":
                    quiz.status = "documents_indexed"
                    db.commit()


def delete_document(db: Session, doc_id: str) -> bool:
    """Delete document"""
    document = db.query(Document).filter(Document.doc_id == doc_id).first()
    if document:
        db.delete(document)
        db.commit()
        return True
    return False


# Activity Logging
def log_activity(
    db: Session, user_id: str, action: str, details: Optional[Dict[str, Any]] = None
):
    """Log user activity"""
    try:
        activity = ActivityLog(user_id=user_id, action=action, details=details or {})
        db.add(activity)
        db.commit()
    except Exception as e:
        # Log error but don't break the flow
        import logging

        logging.error(f"Failed to log activity: {e}")


# Statistics
def get_system_stats(db: Session) -> Dict[str, Any]:
    """Get system usage statistics"""
    total_quizzes = db.query(func.count(Quiz.quiz_id)).scalar()
    total_documents = db.query(func.count(Document.doc_id)).scalar()

    # Active users (activity in last 24h)
    cutoff = datetime.now() - timedelta(hours=24)
    active_users = (
        db.query(func.count(User.user_id)).filter(User.last_activity > cutoff).scalar()
    )

    return {
        "total_quizzes": total_quizzes or 0,
        "total_documents": total_documents or 0,
        "total_questions_generated": 0,
        "active_users": active_users or 0,
    }


def get_user_stats(db: Session, user_id: str) -> Dict[str, Any]:
    """Get user statistics"""
    quizzes_created = (
        db.query(func.count(Quiz.quiz_id)).filter(Quiz.user_id == user_id).scalar()
    )

    documents_uploaded = (
        db.query(func.count(Document.doc_id))
        .join(Quiz)
        .filter(Quiz.user_id == user_id)
        .scalar()
    )

    # Count questions answered from user_answers in quizzes
    questions_answered = 0
    user_quizzes = db.query(Quiz).filter(Quiz.user_id == user_id).all()

    for quiz in user_quizzes:
        if quiz.user_answers:
            unique_questions = set()
            for answer in quiz.user_answers:
                if isinstance(answer, dict) and answer.get("attempt_number", 1) == 1:
                    unique_questions.add(answer.get("question_id"))
            questions_answered += len(unique_questions)

    return {
        "quizzes_created": quizzes_created or 0,
        "documents_uploaded": documents_uploaded or 0,
        "questions_answered": questions_answered,
    }
