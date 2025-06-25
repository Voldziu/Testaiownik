# src/Testaiownik/Backend/api/quiz.py
from fastapi import APIRouter, HTTPException, Request
from typing import List, Optional
import uuid
from datetime import datetime

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
    delete_user,
    log_activity,
    update_quiz_status,
    reset_quiz_execution,
)
from utils import logger

router = APIRouter()
quiz_service = QuizService()
document_service = DocumentService()


def get_user_id(request: Request) -> str:
    """Extract user ID from request"""
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID required")
    return user_id


def validate_quiz_access(quiz_id: str, user_id: str):
    """Validate that quiz belongs to user"""
    quiz = get_quiz(quiz_id)
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    if quiz.user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return quiz


@router.post("/quiz/create", response_model=QuizCreateResponse)
async def create_quiz_endpoint(request: Request):
    """Creates a new quiz instance and returns unique quiz ID"""
    user_id = get_user_id(request)

    try:
        quiz = create_quiz(user_id)

        return QuizCreateResponse(
            quiz_id=quiz.quiz_id, created_at=quiz.created_at, status=quiz.status
        )
    except Exception as e:
        logger.error(f"Failed to create quiz: {e}")
        raise HTTPException(status_code=500, detail="Failed to create quiz")


@router.get("/quiz/list", response_model=QuizListResponse)
async def list_quizzes(request: Request, limit: int = 10, offset: int = 0):
    """Lists all quizzes created by the user"""
    user_id = get_user_id(request)

    try:
        quizzes = get_quizzes_by_user(user_id, limit, offset)

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


@router.get("/quiz/{quiz_id}/status")
async def get_quiz_status(quiz_id: str, request: Request):
    """Get detailed quiz status and progress"""
    user_id = get_user_id(request)
    quiz = validate_quiz_access(quiz_id, user_id)

    try:
        # Get documents and calculate status
        documents = document_service.get_quiz_documents(quiz_id)
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
@router.post("/quiz/{quiz_id}/start", response_model=QuizStartResponse)
async def start_quiz(quiz_id: str, request_data: StartQuizRequest, request: Request):
    """Starts quiz execution with confirmed topics"""
    user_id = get_user_id(request)
    quiz = validate_quiz_access(quiz_id, user_id)

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


