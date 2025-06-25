# src/Testaiownik/Backend/api/topics.py
from fastapi import APIRouter, HTTPException, Request
from typing import Optional

from ..services.quiz_service import QuizService
from ..services.topic_service import TopicService
from ..models.requests import (
    TopicAnalysisRequest,
    TopicFeedbackRequest,
    AddTopicRequest,
    UpdateTopicRequest,
)
from ..models.responses import (
    TopicAnalysisStartResponse,
    TopicSessionStatusResponse,
    TopicFeedbackResponse,
    TopicConfirmResponse,
    WeightedTopicResponse,
    TopicDeleteResponse,
    TopicUpdateResponse,
    TopicAddResponse,
    BaseResponse,
    TopicSuggestionsResponse,
)
from ..database.crud import get_quiz, log_activity
from utils import logger

router = APIRouter()
quiz_service = QuizService()
topic_service = TopicService()


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


@router.post("/topics/{quiz_id}/start", response_model=TopicAnalysisStartResponse)
async def start_topic_analysis(
    quiz_id: str,
    request: Request,
    analysis_request: TopicAnalysisRequest = TopicAnalysisRequest(),
):
    """Starts topic analysis process for quiz documents"""
    user_id = get_user_id(request)
    quiz = validate_quiz_access(quiz_id, user_id)

    # Check if quiz has documents
    if quiz.status not in ["documents_uploaded", "documents_indexed"]:
        raise HTTPException(
            status_code=400,
            detail="Quiz must have documents uploaded and indexed before topic analysis",
        )

    # Check if documents are indexed
    if not quiz.collection_name:
        raise HTTPException(
            status_code=400, detail="Documents must be indexed before topic analysis"
        )

    try:
        success = await quiz_service.start_topic_analysis(
            quiz_id=quiz_id,
            user_id=user_id,
            desired_topic_count=analysis_request.desired_topic_count,
        )

        if not success:
            raise HTTPException(
                status_code=500, detail="Failed to start topic analysis"
            )

        return TopicAnalysisStartResponse(
            quiz_id=quiz_id,  # Using quiz_id consistently
            status="analyzing",
            estimated_completion=None,
        )

    except Exception as e:
        logger.error(f"Failed to start topic analysis: {e}")
        raise HTTPException(status_code=500, detail="Failed to start topic analysis")


@router.get("/topics/{quiz_id}/status", response_model=TopicSessionStatusResponse)
async def get_topic_status(quiz_id: str, request: Request):
    """Gets current state of topic selection process"""
    user_id = get_user_id(request)
    quiz = validate_quiz_access(quiz_id, user_id)

    try:
        return TopicSessionStatusResponse(
            quiz_id=quiz_id,  # Using quiz_id consistently
            status=quiz.status,
            suggested_topics=[
                WeightedTopicResponse(**topic)
                for topic in (quiz.suggested_topics or [])
            ],
            feedback_request=quiz.topic_feedback_request,
            conversation_history=quiz.topic_conversation_history or [],
        )

    except Exception as e:
        logger.error(f"Failed to get topic status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get topic status")


@router.post("/topics/{quiz_id}/feedback", response_model=TopicFeedbackResponse)
async def submit_topic_feedback(
    quiz_id: str, feedback_data: TopicFeedbackRequest, request: Request
):
    """Submits user feedback on suggested topics"""
    user_id = get_user_id(request)
    quiz = validate_quiz_access(quiz_id, user_id)

    if quiz.status not in ["topic_analysis", "topic_feedback"]:
        raise HTTPException(
            status_code=400, detail="Quiz is not in topic selection phase"
        )

    try:
        result = await quiz_service.submit_topic_feedback(
            quiz_id=quiz_id,
            user_input=feedback_data.user_input,
            user_id=user_id,
        )

        return TopicFeedbackResponse(**result)

    except Exception as e:
        logger.error(f"Failed to submit topic feedback: {e}")
        raise HTTPException(status_code=500, detail="Failed to submit topic feedback")


@router.post("/topics/{quiz_id}/confirm", response_model=TopicConfirmResponse)
async def confirm_topics(quiz_id: str, request: Request):
    """Confirms final topic selection and prepares for quiz"""
    user_id = get_user_id(request)
    quiz = validate_quiz_access(quiz_id, user_id)

    if not quiz.suggested_topics:
        raise HTTPException(status_code=400, detail="No topics available to confirm")

    try:
        result = quiz_service.confirm_topics(quiz_id, user_id)

        return TopicConfirmResponse(**result)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to confirm topics: {e}")
        raise HTTPException(status_code=500, detail="Failed to confirm topics")


# Topic Management Endpoints
@router.delete(
    "/topics/{quiz_id}/topic/{topic_name}", response_model=TopicDeleteResponse
)
async def delete_topic(quiz_id: str, topic_name: str, request: Request):
    """Removes specific topic from suggestions"""
    user_id = get_user_id(request)
    quiz = validate_quiz_access(quiz_id, user_id)

    try:
        result = topic_service.delete_topic(
            quiz_id=quiz_id,
            topic_name=topic_name,
            user_id=user_id,
        )

        return TopicDeleteResponse(**result)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to delete topic: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete topic")


