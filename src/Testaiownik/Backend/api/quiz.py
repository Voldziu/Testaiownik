# src/Testaiownik/Backend/api/quiz.py
from fastapi import APIRouter, HTTPException, Request
from typing import List, Optional
import uuid
from datetime import datetime
from fastapi import Depends
from sqlalchemy.orm import Session

from ..services.quiz_service import QuizService
from ..services.document_service import DocumentService
from ..models.requests import (
    StartQuizRequest,
    AnswerQuestionRequest,
    QuizDifficultyRequest,
    QuizQuestionsRequest,
    UserQuestionsRequest,
)
from ..models.responses import (
    QuizResults,
    QuizCreateResponse,
    QuizListResponse,
    QuizListItem,
    QuizStartResponse,
    QuizCurrentResponse,
    QuizAnswerResponse,
    QuizResultsResponse,
    UserListResponse,
    UserDeleteResponse,
    BaseResponse,
)
from ..database.crud import (
    create_quiz,
    get_quizzes_by_user,
    get_quiz,
    log_activity,
    update_quiz_status,
    reset_quiz_execution,
)
from ..database.sql_database_connector import get_db

from .system import get_user_id, validate_quiz_access


from utils import logger

router = APIRouter()
quiz_service = QuizService()
document_service = DocumentService()


@router.post("/create", response_model=QuizCreateResponse)
async def create_quiz_endpoint(request: Request, db: Session = Depends(get_db)):
    """Creates a new quiz instance and returns unique quiz ID"""
    user_id = get_user_id(request)

    try:
        quiz = create_quiz(db, user_id)

        return QuizCreateResponse(
            quiz_id=quiz.quiz_id, created_at=quiz.created_at, status=quiz.status
        )
    except Exception as e:
        logger.error(f"Failed to create quiz: {e}")
        raise HTTPException(status_code=500, detail="Failed to create quiz")


@router.get("/list", response_model=QuizListResponse)
async def list_quizzes(
    request: Request, limit: int = 10, offset: int = 0, db: Session = Depends(get_db)
):
    """Lists all quizzes created by the user"""
    user_id = get_user_id(request)

    try:
        quizzes = get_quizzes_by_user(db, user_id, limit, offset)

        quiz_items = []
        for quiz in quizzes:
            # Count documents and topics (already included in dict)
            document_count = len(quiz.documents)
            topic_count = len(quiz.confirmed_topics or quiz.suggested_topics or [])

            quiz_items.append(
                QuizListItem(
                    quiz_id=quiz.quiz_id,
                    created_at=quiz.created_at,
                    status=quiz.status,
                    document_count=document_count,
                    topic_count=topic_count,
                )
            )

        return QuizListResponse(quizzes=quiz_items, total=len(quiz_items))
    except Exception as e:
        logger.error(f"Failed to list quizzes: {e}")
        raise HTTPException(status_code=500, detail="Failed to list quizzes")


@router.get("/{quiz_id}/status")
async def get_quiz_status(
    quiz_id: str, request: Request, db: Session = Depends(get_db)
):
    """Get detailed quiz status and progress"""
    user_id = get_user_id(request)
    quiz = validate_quiz_access(quiz_id, user_id, db)

    try:
        # Get documents and calculate status
        documents = document_service.get_quiz_documents(quiz_id, db)
        document_count = len(documents)
        indexed_docs = sum(1 for doc in documents if doc.indexed)

        # Count topics
        topic_count = len(quiz.confirmed_topics or quiz.suggested_topics or [])

        # Quiz progress
        answered_questions = len(quiz.user_answers or [])
        total_questions = quiz.total_questions or 0

        return {
            "quiz_id": quiz_id,
            "status": quiz.status,
            "created_at": quiz.created_at,
            "documents": {
                "total": document_count,
                "indexed": indexed_docs,
                "collection_name": quiz.collection_name,
            },
            "topics": {
                "count": topic_count,
                "confirmed": bool(quiz.confirmed_topics),
                "suggested_count": len(quiz.suggested_topics or []),
            },
            "quiz_execution": {
                "total_questions": total_questions,
                "answered": answered_questions,
                "current_index": quiz.current_question_index,
                "difficulty": quiz.difficulty,
                "progress_percentage": (
                    (answered_questions / total_questions * 100)
                    if total_questions > 0
                    else 0
                ),
            },
            "timestamps": {
                "created_at": quiz.created_at,
                "topic_analysis_started": quiz.topic_analysis_completed_at,
                "topic_analysis_completed": quiz.topic_analysis_completed_at,
                "quiz_started": quiz.quiz_started_at,
                "quiz_completed": quiz.quiz_completed_at,
            },
        }

    except Exception as e:
        logger.error(f"Failed to get quiz status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get quiz status")


