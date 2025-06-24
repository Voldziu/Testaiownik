# src/Testaiownik/Backend/api/quiz.py
from fastapi import APIRouter, HTTPException, Request
from typing import List, Optional
import uuid
from datetime import datetime

from services.quiz_service import QuizService
from models.requests import (
    StartQuizRequest,
    AnswerQuestionRequest,
    QuizDifficultyRequest,
    QuizQuestionsRequest,
    UserQuestionsRequest,
)
from models.responses import (
    QuizResults,
    QuizCreateResponse,
    QuizListResponse,
    QuizListItem,
    SessionListResponse,
    SessionItem,
    SessionDetailResponse,
    SessionDeleteResponse,
    QuizStartResponse,
    QuizCurrentResponse,
    QuizAnswerResponse,
    QuizResultsResponse,
)
from database.crud import (
    create_quiz,
    get_quizzes_by_session,
    get_quiz,
    delete_session,
    log_activity,
)
from utils import logger

router = APIRouter()
quiz_service = QuizService()


def get_session_id(request: Request) -> str:
    """Extract session ID from request"""
    session_id = getattr(request.state, "session_id", None)
    if not session_id:
        raise HTTPException(status_code=401, detail="Session ID required")
    return session_id


@router.post("/quiz/create", response_model=QuizCreateResponse)
async def create_quiz_endpoint(request: Request):
    """Creates a new quiz instance and returns unique quiz ID"""
    session_id = get_session_id(request)

    try:
        quiz = create_quiz(session_id)

        return QuizCreateResponse(
            quiz_id=quiz.quiz_id, created_at=quiz.created_at, status=quiz.status
        )
    except Exception as e:
        logger.error(f"Failed to create quiz: {e}")
        raise HTTPException(status_code=500, detail="Failed to create quiz")


@router.get("/quiz/list", response_model=QuizListResponse)
async def list_quizzes(request: Request, limit: int = 10, offset: int = 0):
    """Lists all quizzes created by the user"""
    session_id = get_session_id(request)

    try:
        quizzes = get_quizzes_by_session(session_id, limit, offset)

        quiz_items = []
        for quiz in quizzes:
            # Get document and topic counts (simplified)
            quiz_items.append(
                QuizListItem(
                    quiz_id=quiz.quiz_id,
                    created_at=quiz.created_at,
                    status=quiz.status,
                    document_count=len(quiz.documents) if quiz.documents else 0,
                    topic_count=0,  # Would get from topic sessions
                )
            )

        return QuizListResponse(quizzes=quiz_items, total=len(quiz_items))
    except Exception as e:
        logger.error(f"Failed to list quizzes: {e}")
        raise HTTPException(status_code=500, detail="Failed to list quizzes")


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(request: Request):
    """Lists user's browser sessions with activity summary"""
    session_id = get_session_id(request)

    # For simplicity, just return current session
    # In practice, you might track multiple sessions per user
    return SessionListResponse(
        current_session=session_id,
        sessions=[
            SessionItem(
                session_id=session_id,
                created_at=datetime.now(),
                last_activity=datetime.now(),
                quiz_count=len(get_quizzes_by_session(session_id)),
            )
        ],
    )


@router.get("/sessions/{session_id}", response_model=SessionDetailResponse)
async def get_session_detail(session_id: str, request: Request):
    """Gets detailed information about specific browser session"""
    current_session_id = get_session_id(request)

    if session_id != current_session_id:
        raise HTTPException(status_code=403, detail="Access denied")

    quizzes = get_quizzes_by_session(session_id)

    return SessionDetailResponse(
        session_id=session_id,
        created_at=datetime.now(),
        last_activity=datetime.now(),
        quizzes=[quiz.quiz_id for quiz in quizzes],
        activity_log=[],  # Would implement proper activity tracking
    )


@router.delete("/sessions/{session_id}", response_model=SessionDeleteResponse)
async def delete_session_endpoint(session_id: str, request: Request):
    """Deletes browser session and all associated data"""
    current_session_id = get_session_id(request)

    if session_id != current_session_id:
        raise HTTPException(status_code=403, detail="Access denied")

    try:
        # Get quiz count before deletion
        quizzes = get_quizzes_by_session(session_id)
        quiz_count = len(quizzes)

        # Delete session and cascaded data
        success = delete_session(session_id)

        if success:
            return SessionDeleteResponse(
                message="Session deleted successfully", deleted_quizzes=quiz_count
            )
        else:
            raise HTTPException(status_code=404, detail="Session not found")

    except Exception as e:
        logger.error(f"Failed to delete session: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete session")


# Quiz Execution Endpoints