@router.post("/topics/{quiz_id}/add", response_model=TopicAddResponse)
async def add_topic(quiz_id: str, topic_data: AddTopicRequest, request: Request):
    """Adds custom topic to suggestions"""
    user_id = get_user_id(request)
    quiz = validate_quiz_access(quiz_id, user_id)

    try:
        result = topic_service.add_topic(
            quiz_id=quiz_id,
            topic_name=topic_data.topic_name,
            weight=topic_data.weight,
            user_id=user_id,
        )

        return TopicAddResponse(**result)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to add topic: {e}")
        raise HTTPException(status_code=500, detail="Failed to add topic")


@router.patch(
    "/topics/{quiz_id}/topic/{topic_name}", response_model=TopicUpdateResponse
)
async def update_topic(
    quiz_id: str,
    topic_name: str,
    update_data: UpdateTopicRequest,
    request: Request,
):
    """Renames topic and/or changes its weight"""
    user_id = get_user_id(request)
    quiz = validate_quiz_access(quiz_id, user_id)

    try:
        result = topic_service.update_topic(
            quiz_id=quiz_id,
            current_topic_name=topic_name,
            new_name=update_data.new_name,
            new_weight=update_data.new_weight,
            user_id=user_id,
        )

        return TopicUpdateResponse(**result)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update topic: {e}")
        raise HTTPException(status_code=500, detail="Failed to update topic")


@router.get("/topics/{quiz_id}/suggestions", response_model=TopicSuggestionsResponse)
async def get_topic_suggestions(
    quiz_id: str, request: Request, count: Optional[int] = 5
):
    """Gets AI-generated topic suggestions based on documents"""
    user_id = get_user_id(request)
    quiz = validate_quiz_access(quiz_id, user_id)

    try:
        suggestions = await topic_service.generate_topic_suggestions(quiz_id, count)

        return TopicSuggestionsResponse(
            suggestions=suggestions, total_suggestions=len(suggestions)
        )

    except Exception as e:
        logger.error(f"Failed to get topic suggestions: {e}")
        raise HTTPException(status_code=500, detail="Failed to get topic suggestions")


# Utility endpoints
@router.post("/topics/{quiz_id}/count", response_model=BaseResponse)
async def set_topic_count(quiz_id: str, request: Request, desired_count: int):
    """Sets desired number of topics for analysis"""
    user_id = get_user_id(request)
    quiz = validate_quiz_access(quiz_id, user_id)

    try:
        result = topic_service.set_topic_count(
            quiz_id=quiz_id,
            desired_count=desired_count,
            user_id=user_id,
        )

        return BaseResponse(**result)

    except Exception as e:
        logger.error(f"Failed to set topic count: {e}")
        raise HTTPException(status_code=500, detail="Failed to set topic count")


@router.post("/topics/{quiz_id}/reset")
async def reset_topics(quiz_id: str, request: Request):
    """Reset topic selection to start over"""
    user_id = get_user_id(request)
    quiz = validate_quiz_access(quiz_id, user_id)

    try:
        from ..database.crud import reset_quiz_to_topic_selection

        success = reset_quiz_to_topic_selection(quiz_id)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to reset topics")

        log_activity(
            user_id,
            "topics_reset",
            {"quiz_id": quiz_id},
        )

        return {
            "success": True,
            "message": "Topic selection reset successfully",
            "quiz_status": "documents_indexed",
        }

    except Exception as e:
        logger.error(f"Failed to reset topics: {e}")
        raise HTTPException(status_code=500, detail="Failed to reset topics")


@router.get("/topics/{quiz_id}/validate")
async def validate_topics_endpoint(quiz_id: str, request: Request):
    """Validate current topics configuration"""
    user_id = get_user_id(request)
    quiz = validate_quiz_access(quiz_id, user_id)

    topics = quiz.suggested_topics or []
    is_valid = topic_service.validate_topics(topics)

    issues = []
    if not is_valid:
        total_weight = sum(topic.get("weight", 0) for topic in topics)
        if abs(total_weight - 1.0) > 0.01:
            issues.append(f"Weights sum to {total_weight:.3f}, should be 1.0")

        for i, topic in enumerate(topics):
            if not topic.get("topic", "").strip():
                issues.append(f"Topic {i+1} has empty name")
            if topic.get("weight", 0) <= 0:
                issues.append(f"Topic '{topic.get('topic', '')}' has invalid weight")

    return {
        "valid": is_valid,
        "total_topics": len(topics),
        "total_weight": sum(topic.get("weight", 0) for topic in topics),
        "issues": issues,
        "can_proceed_to_quiz": is_valid and len(topics) > 0,
    }