@router.get("/quiz/{quiz_id}/current", response_model=QuizCurrentResponse)
async def get_current_question(quiz_id: str, request: Request):
    """Gets current question and quiz state"""
    user_id = get_user_id(request)
    quiz = validate_quiz_access(quiz_id, user_id)

    try:
        current_data = quiz_service.get_current_question(quiz_id)

        if not current_data:
            raise HTTPException(status_code=404, detail="No current question available")

        return QuizCurrentResponse(**current_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get current question: {e}")
        raise HTTPException(status_code=500, detail="Failed to get current question")


@router.post("/quiz/{quiz_id}/answer", response_model=QuizAnswerResponse)
async def submit_answer(
    quiz_id: str, answer_data: AnswerQuestionRequest, request: Request
):
    """Submits answer to current question"""
    user_id = get_user_id(request)
    quiz = validate_quiz_access(quiz_id, user_id)

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


@router.get("/quiz/{quiz_id}/results", response_model=QuizResultsResponse)
async def get_quiz_results(quiz_id: str, request: Request):
    """Gets final quiz results and statistics"""
    user_id = get_user_id(request)
    quiz = validate_quiz_access(quiz_id, user_id)

    if quiz.status != "quiz_completed":
        raise HTTPException(status_code=400, detail="Quiz is not completed yet")

    try:
        results = quiz_service.get_quiz_results(quiz_id)

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
@router.get("/quiz/{quiz_id}/preview")
async def preview_quiz(quiz_id: str, request: Request):
    """Previews generated quiz before starting"""
    user_id = get_user_id(request)
    quiz = validate_quiz_access(quiz_id, user_id)

    if quiz.status not in ["topic_ready", "quiz_active"]:
        raise HTTPException(
            status_code=400, detail="Quiz must have confirmed topics to preview"
        )

    try:
        preview_data = quiz_service.get_quiz_preview(quiz_id)

        return {
            "quiz_preview": preview_data,
            "ready_to_start": quiz.status == "topic_ready",
        }

    except Exception as e:
        logger.error(f"Failed to preview quiz: {e}")
        raise HTTPException(status_code=500, detail="Failed to preview quiz")


@router.post("/quiz/{quiz_id}/pause")
async def pause_quiz(quiz_id: str, request: Request):
    """Pauses active quiz"""
    user_id = get_user_id(request)
    quiz = validate_quiz_access(quiz_id, user_id)

    if quiz.status != "quiz_active":
        raise HTTPException(status_code=400, detail="Quiz is not active")

    try:
        success = quiz_service.pause_quiz(quiz_id)

        if not success:
            raise HTTPException(status_code=500, detail="Failed to pause quiz")

        log_activity(user_id, "quiz_paused", {"quiz_id": quiz_id})

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


@router.post("/quiz/{quiz_id}/resume")
async def resume_quiz(quiz_id: str, request: Request):
    """Resumes paused quiz"""
    user_id = get_user_id(request)
    quiz = validate_quiz_access(quiz_id, user_id)

    if quiz.status != "paused":
        raise HTTPException(status_code=400, detail="Quiz is not paused")

    try:
        success = quiz_service.resume_quiz(quiz_id)

        if not success:
            raise HTTPException(status_code=500, detail="Failed to resume quiz")

        log_activity(user_id, "quiz_resumed", {"quiz_id": quiz_id})

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


@router.post("/quiz/{quiz_id}/restart")
async def restart_quiz(quiz_id: str, request: Request):
    """Restarts quiz with same topics but new questions"""
    user_id = get_user_id(request)
    quiz = validate_quiz_access(quiz_id, user_id)

    try:
        # Reset quiz execution but keep topics
        success = reset_quiz_execution(quiz_id)

        if not success:
            raise HTTPException(status_code=500, detail="Failed to restart quiz")

        log_activity(user_id, "quiz_restarted", {"quiz_id": quiz_id})

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


@router.get("/quiz/{quiz_id}/progress")
async def get_quiz_progress(quiz_id: str, request: Request):
    """Gets detailed progress statistics"""
    user_id = get_user_id(request)
    quiz = validate_quiz_access(quiz_id, user_id)

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


# User Management Endpoints (simplified)
@router.get("/users", response_model=UserListResponse)
async def list_users(request: Request):
    """Lists user's quiz activity summary"""
    user_id = get_user_id(request)

    # For simplicity, just return current user info
    quizzes = get_quizzes_by_user(user_id)

    return UserListResponse(
        current_user=user_id,
        total_quizzes=len(quizzes),
    )


@router.delete("/users/{user_id}", response_model=UserDeleteResponse)
async def delete_user_endpoint(user_id: str, request: Request):
    """Deletes user and all associated data"""
    current_user_id = get_user_id(request)

    if user_id != current_user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    try:
        # Get quiz count before deletion
        quizzes = get_quizzes_by_user(user_id)
        quiz_count = len(quizzes)

        # Delete user and cascaded data
        success = delete_user(user_id)

        if success:
            return UserDeleteResponse(
                message="User deleted successfully", deleted_quizzes=quiz_count
            )
        else:
            raise HTTPException(status_code=404, detail="User not found")

    except Exception as e:
        logger.error(f"Failed to delete user: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete user")


# Quiz configuration endpoints
@router.post("/quiz/{quiz_id}/difficulty", response_model=BaseResponse)
async def change_quiz_difficulty(
    quiz_id: str, difficulty_data: QuizDifficultyRequest, request: Request
):
    """Changes quiz difficulty level"""
    user_id = get_user_id(request)
    quiz = validate_quiz_access(quiz_id, user_id)

    if quiz.status not in ["topic_ready", "quiz_active"]:
        raise HTTPException(
            status_code=400, detail="Cannot change difficulty at this stage"
        )

    try:
        from ..database.crud import update_quiz

        old_difficulty = quiz.difficulty
        update_quiz(quiz_id, difficulty=difficulty_data.difficulty)

        log_activity(
            user_id,
            "quiz_difficulty_changed",
            {
                "quiz_id": quiz_id,
                "old_difficulty": old_difficulty,
                "new_difficulty": difficulty_data.difficulty,
            },
        )

        return BaseResponse(
            success=True,
            old_difficulty=old_difficulty,
            new_difficulty=difficulty_data.difficulty,
            regeneration_required=quiz.status == "quiz_active",
        )

    except Exception as e:
        logger.error(f"Failed to change difficulty: {e}")
        raise HTTPException(status_code=500, detail="Failed to change difficulty")


@router.post("/quiz/{quiz_id}/questions-count", response_model=BaseResponse)
async def change_question_count(
    quiz_id: str, questions_data: QuizQuestionsRequest, request: Request
):
    """Changes total number of quiz questions"""
    user_id = get_user_id(request)
    quiz = validate_quiz_access(quiz_id, user_id)

    if quiz.status not in ["topic_ready", "quiz_active"]:
        raise HTTPException(
            status_code=400, detail="Cannot change question count at this stage"
        )

    try:
        from ..database.crud import update_quiz

        old_count = quiz.total_questions
        update_quiz(quiz_id, total_questions=questions_data.total_questions)

        log_activity(
            user_id,
            "quiz_questions_changed",
            {
                "quiz_id": quiz_id,
                "old_count": old_count,
                "new_count": questions_data.total_questions,
            },
        )

        return BaseResponse(
            success=True,
            old_count=old_count,
            new_count=questions_data.total_questions,
            additional_generation_required=questions_data.total_questions
            > (old_count or 0),
        )

    except Exception as e:
        logger.error(f"Failed to change question count: {e}")
        raise HTTPException(status_code=500, detail="Failed to change question count")
