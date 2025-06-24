# src/Testaiownik/Backend/database/crud.py
from sqlalchemy.orm import Session as DBSession
from sqlalchemy import func, desc
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import uuid

from .models import (
    get_db,
    Session,
    Quiz,
    Document,
    TopicSession,
    QuizSession,
    ActivityLog,
)
from utils import logger


# Session Operations
def create_session(session_id: str) -> Session:
    """Create new session"""
    db = next(get_db())
    try:
        session = Session(session_id=session_id)
        db.add(session)
        db.commit()
        db.refresh(session)

        # Log activity
        log_activity(session_id, "session_created")
        return session
    finally:
        db.close()


def get_session(session_id: str) -> Optional[Session]:
    """Get session by ID"""
    db = next(get_db())
    try:
        return db.query(Session).filter(Session.session_id == session_id).first()
    finally:
        db.close()


def update_session_activity(session_id: str):
    """Update session last activity"""
    db = next(get_db())
    try:
        session = db.query(Session).filter(Session.session_id == session_id).first()
        if session:
            session.last_activity = datetime.now()
            db.commit()
    finally:
        db.close()


def delete_session(session_id: str) -> bool:
    """Delete session and all associated data"""
    db = next(get_db())
    try:
        session = db.query(Session).filter(Session.session_id == session_id).first()
        if session:
            db.delete(session)
            db.commit()
            log_activity(session_id, "session_deleted")
            return True
        return False
    finally:
        db.close()


# Quiz Operations
def create_quiz(session_id: str) -> Quiz:
    """Create new quiz"""
    quiz_id = f"quiz_{uuid.uuid4()}"
    db = next(get_db())
    try:
        quiz = Quiz(quiz_id=quiz_id, session_id=session_id)
        db.add(quiz)
        db.commit()
        db.refresh(quiz)

        log_activity(session_id, "quiz_created", {"quiz_id": quiz_id})
        return quiz
    finally:
        db.close()


def get_quiz(quiz_id: str) -> Optional[Quiz]:
    """Get quiz by ID"""
    db = next(get_db())
    try:
        return db.query(Quiz).filter(Quiz.quiz_id == quiz_id).first()
    finally:
        db.close()


def get_quizzes_by_session(
    session_id: str, limit: int = 10, offset: int = 0
) -> List[Quiz]:
    """Get quizzes for session"""
    db = next(get_db())
    try:
        return (
            db.query(Quiz)
            .filter(Quiz.session_id == session_id)
            .order_by(desc(Quiz.created_at))
            .offset(offset)
            .limit(limit)
            .all()
        )
    finally:
        db.close()


def update_quiz_status(quiz_id: str, status: str):
    """Update quiz status"""
    db = next(get_db())
    try:
        quiz = db.query(Quiz).filter(Quiz.quiz_id == quiz_id).first()
        if quiz:
            quiz.status = status
            quiz.updated_at = datetime.now()
            db.commit()
    finally:
        db.close()


def update_quiz_collection(quiz_id: str, collection_name: str):
    """Update quiz collection name"""
    db = next(get_db())
    try:
        quiz = db.query(Quiz).filter(Quiz.quiz_id == quiz_id).first()
        if quiz:
            quiz.collection_name = collection_name
            quiz.updated_at = datetime.now()
            db.commit()
    finally:
        db.close()


# Document Operations
def create_document(
    quiz_id: str, filename: str, file_path: str, size_bytes: int, file_type: str
) -> Document:
    """Create document record"""
    doc_id = f"doc_{uuid.uuid4()}"
    db = next(get_db())
    try:
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
        return document
    finally:
        db.close()


def get_documents_by_quiz(quiz_id: str) -> List[Document]:
    """Get all documents for quiz"""
    db = next(get_db())
    try:
        return db.query(Document).filter(Document.quiz_id == quiz_id).all()
    finally:
        db.close()


def update_document_indexed(doc_id: str, indexed: bool):
    """Update document indexing status"""
    db = next(get_db())
    try:
        document = db.query(Document).filter(Document.doc_id == doc_id).first()
        if document:
            document.indexed = indexed
            db.commit()
    finally:
        db.close()


def delete_document(doc_id: str) -> bool:
    """Delete document"""
    db = next(get_db())
    try:
        document = db.query(Document).filter(Document.doc_id == doc_id).first()
        if document:
            db.delete(document)
            db.commit()
            return True
        return False
    finally:
        db.close()


