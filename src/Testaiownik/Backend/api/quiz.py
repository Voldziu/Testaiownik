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
        total_questions = quiz.total_questions

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

    # Use provided topics or fall back to quiz's confirmed topics
    topics_to_use = request_data.confirmed_topics
    if topics_to_use is None:
        if not quiz.confirmed_topics:
            raise HTTPException(status_code=400, detail="No topics confirmed for quiz")
        topics_to_use = quiz.confirmed_topics

    # Validate we have topics
    if not topics_to_use:
        raise HTTPException(status_code=400, detail="No topics available for quiz")

    try:
        success = await quiz_service.start_quiz(
            quiz_id=quiz_id,
            confirmed_topics=topics_to_use,  # Use selected topics
            total_questions=request_data.total_questions,
            difficulty=request_data.difficulty,
            user_questions=request_data.user_questions or [],
            user_id=user_id,
            db=db,
        )

        if not success:
            raise HTTPException(status_code=500, detail="Failed to start quiz")

        return QuizStartResponse(
            quiz_id=quiz_id,
            status="generated",
            estimated_generation_time=30,
            total_questions=request_data.total_questions
            + len(request_data.user_questions or []),
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
        quiz_current_response = quiz_service.get_current_question(quiz_id, db)

        if not quiz_current_response:
            raise HTTPException(status_code=404, detail="No current question available")

        return quiz_current_response

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

    # Validate that the question_id matches the current question
    try:
        questions_data = quiz.questions_data
        if not questions_data or not questions_data.get("active_question_pool"):
            raise HTTPException(status_code=400, detail="No questions available")

        current_index = quiz.current_question_index
        active_pool = questions_data.get("active_question_pool", [])

        if current_index >= len(active_pool):
            raise HTTPException(status_code=400, detail="Quiz is completed")

        current_question_id = active_pool[current_index]

        if answer_data.question_id != current_question_id:
            raise HTTPException(
                status_code=400,
                detail=f"Can only answer current question. Expected: {current_question_id}, got: {answer_data.question_id}",
            )

        quiz_answer_response = await quiz_service.submit_answer(
            quiz_id=quiz_id,
            selected_choices=answer_data.selected_choices,
            question_id=answer_data.question_id,
            db=db,
        )

        return quiz_answer_response

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
        quiz_results = quiz_service.get_quiz_results(quiz_id, db)

        if not quiz_results:
            raise HTTPException(status_code=404, detail="Quiz results not found")

        return QuizResultsResponse(
            quiz_results=quiz_results,
            status=quiz_results.status,
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
        success = reset_quiz_execution(db, quiz_id)

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

    if quiz.status not in ["quiz_active", "paused", "quiz_completed"]:
        raise HTTPException(status_code=400, detail="Quiz has not started yet")

    try:

        questions_data = quiz.questions_data or {}
        all_questions = questions_data.get("all_generated_questions", [])
        user_answers = quiz.user_answers or []
        active_pool = questions_data.get("active_question_pool", [])

        total_attempts = len(user_answers)
        correct_attempts = sum(1 for answer in user_answers if answer.get("is_correct"))

        answered_unique_questions = set()
        correct_unique_questions = set()

        for answer in user_answers:
            question_id = answer.get("question_id")
            attempt_number = answer.get("attempt_number", 1)

            if attempt_number == 1:
                answered_unique_questions.add(question_id)
                if answer.get("is_correct"):
                    correct_unique_questions.add(question_id)

        # Basic progress stats
        total_unique_questions = len(set(active_pool))  # Total unique questions in pool
        unique_answered = len(answered_unique_questions)
        unique_correct = len(correct_unique_questions)
        remaining_unique = max(0, total_unique_questions - unique_answered)

        # Percentages based on attempts vs unique questions
        attempt_success_rate = (
            (correct_attempts / total_attempts * 100) if total_attempts > 0 else 0
        )
        unique_question_success_rate = (
            (unique_correct / unique_answered * 100) if unique_answered > 0 else 0
        )

        # Current position in the quiz
        current_position = min(quiz.current_question_index + 1, total_unique_questions)

        # Calculate topic progress
        topic_progress = {}
        if quiz.confirmed_topics and all_questions:
            # Create mappings
            question_to_topic = {q.get("id"): q.get("topic") for q in all_questions}

            for topic_data in quiz.confirmed_topics:
                topic_name = topic_data.get("topic", "Unknown")

                # Get all unique questions for this topic in active pool
                topic_questions_in_pool = [
                    q_id
                    for q_id in set(active_pool)
                    if question_to_topic.get(q_id) == topic_name
                ]

                # Count attempts and success for this topic
                topic_attempts = 0
                topic_correct_attempts = 0
                topic_unique_answered = set()
                topic_unique_correct = set()

                for answer in user_answers:
                    question_id = answer.get("question_id")
                    if question_id in topic_questions_in_pool:
                        topic_attempts += 1
                        if answer.get("is_correct"):
                            topic_correct_attempts += 1

                        # Track unique questions (first attempt only)
                        if answer.get("attempt_number", 1) == 1:
                            topic_unique_answered.add(question_id)
                            if answer.get("is_correct"):
                                topic_unique_correct.add(question_id)

                topic_total_unique = len(topic_questions_in_pool)
                topic_answered_unique = len(topic_unique_answered)
                topic_correct_unique = len(topic_unique_correct)

                topic_progress[topic_name] = {
                    # Unique question metrics
                    "unique_answered": topic_answered_unique,
                    "unique_correct": topic_correct_unique,
                    "total_unique": topic_total_unique,
                    "remaining_unique": max(
                        0, topic_total_unique - topic_answered_unique
                    ),
                    # All attempt metrics
                    "total_attempts": topic_attempts,
                    "correct_attempts": topic_correct_attempts,
                    # Success rates
                    "unique_success_rate": (
                        (topic_correct_unique / topic_answered_unique * 100)
                        if topic_answered_unique > 0
                        else 0
                    ),
                    "attempt_success_rate": (
                        (topic_correct_attempts / topic_attempts * 100)
                        if topic_attempts > 0
                        else 0
                    ),
                }

        # Timing calculations
        time_elapsed_seconds = 0
        if quiz.quiz_started_at:
            time_elapsed_seconds = int(
                (datetime.now() - quiz.quiz_started_at).total_seconds()
            )

        avg_time_per_attempt = (
            (time_elapsed_seconds / total_attempts) if total_attempts > 0 else 0
        )
        avg_time_per_unique = (
            (time_elapsed_seconds / unique_answered) if unique_answered > 0 else 0
        )

        return {
            "progress": {
                # Current position
                "current_question": current_position,
                "total_unique_questions": total_unique_questions,
                # Unique question progress
                "unique_answered": unique_answered,
                "unique_correct": unique_correct,
                "remaining_unique": remaining_unique,
                "unique_success_rate": round(unique_question_success_rate, 1),
                # All attempts progress
                "total_attempts": total_attempts,
                "correct_attempts": correct_attempts,
                "attempt_success_rate": round(attempt_success_rate, 1),
                # Timing
                "time_elapsed_seconds": time_elapsed_seconds,
                "average_time_per_attempt": round(avg_time_per_attempt, 1),
                "average_time_per_unique_question": round(avg_time_per_unique, 1),
                # Topic breakdown
                "topic_progress": topic_progress,
            },
            "status": quiz.status,
            "quiz_metadata": {
                "difficulty": quiz.difficulty,
                "total_questions_generated": len(all_questions),
                "recycling_enabled": True,
            },
        }

    except Exception as e:
        logger.error(f"Failed to get quiz progress: {e}")
        raise HTTPException(status_code=500, detail="Failed to get quiz progress")