@router.post("/quiz/{quiz_id}/start", response_model=QuizStartResponse)
async def start_quiz(quiz_id: str, request_data: StartQuizRequest, request: Request):
    """Starts quiz execution with confirmed topics"""
    session_id = get_session_id(request)

    try:
        # Validate quiz exists and belongs to session
        quiz = get_quiz(quiz_id)
        if not quiz:
            raise HTTPException(status_code=404, detail="Quiz not found")
        if quiz.session_id != session_id:
            raise HTTPException(status_code=403, detail="Access denied")

        # Start quiz
        quiz_session_id = await quiz_service.start_quiz(
            quiz_id=quiz_id,
            confirmed_topics=request_data.confirmed_topics,
            total_questions=request_data.total_questions,
            difficulty=request_data.difficulty,
            user_questions=request_data.user_questions,
            session_id=session_id,
        )

        return QuizStartResponse(
            quiz_session_id=quiz_session_id,
            status="generating",
            estimated_generation_time=30,
            total_questions=request_data.total_questions,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start quiz: {e}")
        raise HTTPException(status_code=500, detail="Failed to start quiz")


@router.get("/quiz/session/{quiz_session_id}", response_model=QuizCurrentResponse)
async def get_current_question(quiz_session_id: str, request: Request):
    """Gets current question and quiz state"""
    session_id = get_session_id(request)

    try:
        current_data = quiz_service.get_current_question(quiz_session_id)

        if not current_data:
            raise HTTPException(status_code=404, detail="Quiz session not found")

        return QuizCurrentResponse(**current_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get current question: {e}")
        raise HTTPException(status_code=500, detail="Failed to get current question")


@router.post(
    "/quiz/session/{quiz_session_id}/answer", response_model=QuizAnswerResponse
)
async def submit_answer(
    quiz_session_id: str, answer_data: AnswerQuestionRequest, request: Request
):
    """Submits answer to current question"""
    session_id = get_session_id(request)

    try:
        result = await quiz_service.submit_answer(
            quiz_session_id=quiz_session_id,
            selected_choices=answer_data.selected_choices,
            question_id=answer_data.question_id,
            session_id=session_id,
        )

        return QuizAnswerResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to submit answer: {e}")
        raise HTTPException(status_code=500, detail="Failed to submit answer")


@router.get(
    "/quiz/session/{quiz_session_id}/results", response_model=QuizResultsResponse
)
async def get_quiz_results(quiz_session_id: str, request: Request):
    """Gets final quiz results and statistics"""
    session_id = get_session_id(request)

    try:
        # Implementation would get results from quiz service
        # This is a placeholder response
        return QuizResultsResponse(
            quiz_results=QuizResults(
                session_id=quiz_session_id,
                total_questions=20,
                correct_answers=16,
                score_percentage=80.0,
                topic_scores={},
                completed_at=datetime.now(),
            ),
            status="completed",
        )

    except Exception as e:
        logger.error(f"Failed to get quiz results: {e}")
        raise HTTPException(status_code=500, detail="Failed to get quiz results")


@router.get("/quiz/session/{quiz_session_id}/preview")
async def preview_quiz(quiz_session_id: str, request: Request):
    """Previews generated quiz before starting"""
    session_id = get_session_id(request)

    # Implementation would get preview from quiz service
    return {
        "quiz_preview": {
            "total_questions": 20,
            "difficulty": "medium",
            "topics": [],
            "estimated_duration_minutes": 25,
        },
        "ready_to_start": True,
    }


@router.post("/quiz/session/{quiz_session_id}/pause")
async def pause_quiz(quiz_session_id: str, request: Request):
    """Pauses active quiz session"""
    session_id = get_session_id(request)

    # Implementation would pause quiz in service
    return {
        "success": True,
        "status": "paused",
        "paused_at": datetime.now(),
        "progress_saved": True,
    }


@router.post("/quiz/session/{quiz_session_id}/resume")
async def resume_quiz(quiz_session_id: str, request: Request):
    """Resumes paused quiz session"""
    session_id = get_session_id(request)

    # Implementation would resume quiz in service
    return {
        "success": True,
        "status": "active",
        "resumed_at": datetime.now(),
        "current_question_restored": True,
    }


@router.post("/quiz/session/{quiz_session_id}/restart")
async def restart_quiz(quiz_session_id: str, request: Request):
    """Restarts quiz with same topics but new questions"""
    session_id = get_session_id(request)

    # Implementation would restart quiz in service
    new_session_id = f"quiz_session_{uuid.uuid4()}"
    return {
        "new_quiz_session_id": new_session_id,
        "regenerated_questions": True,
        "same_topics": True,
        "status": "ready",
    }


@router.get("/quiz/session/{quiz_session_id}/progress")
async def get_quiz_progress(quiz_session_id: str, request: Request):
    """Gets detailed progress statistics"""
    session_id = get_session_id(request)

    # Implementation would get progress from quiz service
    return {
        "progress": {
            "current_question": 8,
            "total_questions": 20,
            "answered": 7,
            "correct": 5,
            "score_percentage": 71.4,
            "time_elapsed_minutes": 12,
        },
        "topic_progress": {},
    }


@router.post("/quiz/session/{quiz_session_id}/difficulty")
async def change_difficulty(
    quiz_session_id: str, difficulty_data: QuizDifficultyRequest, request: Request
):
    """Changes quiz difficulty level"""
    session_id = get_session_id(request)

    # Implementation would update difficulty in service
    return {
        "success": True,
        "old_difficulty": "medium",
        "new_difficulty": difficulty_data.difficulty,
        "regeneration_required": True,
    }


@router.post("/quiz/session/{quiz_session_id}/questions-number")
async def change_questions_number(
    quiz_session_id: str, questions_data: QuizQuestionsRequest, request: Request
):
    """Changes total number of quiz questions"""
    session_id = get_session_id(request)

    # Implementation would update question count in service
    return {
        "success": True,
        "old_count": 20,
        "new_count": questions_data.total_questions,
        "additional_generation_required": True,
    }


@router.post("/quiz/session/{quiz_session_id}/user-questions")
async def add_user_questions(
    quiz_session_id: str, questions_data: UserQuestionsRequest, request: Request
):
    """Adds user-provided questions to quiz"""
    session_id = get_session_id(request)

    # Implementation would add user questions in service
    return {
        "success": True,
        "added_questions": len(questions_data.user_questions),
        "processed_questions": [],
        "total_questions_updated": 20 + len(questions_data.user_questions),
    }


@router.get("/quiz/explanation/{question_id}")
async def get_question_explanation(question_id: str, request: Request):
    """Gets explanation context from vector store for specific question"""
    session_id = get_session_id(request)

    # Implementation would get explanation from quiz service
    return {
        "question_id": question_id,
        "explanation": "Detailed explanation...",
        "source_chunks": [],
        "additional_context": "Related topics...",
    }