# Topic Session Operations
def create_topic_session(quiz_id: str, desired_topic_count: int = 10) -> TopicSession:
    """Create topic selection session"""
    topic_session_id = f"topic_session_{uuid.uuid4()}"
    db = next(get_db())
    try:
        topic_session = TopicSession(
            topic_session_id=topic_session_id,
            quiz_id=quiz_id,
            desired_topic_count=desired_topic_count,
        )
        db.add(topic_session)
        db.commit()
        db.refresh(topic_session)
        return topic_session
    finally:
        db.close()


def get_topic_session(topic_session_id: str) -> Optional[TopicSession]:
    """Get topic session by ID"""
    db = next(get_db())
    try:
        return (
            db.query(TopicSession)
            .filter(TopicSession.topic_session_id == topic_session_id)
            .first()
        )
    finally:
        db.close()


def update_topic_session(topic_session_id: str, **kwargs):
    """Update topic session fields"""
    db = next(get_db())
    try:
        topic_session = (
            db.query(TopicSession)
            .filter(TopicSession.topic_session_id == topic_session_id)
            .first()
        )
        if topic_session:
            for key, value in kwargs.items():
                if hasattr(topic_session, key):
                    setattr(topic_session, key, value)
            topic_session.updated_at = datetime.now()
            db.commit()
    finally:
        db.close()


# Quiz Session Operations
def create_quiz_session(
    quiz_id: str, total_questions: int, difficulty: str
) -> QuizSession:
    """Create quiz execution session"""
    quiz_session_id = f"quiz_session_{uuid.uuid4()}"
    db = next(get_db())
    try:
        quiz_session = QuizSession(
            quiz_session_id=quiz_session_id,
            quiz_id=quiz_id,
            total_questions=total_questions,
            difficulty=difficulty,
        )
        db.add(quiz_session)
        db.commit()
        db.refresh(quiz_session)
        return quiz_session
    finally:
        db.close()


def get_quiz_session(quiz_session_id: str) -> Optional[QuizSession]:
    """Get quiz session by ID"""
    db = next(get_db())
    try:
        return (
            db.query(QuizSession)
            .filter(QuizSession.quiz_session_id == quiz_session_id)
            .first()
        )
    finally:
        db.close()


def update_quiz_session(quiz_session_id: str, **kwargs):
    """Update quiz session fields"""
    db = next(get_db())
    try:
        quiz_session = (
            db.query(QuizSession)
            .filter(QuizSession.quiz_session_id == quiz_session_id)
            .first()
        )
        if quiz_session:
            for key, value in kwargs.items():
                if hasattr(quiz_session, key):
                    setattr(quiz_session, key, value)
            quiz_session.updated_at = datetime.now()
            db.commit()
    finally:
        db.close()


# Activity Logging
def log_activity(
    session_id: str, action: str, details: Optional[Dict[str, Any]] = None
):
    """Log user activity"""
    db = next(get_db())
    try:
        activity = ActivityLog(
            session_id=session_id, action=action, details=details or {}
        )
        db.add(activity)
        db.commit()
    except Exception as e:
        logger.error(f"Failed to log activity: {e}")
    finally:
        db.close()


# Statistics
def get_system_stats() -> Dict[str, Any]:
    """Get system usage statistics"""
    db = next(get_db())
    try:
        total_quizzes = db.query(func.count(Quiz.quiz_id)).scalar()
        total_documents = db.query(func.count(Document.doc_id)).scalar()

        # Active sessions (activity in last 24h)
        cutoff = datetime.now() - timedelta(hours=24)
        active_sessions = (
            db.query(func.count(Session.session_id))
            .filter(Session.last_activity > cutoff)
            .scalar()
        )

        return {
            "total_quizzes": total_quizzes or 0,
            "total_documents": total_documents or 0,
            "total_questions_generated": 0,  # Could track this separately
            "active_sessions": active_sessions or 0,
        }
    finally:
        db.close()


def get_session_stats(session_id: str) -> Dict[str, Any]:
    """Get user session statistics"""
    db = next(get_db())
    try:
        quizzes_created = (
            db.query(func.count(Quiz.quiz_id))
            .filter(Quiz.session_id == session_id)
            .scalar()
        )

        documents_uploaded = (
            db.query(func.count(Document.doc_id))
            .join(Quiz)
            .filter(Quiz.session_id == session_id)
            .scalar()
        )

        return {
            "quizzes_created": quizzes_created or 0,
            "documents_uploaded": documents_uploaded or 0,
            "questions_answered": 0,  # Could track from quiz sessions
        }
    finally:
        db.close()
