# src/Testaiownik/Backend/api/quiz.py
from fastapi import APIRouter, HTTPException, Request, Depends
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
    SessionItem,
    QuizCreateResponse,
    QuizListResponse,
    QuizListItem,
    QuizStartResponse,
    QuizCurrentResponse,
    QuizAnswerResponse,
    QuizResultsResponse,
    SessionListResponse,
    SessionDetailResponse,
    SessionDeleteResponse,
)
from ..database.crud import (
    create_quiz,
    get_quizzes_by_user,
    get_quiz,
    delete_user,
    log_activity,
)
from utils import logger

router = APIRouter()
quiz_service = QuizService()


def get_user_id(request: Request) -> str:
    """Extract user ID from request"""
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID required")
    return user_id


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


@router.get("/users", response_model=SessionListResponse)
async def list_users(request: Request):
    """Lists user's browser sessions with activity summary"""
    user_id = get_user_id(request)

    # For simplicity, just return current user
    # In practice, you might track multiple sessions per user
    return SessionListResponse(
        current_session=user_id,
        sessions=[
            SessionItem(
                session_id=user_id,
                created_at=datetime.now(),
                last_activity=datetime.now(),
                quiz_count=len(get_quizzes_by_user(user_id)),
            )
        ],
    )


@router.get("/users/{user_id}", response_model=SessionDetailResponse)
async def get_user_detail(user_id: str, request: Request):
    """Gets detailed information about specific user"""
    current_user_id = get_user_id(request)

    if user_id != current_user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    quizzes = get_quizzes_by_user(user_id)

    return SessionDetailResponse(
        session_id=user_id,
        created_at=datetime.now(),
        last_activity=datetime.now(),
        quizzes=[quiz.quiz_id for quiz in quizzes],
        activity_log=[],  # Would implement proper activity tracking
    )


@router.delete("/users/{user_id}", response_model=SessionDeleteResponse)
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
            return SessionDeleteResponse(
                message="User deleted successfully", deleted_quizzes=quiz_count
            )
        else:
            raise HTTPException(status_code=404, detail="User not found")

    except Exception as e:
        logger.error(f"Failed to delete user: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete user")


# Quiz Execution Endpoints