# Quiz Execution Endpoints
@router.post("/{quiz_id}/start", response_model=QuizStartResponse)
async def start_quiz(
    quiz_id: str,
    request_data: StartQuizRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Starts quiz execution with confirmed topics"""
    user_id = get_user_id(request)
    quiz = validate_quiz_access(quiz_id, user_id, db)

    # Validate quiz is ready
    if quiz.status != "topic_ready":
        raise HTTPException(
            status_code=400,
            detail=f"Quiz is not ready to start. Current status: {quiz.status}",
        )

    if not quiz.confirmed_topics:
        raise HTTPException(status_code=400, detail="No topics confirmed for quiz")

    try:
        success = await quiz_service.start_quiz(
            quiz_id=quiz_id,
            confirmed_topics=quiz.confirmed_topics,
            total_questions=request_data.total_questions,
            difficulty=request_data.difficulty,
            user_questions=request_data.user_questions or [],
            user_id=user_id,
            db=db,
        )

        if not success:
            raise HTTPException(status_code=500, detail="Failed to start quiz")

        return QuizStartResponse(
            quiz_id=quiz_id,  # Using quiz_id consistently
            status="generating",
            estimated_generation_time=30,
            total_questions=request_data.total_questions,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start quiz: {e}")
        raise HTTPException(status_code=500, detail="Failed to start quiz")


@router.get("/{quiz_id}/current", response_model=QuizCurrentResponse)
async def get_current_question(
    quiz_id: str, request: Request, db: Session = Depends(get_db)
):
    """Gets current question and quiz state"""
    user_id = get_user_id(request)
    quiz = validate_quiz_access(quiz_id, user_id, db)

    try:
        current_data = quiz_service.get_current_question(quiz_id, db)

        if not current_data:
            raise HTTPException(status_code=404, detail="No current question available")

        return QuizCurrentResponse(**current_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get current question: {e}")
        raise HTTPException(status_code=500, detail="Failed to get current question")


@router.post("/{quiz_id}/answer", response_model=QuizAnswerResponse)
async def submit_answer(
    quiz_id: str,
    answer_data: AnswerQuestionRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Submits answer to current question"""
    user_id = get_user_id(request)
    quiz = validate_quiz_access(quiz_id, user_id, db)

    if quiz.status != "quiz_active":
        raise HTTPException(status_code=400, detail="Quiz is not active")

    try:
        result = await quiz_service.submit_answer(
            quiz_id=quiz_id,
            selected_choices=answer_data.selected_choices,
            question_id=answer_data.question_id,
        )

        return QuizAnswerResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to submit answer: {e}")
        raise HTTPException(status_code=500, detail="Failed to submit answer")


@router.get("/{quiz_id}/results", response_model=QuizResultsResponse)
async def get_quiz_results(
    quiz_id: str, request: Request, db: Session = Depends(get_db)
):
    """Gets final quiz results and statistics"""
    user_id = get_user_id(request)
    quiz = validate_quiz_access(quiz_id, user_id, db)

    if quiz.status != "quiz_completed":
        raise HTTPException(status_code=400, detail="Quiz is not completed yet")

    try:
        results = quiz_service.get_quiz_results(quiz_id, db)

        if not results:
            raise HTTPException(status_code=404, detail="Quiz results not found")

        return QuizResultsResponse(
            quiz_results=QuizResults(**results["quiz_results"]),
            status=results["status"],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get quiz results: {e}")
        raise HTTPException(status_code=500, detail="Failed to get quiz results")


# Quiz Management Endpoints
@router.get("/{quiz_id}/preview")
async def preview_quiz(quiz_id: str, request: Request, db: Session = Depends(get_db)):
    """Previews generated quiz before starting"""
    user_id = get_user_id(request)
    quiz = validate_quiz_access(quiz_id, user_id, db)

    if quiz.status not in ["topic_ready", "quiz_active"]:
        raise HTTPException(
            status_code=400, detail="Quiz must have confirmed topics to preview"
        )

    try:
        preview_data = quiz_service.get_quiz_preview(quiz_id, db)

        return {
            "quiz_preview": preview_data,
            "ready_to_start": quiz.status == "topic_ready",
        }

    except Exception as e:
        logger.error(f"Failed to preview quiz: {e}")
        raise HTTPException(status_code=500, detail="Failed to preview quiz")


@router.post("/{quiz_id}/pause")
async def pause_quiz(quiz_id: str, request: Request, db: Session = Depends(get_db)):
    """Pauses active quiz"""
    user_id = get_user_id(request)
    quiz = validate_quiz_access(quiz_id, user_id, db)

    if quiz.status != "quiz_active":
        raise HTTPException(status_code=400, detail="Quiz is not active")

    try:
        success = quiz_service.pause_quiz(quiz_id, db)

        if not success:
            raise HTTPException(status_code=500, detail="Failed to pause quiz")

        log_activity(db, user_id, "quiz_paused", {"quiz_id": quiz_id})

        return {
            "success": True,
            "status": "paused",
            "paused_at": datetime.now(),
            "progress_saved": True,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to pause quiz: {e}")
        raise HTTPException(status_code=500, detail="Failed to pause quiz")


@router.post("/{quiz_id}/resume")
async def resume_quiz(quiz_id: str, request: Request, db: Session = Depends(get_db)):
    """Resumes paused quiz"""
    user_id = get_user_id(request)
    quiz = validate_quiz_access(quiz_id, user_id, db)

    if quiz.status != "paused":
        raise HTTPException(status_code=400, detail="Quiz is not paused")

    try:
        success = quiz_service.resume_quiz(quiz_id, db)

        if not success:
            raise HTTPException(status_code=500, detail="Failed to resume quiz")

        log_activity(db, user_id, "quiz_resumed", {"quiz_id": quiz_id})

        return {
            "success": True,
            "status": "quiz_active",
            "resumed_at": datetime.now(),
            "current_question_restored": True,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to resume quiz: {e}")
        raise HTTPException(status_code=500, detail="Failed to resume quiz")


@router.post("/{quiz_id}/restart")
async def restart_quiz(quiz_id: str, request: Request, db: Session = Depends(get_db)):
    """Restarts quiz with same topics but new questions"""
    user_id = get_user_id(request)
    quiz = validate_quiz_access(quiz_id, user_id, db)

    try:
        # Reset quiz execution but keep topics
        success = reset_quiz_execution(quiz_id)

        if not success:
            raise HTTPException(status_code=500, detail="Failed to restart quiz")

        log_activity(db, user_id, "quiz_restarted", {"quiz_id": quiz_id})

        return {
            "quiz_id": quiz_id,  # Same quiz, no new ID needed
            "regenerated_questions": False,  # Will regenerate when started
            "same_topics": True,
            "status": "topic_ready",
            "message": "Quiz reset successfully. Start again to generate new questions.",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to restart quiz: {e}")
        raise HTTPException(status_code=500, detail="Failed to restart quiz")


@router.get("/{quiz_id}/progress")
async def get_quiz_progress(
    quiz_id: str, request: Request, db: Session = Depends(get_db)
):
    """Gets detailed progress statistics"""
    user_id = get_user_id(request)
    quiz = validate_quiz_access(quiz_id, user_id, db)

    try:
        if quiz.status not in [
            "quiz_active",
            "paused",
            "quiz_completed",
        ]:
            raise HTTPException(status_code=400, detail="Quiz has not started yet")

        # Calculate progress from quiz data
        total_questions = quiz.total_questions or 0
        answered = len(quiz.user_answers or [])

        # Calculate correct answers
        correct = 0
        for answer in quiz.user_answers or []:
            if isinstance(answer, dict) and answer.get("is_correct"):
                correct += 1

        remaining = max(0, total_questions - answered)
        score_percentage = (correct / answered * 100) if answered > 0 else 0

        # Calculate topic progress
        topic_progress = {}
        if quiz.confirmed_topics:
            for topic_data in quiz.confirmed_topics:
                topic_name = topic_data.get("topic", "Unknown")
                topic_progress[topic_name] = {
                    "answered": 0,
                    "correct": 0,
                    "total": 0,  # Would calculate from questions_data
                }

        # Calculate timing
        time_elapsed = 0
        if quiz.quiz_started_at:
            time_elapsed = (datetime.now() - quiz.quiz_started_at).total_seconds()

        avg_time_per_question = time_elapsed / answered if answered > 0 else 0

        return {
            "progress": {
                "total_questions": total_questions,
                "answered": answered,
                "correct": correct,
                "remaining": remaining,
                "score_percentage": round(score_percentage, 1),
                "time_elapsed_seconds": int(time_elapsed),
                "average_time_per_question": round(avg_time_per_question, 1),
                "topic_progress": topic_progress,
            },
            "status": quiz.status,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get quiz progress: {e}")
        raise HTTPException(status_code=500, detail="Failed to get quiz progress")