@router.post("/quiz/{quiz_id}/start", response_model=QuizStartResponse)
async def start_quiz(quiz_id: str, request_data: StartQuizRequest, request: Request):
    """Starts quiz execution with confirmed topics"""
    user_id = get_user_id(request)

    try:
        # Validate quiz exists and belongs to user
        quiz = get_quiz(quiz_id)
        if not quiz:
            raise HTTPException(status_code=404, detail="Quiz not found")
        if quiz.user_id != user_id:
            raise HTTPException(status_code=403, detail="Access denied")

        # Start quiz
        quiz_session_id = await quiz_service.start_quiz(
            quiz_id=quiz_id,
            confirmed_topics=request_data.confirmed_topics,
            total_questions=request_data.total_questions,
            difficulty=request_data.difficulty,
            user_questions=request_data.user_questions,
            session_id=user_id,
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
    user_id = get_user_id(request)

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
    user_id = get_user_id(request)

    try:
        result = await quiz_service.submit_answer(
            quiz_session_id=quiz_session_id,
            selected_choices=answer_data.selected_choices,
            question_id=answer_data.question_id,
            session_id=user_id,
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
    user_id = get_user_id(request)

    try:
        quiz_session = quiz_service.get_quiz_session(quiz_session_id)
        if not quiz_session:
            raise HTTPException(status_code=404, detail="Quiz session not found")

        # Verify user access
        from ..database.crud import get_quiz

        quiz = get_quiz(quiz_session.quiz_id)
        if not quiz or quiz.user_id != user_id:
            raise HTTPException(status_code=403, detail="Access denied")

        if quiz_session.status != "completed":
            raise HTTPException(status_code=400, detail="Quiz not completed yet")

        # Calculate results from stored data
        questions_data = quiz_session.questions_data or {}
        user_answers = questions_data.get("user_answers", [])

        # Filter to first attempts only for scoring
        first_attempts = [a for a in user_answers if a.get("attempt_number", 1) == 1]
        correct_answers = [a for a in first_attempts if a.get("is_correct", False)]

        total_questions = len(first_attempts)
        correct_count = len(correct_answers)
        score_percentage = (correct_count / max(total_questions, 1)) * 100

        # Calculate topic-wise scores
        topic_scores = {}
        all_questions = questions_data.get("all_generated_questions", [])
        question_topics = {
            q.get("id"): q.get("topic", "Unknown") for q in all_questions
        }

        for answer in first_attempts:
            question_id = answer.get("question_id")
            topic = question_topics.get(question_id, "Unknown")

            if topic not in topic_scores:
                topic_scores[topic] = {"correct": 0, "total": 0}

            topic_scores[topic]["total"] += 1
            if answer.get("is_correct", False):
                topic_scores[topic]["correct"] += 1

        # Add percentages
        for topic_data in topic_scores.values():
            total = topic_data["total"]
            topic_data["percentage"] = (topic_data["correct"] / max(total, 1)) * 100

        quiz_results = QuizResults(
            session_id=quiz_session_id,
            total_questions=total_questions,
            correct_answers=correct_count,
            score_percentage=score_percentage,
            topic_scores=topic_scores,
            completed_at=quiz_session.completed_at or datetime.now(),
        )

        return QuizResultsResponse(quiz_results=quiz_results, status="completed")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get quiz results: {e}")
        raise HTTPException(status_code=500, detail="Failed to get quiz results")


@router.get("/quiz/session/{quiz_session_id}/preview")
async def preview_quiz(quiz_session_id: str, request: Request):
    """Previews generated quiz before starting"""
    user_id = get_user_id(request)

    try:
        quiz_session = quiz_service.get_quiz_session(quiz_session_id)
        if not quiz_session:
            raise HTTPException(status_code=404, detail="Quiz session not found")

        # Verify access
        from ..database.crud import get_quiz

        quiz = get_quiz(quiz_session.quiz_id)
        if not quiz or quiz.user_id != user_id:
            raise HTTPException(status_code=403, detail="Access denied")

        questions_data = quiz_session.questions_data or {}
        all_questions = questions_data.get("all_generated_questions", [])

        # Count questions by topic
        topic_counts = {}
        for question in all_questions:
            topic = question.get("topic", "Unknown")
            topic_counts[topic] = topic_counts.get(topic, 0) + 1

        topics_list = [
            {"topic": topic, "question_count": count}
            for topic, count in topic_counts.items()
        ]

        # Estimate duration (assume 1.5 minutes per question)
        estimated_duration = len(all_questions) * 1.5

        return {
            "quiz_preview": {
                "total_questions": len(all_questions),
                "difficulty": quiz_session.difficulty,
                "topics": topics_list,
                "estimated_duration_minutes": int(estimated_duration),
            },
            "ready_to_start": quiz_session.status in ["active", "generating"],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to preview quiz: {e}")
        raise HTTPException(status_code=500, detail="Failed to preview quiz")


@router.post("/quiz/session/{quiz_session_id}/pause")
async def pause_quiz(quiz_session_id: str, request: Request):
    """Pauses active quiz session"""
    user_id = get_user_id(request)

    try:
        quiz_session = quiz_service.get_quiz_session(quiz_session_id)
        if not quiz_session:
            raise HTTPException(status_code=404, detail="Quiz session not found")

        # Verify access
        from ..database.crud import get_quiz

        quiz = get_quiz(quiz_session.quiz_id)
        if not quiz or quiz.user_id != user_id:
            raise HTTPException(status_code=403, detail="Access denied")

        if quiz_session.status != "active":
            raise HTTPException(status_code=400, detail="Quiz is not active")

        # Update status to paused
        from ..database.crud import update_quiz_session

        update_quiz_session(quiz_session_id, status="paused")

        log_activity(user_id, "quiz_paused", {"quiz_session_id": quiz_session_id})

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


@router.post("/quiz/session/{quiz_session_id}/resume")
async def resume_quiz(quiz_session_id: str, request: Request):
    """Resumes paused quiz session"""
    user_id = get_user_id(request)

    try:
        quiz_session = quiz_service.get_quiz_session(quiz_session_id)
        if not quiz_session:
            raise HTTPException(status_code=404, detail="Quiz session not found")

        # Verify access
        from ..database.crud import get_quiz

        quiz = get_quiz(quiz_session.quiz_id)
        if not quiz or quiz.user_id != user_id:
            raise HTTPException(status_code=403, detail="Access denied")

        if quiz_session.status != "paused":
            raise HTTPException(status_code=400, detail="Quiz is not paused")

        # Restore session and resume
        quiz_service._restore_quiz_session(quiz_session_id)

        # Update status to active
        from ..database.crud import update_quiz_session

        update_quiz_session(quiz_session_id, status="active")

        log_activity(user_id, "quiz_resumed", {"quiz_session_id": quiz_session_id})

        return {
            "success": True,
            "status": "active",
            "resumed_at": datetime.now(),
            "current_question_restored": True,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to resume quiz: {e}")
        raise HTTPException(status_code=500, detail="Failed to resume quiz")


@router.post("/quiz/session/{quiz_session_id}/restart")
async def restart_quiz(quiz_session_id: str, request: Request):
    """Restarts quiz with same topics but new questions"""
    user_id = get_user_id(request)

    try:
        quiz_session = quiz_service.get_quiz_session(quiz_session_id)
        if not quiz_session:
            raise HTTPException(status_code=404, detail="Quiz session not found")

        # Verify access
        from ..database.crud import get_quiz

        quiz = get_quiz(quiz_session.quiz_id)
        if not quiz or quiz.user_id != user_id:
            raise HTTPException(status_code=403, detail="Access denied")

        # Get original quiz configuration
        questions_data = quiz_session.questions_data or {}
        topics = questions_data.get("topics", [])

        if not topics:
            raise HTTPException(
                status_code=400, detail="No topics found to restart quiz"
            )

        # Create new quiz session with same configuration
        new_quiz_session_id = await quiz_service.start_quiz(
            quiz_id=quiz_session.quiz_id,
            confirmed_topics=topics,
            total_questions=quiz_session.total_questions,
            difficulty=quiz_session.difficulty,
            user_questions=[],  # Could preserve user questions if needed
            session_id=user_id,
        )

        log_activity(
            user_id,
            "quiz_restarted",
            {
                "old_quiz_session_id": quiz_session_id,
                "new_quiz_session_id": new_quiz_session_id,
            },
        )

        return {
            "new_quiz_session_id": new_quiz_session_id,
            "regenerated_questions": True,
            "same_topics": True,
            "status": "generating",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to restart quiz: {e}")
        raise HTTPException(status_code=500, detail="Failed to restart quiz")


@router.get("/quiz/session/{quiz_session_id}/progress")
async def get_quiz_progress(quiz_session_id: str, request: Request):
    """Gets detailed progress statistics"""
    user_id = get_user_id(request)

    try:
        quiz_session = quiz_service.get_quiz_session(quiz_session_id)
        if not quiz_session:
            raise HTTPException(status_code=404, detail="Quiz session not found")

        # Verify access
        from ..database.crud import get_quiz

        quiz = get_quiz(quiz_session.quiz_id)
        if not quiz or quiz.user_id != user_id:
            raise HTTPException(status_code=403, detail="Access denied")

        questions_data = quiz_session.questions_data or {}
        user_answers = questions_data.get("user_answers", [])
        all_questions = questions_data.get("all_generated_questions", [])

        # Calculate overall progress
        first_attempts = [a for a in user_answers if a.get("attempt_number", 1) == 1]
        correct_first = [a for a in first_attempts if a.get("is_correct", False)]

        current_index = quiz_session.current_question_index
        total_questions = len(all_questions)

        progress = {
            "current_question": (
                current_index + 1
                if current_index < total_questions
                else total_questions
            ),
            "total_questions": total_questions,
            "answered": len(first_attempts),
            "correct": len(correct_first),
            "score_percentage": (
                (len(correct_first) / max(len(first_attempts), 1)) * 100
                if first_attempts
                else 0
            ),
            "time_elapsed_minutes": 0,  # Would need to track start time
            "estimated_remaining_minutes": max(
                0, (total_questions - len(first_attempts)) * 1.5
            ),
        }

        # Calculate topic-wise progress
        topic_progress = {}
        question_topics = {
            q.get("id"): q.get("topic", "Unknown") for q in all_questions
        }

        for answer in first_attempts:
            question_id = answer.get("question_id")
            topic = question_topics.get(question_id, "Unknown")

            if topic not in topic_progress:
                topic_progress[topic] = {"answered": 0, "correct": 0, "remaining": 0}

            topic_progress[topic]["answered"] += 1
            if answer.get("is_correct", False):
                topic_progress[topic]["correct"] += 1

        # Calculate remaining questions per topic
        for question in all_questions:
            topic = question.get("topic", "Unknown")
            if topic not in topic_progress:
                topic_progress[topic] = {"answered": 0, "correct": 0, "remaining": 0}

        answered_questions = {a.get("question_id") for a in first_attempts}
        for question in all_questions:
            if question.get("id") not in answered_questions:
                topic = question.get("topic", "Unknown")
                topic_progress[topic]["remaining"] += 1

        return {"progress": progress, "topic_progress": topic_progress}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get quiz progress: {e}")
        raise HTTPException(status_code=500, detail="Failed to get quiz progress")


@router.post("/quiz/session/{quiz_session_id}/difficulty")
async def change_difficulty(
    quiz_session_id: str, difficulty_data: QuizDifficultyRequest, request: Request
):
    """Changes quiz difficulty level"""
    user_id = get_user_id(request)

    try:
        quiz_session = quiz_service.get_quiz_session(quiz_session_id)
        if not quiz_session:
            raise HTTPException(status_code=404, detail="Quiz session not found")

        # Verify access
        from ..database.crud import get_quiz

        quiz = get_quiz(quiz_session.quiz_id)
        if not quiz or quiz.user_id != user_id:
            raise HTTPException(status_code=403, detail="Access denied")

        if quiz_session.status == "completed":
            raise HTTPException(
                status_code=400, detail="Cannot change difficulty of completed quiz"
            )

        old_difficulty = quiz_session.difficulty

        # Update difficulty in database
        from ..database.crud import update_quiz_session

        update_quiz_session(quiz_session_id, difficulty=difficulty_data.difficulty)

        log_activity(
            user_id,
            "quiz_difficulty_changed",
            {
                "quiz_session_id": quiz_session_id,
                "old_difficulty": old_difficulty,
                "new_difficulty": difficulty_data.difficulty,
            },
        )

        # Determine if regeneration is needed
        regeneration_required = quiz_session.status in ["active", "generating"]

        return {
            "success": True,
            "old_difficulty": old_difficulty,
            "new_difficulty": difficulty_data.difficulty,
            "regeneration_required": regeneration_required,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to change difficulty: {e}")
        raise HTTPException(status_code=500, detail="Failed to change difficulty")


@router.post("/quiz/session/{quiz_session_id}/user-questions")
async def add_user_questions(
    quiz_session_id: str, questions_data: UserQuestionsRequest, request: Request
):
    """Adds user-provided questions to quiz"""
    user_id = get_user_id(request)

    try:
        quiz_session = quiz_service.get_quiz_session(quiz_session_id)
        if not quiz_session:
            raise HTTPException(status_code=404, detail="Quiz session not found")

        # Verify access
        from ..database.crud import get_quiz

        quiz = get_quiz(quiz_session.quiz_id)
        if not quiz or quiz.user_id != user_id:
            raise HTTPException(status_code=403, detail="Access denied")

        if quiz_session.status == "completed":
            raise HTTPException(
                status_code=400, detail="Cannot add questions to completed quiz"
            )

        # Process user questions using the quiz service
        # This would need to be implemented in quiz_service to process user questions
        processed_questions = []

        for i, question_text in enumerate(questions_data.user_questions):
            processed_questions.append(
                {
                    "original": question_text,
                    "processed": True,
                    "assigned_topic": "User Provided",  # Could use LLM to categorize
                    "question_id": f"user_q_{i+1}",
                }
            )

        # Store user questions in session data
        current_data = quiz_session.questions_data or {}
        current_data["user_questions"] = questions_data.user_questions

        from ..database.crud import update_quiz_session

        update_quiz_session(quiz_session_id, questions_data=current_data)

        log_activity(
            user_id,
            "user_questions_added",
            {
                "quiz_session_id": quiz_session_id,
                "question_count": len(questions_data.user_questions),
            },
        )

        # Calculate new total
        existing_questions = len(current_data.get("all_generated_questions", []))
        total_questions_updated = existing_questions + len(
            questions_data.user_questions
        )

        return {
            "success": True,
            "added_questions": len(questions_data.user_questions),
            "processed_questions": processed_questions,
            "total_questions_updated": total_questions_updated,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add user questions: {e}")
        raise HTTPException(status_code=500, detail="Failed to add user questions")


@router.get("/quiz/explanation/{question_id}")
async def get_question_explanation(question_id: str, request: Request):
    """Gets explanation context from vector store for specific question"""
    user_id = get_user_id(request)

    try:
        # Find the quiz session containing this question
        # This is a simplified approach - in practice, you might want to index questions
        from ..database.crud import get_quizzes_by_user

        quizzes = get_quizzes_by_user(user_id)

        found_question = None
        source_quiz_id = None

        for quiz in quizzes:
            quiz_sessions = quiz.quiz_sessions
            for quiz_session in quiz_sessions:
                questions_data = quiz_session.questions_data or {}
                all_questions = questions_data.get("all_generated_questions", [])

                for question in all_questions:
                    if question.get("id") == question_id:
                        found_question = question
                        source_quiz_id = quiz.quiz_id
                        break

                if found_question:
                    break
            if found_question:
                break

        if not found_question:
            raise HTTPException(status_code=404, detail="Question not found")

        # Get explanation from question data
        explanation = found_question.get("explanation", "No explanation available")

        # Get source chunks from vector search if available
        source_chunks = []
        if source_quiz_id:
            quiz = get_quiz(source_quiz_id)
            if quiz and quiz.collection_name:
                try:
                    document_service = DocumentService()
                    search_result = document_service.search_documents(
                        query=found_question.get("question_text", ""),
                        quiz_id=source_quiz_id,
                        limit=3,
                    )
                    source_chunks = search_result.get("results", [])
                except Exception as e:
                    logger.error(f"Failed to get source chunks: {e}")

        return {
            "question_id": question_id,
            "explanation": explanation,
            "source_chunks": source_chunks,
            "additional_context": f"Topic: {found_question.get('topic', 'Unknown')}, Difficulty: {found_question.get('difficulty', 'unknown')}",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get question explanation: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to get question explanation"
        )
