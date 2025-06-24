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
    TopicCountRequest,
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
from ..database.crud import get_quiz, get_topic_session, log_activity
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


def validate_topic_session_access(topic_session_id: str, user_id: str):
    """Validate that topic session belongs to user"""
    topic_session = get_topic_session(topic_session_id)
    if not topic_session:
        raise HTTPException(status_code=404, detail="Topic session not found")

    # Check if the quiz belongs to the user
    quiz = get_quiz(topic_session.quiz_id)
    if not quiz or quiz.user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    return topic_session


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
    if not quiz.document_count or quiz.document_count == 0:
        raise HTTPException(status_code=400, detail="Quiz has no documents to analyze")

    try:
        topic_session_id = await topic_service.start_topic_analysis(
            quiz_id=quiz_id,
            desired_topic_count=analysis_request.desired_topic_count,
        )

        log_activity(
            user_id,
            "topic_analysis_started",
            {
                "quiz_id": quiz_id,
                "topic_session_id": topic_session_id,
                "desired_topic_count": analysis_request.desired_topic_count,
            },
        )

        return TopicAnalysisStartResponse(
            topic_session_id=topic_session_id,
            quiz_id=quiz_id,
            status="analyzing",
            estimated_completion=None,  # Could calculate based on document count
        )

    except Exception as e:
        logger.error(f"Failed to start topic analysis: {e}")
        raise HTTPException(status_code=500, detail="Failed to start topic analysis")


@router.get("/topics/{quiz_id}/status", response_model=TopicSessionStatusResponse)
async def get_topic_analysis_status(quiz_id: str, request: Request):
    """Gets current state of topic selection process"""
    user_id = get_user_id(request)
    validate_quiz_access(quiz_id, user_id)

    try:
        # Get the latest topic session for this quiz
        topic_session = topic_service.get_latest_topic_session(quiz_id)

        if not topic_session:
            raise HTTPException(
                status_code=404, detail="No topic analysis session found for this quiz"
            )

        # Verify user access to this topic session
        if topic_session.quiz_id != quiz_id:
            raise HTTPException(status_code=403, detail="Access denied")

        return TopicSessionStatusResponse(
            topic_session_id=topic_session.topic_session_id,
            quiz_id=quiz_id,
            status=topic_session.status,
            suggested_topics=topic_session.suggested_topics or [],
            feedback_request=topic_session.feedback_request,
            conversation_history=topic_session.conversation_history or [],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get topic analysis status: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to get topic analysis status"
        )


@router.post(
    "/topics/session/{topic_session_id}/feedback", response_model=TopicFeedbackResponse
)
async def submit_topic_feedback(
    topic_session_id: str, feedback_data: TopicFeedbackRequest, request: Request
):
    """Submits user feedback on suggested topics"""
    user_id = get_user_id(request)
    topic_session = validate_topic_session_access(topic_session_id, user_id)

    try:
        result = await topic_service.process_user_feedback(
            topic_session_id=topic_session_id,
            user_input=feedback_data.user_input,
        )

        log_activity(
            user_id,
            "topic_feedback_submitted",
            {
                "topic_session_id": topic_session_id,
                "feedback_type": result.get("action_taken", "unknown"),
            },
        )

        return TopicFeedbackResponse(**result)

    except Exception as e:
        logger.error(f"Failed to process topic feedback: {e}")
        raise HTTPException(status_code=500, detail="Failed to process feedback")


@router.post(
    "/topics/session/{topic_session_id}/confirm", response_model=TopicConfirmResponse
)
async def confirm_topics(topic_session_id: str, request: Request):
    """Confirms final topic selection and prepares for quiz"""
    user_id = get_user_id(request)
    topic_session = validate_topic_session_access(topic_session_id, user_id)

    if not topic_session.suggested_topics:
        raise HTTPException(status_code=400, detail="No topics available to confirm")

    try:
        confirmed_result = topic_service.confirm_topic_selection(topic_session_id)

        log_activity(
            user_id,
            "topics_confirmed",
            {
                "topic_session_id": topic_session_id,
                "quiz_id": topic_session.quiz_id,
                "topic_count": len(topic_session.suggested_topics),
            },
        )

        return TopicConfirmResponse(**confirmed_result)

    except Exception as e:
        logger.error(f"Failed to confirm topics: {e}")
        raise HTTPException(status_code=500, detail="Failed to confirm topics")


# Topic Management Endpoints
@router.delete(
    "/topics/{topic_session_id}/topic/{topic_name}", response_model=TopicDeleteResponse
)
async def delete_topic(topic_session_id: str, topic_name: str, request: Request):
    """Removes specific topic from suggestions. Reassign weights."""
    user_id = get_user_id(request)
    topic_session = validate_topic_session_access(topic_session_id, user_id)

    try:
        result = topic_service.delete_topic(topic_session_id, topic_name)

        log_activity(
            user_id,
            "topic_deleted",
            {"topic_session_id": topic_session_id, "deleted_topic": topic_name},
        )

        return TopicDeleteResponse(**result)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to delete topic: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete topic")


@router.post("/topics/{topic_session_id}/add", response_model=TopicAddResponse)
async def add_topic(
    topic_session_id: str, topic_data: AddTopicRequest, request: Request
):
    """Adds custom topic to suggestions. Reassign weights."""
    user_id = get_user_id(request)
    topic_session = validate_topic_session_access(topic_session_id, user_id)

    try:
        result = topic_service.add_topic(
            topic_session_id, topic_data.topic_name, topic_data.weight
        )

        log_activity(
            user_id,
            "topic_added",
            {
                "topic_session_id": topic_session_id,
                "added_topic": topic_data.topic_name,
            },
        )

        return TopicAddResponse(**result)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to add topic: {e}")
        raise HTTPException(status_code=500, detail="Failed to add topic")


@router.patch(
    "/topics/{topic_session_id}/topic/{topic_name}", response_model=TopicUpdateResponse
)
async def update_topic(
    topic_session_id: str,
    topic_name: str,
    update_data: UpdateTopicRequest,
    request: Request,
):
    """Renames topic and/or changes its weight. Reassign weights."""
    user_id = get_user_id(request)
    topic_session = validate_topic_session_access(topic_session_id, user_id)

    try:
        result = topic_service.update_topic(
            topic_session_id,
            topic_name,
            new_name=update_data.new_name,
            new_weight=update_data.new_weight,
        )

        log_activity(
            user_id,
            "topic_updated",
            {
                "topic_session_id": topic_session_id,
                "old_topic": topic_name,
                "new_topic": update_data.new_name or topic_name,
            },
        )

        return TopicUpdateResponse(**result)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update topic: {e}")
        raise HTTPException(status_code=500, detail="Failed to update topic")


@router.get(
    "/topics/{topic_session_id}/suggestions", response_model=TopicSuggestionsResponse
)
async def get_topic_suggestions(
    topic_session_id: str, request: Request, count: Optional[int] = 5
):
    """Gets AI-generated topic suggestions based on documents"""
    user_id = get_user_id(request)
    topic_session = validate_topic_session_access(topic_session_id, user_id)

    try:
        suggestions = await topic_service.generate_topic_suggestions(
            topic_session.quiz_id, count
        )

        return TopicSuggestionsResponse(
            suggestions=suggestions, total_suggestions=len(suggestions)
        )

    except Exception as e:
        logger.error(f"Failed to get topic suggestions: {e}")
        raise HTTPException(status_code=500, detail="Failed to get topic suggestions")


# Additional utility endpoints
@router.post("/topics/count", response_model=BaseResponse)
async def set_topic_count(count_data: TopicCountRequest, request: Request):
    """Sets desired number of topics for analysis"""
    user_id = get_user_id(request)
    topic_session = validate_topic_session_access(count_data.topic_session_id, user_id)

    try:
        result = topic_service.update_topic_count(
            count_data.topic_session_id, count_data.desired_count
        )

        log_activity(
            user_id,
            "topic_count_updated",
            {
                "topic_session_id": count_data.topic_session_id,
                "new_count": count_data.desired_count,
            },
        )

        return BaseResponse(**result)

    except Exception as e:
        logger.error(f"Failed to update topic count: {e}")
        raise HTTPException(status_code=500, detail="Failed to update topic count")


@router.post("/topics/{topic_session_id}/export")
async def export_topics(topic_session_id: str, request: Request):
    """Export current topic configuration for backup"""
    user_id = get_user_id(request)
    topic_session = validate_topic_session_access(topic_session_id, user_id)

    try:
        export_data = {
            "topic_session_id": topic_session_id,
            "quiz_id": topic_session.quiz_id,
            "suggested_topics": topic_session.suggested_topics,
            "desired_topic_count": topic_session.desired_topic_count,
            "status": topic_session.status,
            "exported_at": topic_session.updated_at.isoformat(),
        }

        return {
            "success": True,
            "export_data": export_data,
            "message": "Topics exported successfully",
        }

    except Exception as e:
        logger.error(f"Failed to export topics: {e}")
        raise HTTPException(status_code=500, detail="Failed to export topics")


@router.post("/topics/{topic_session_id}/import")
async def import_topics(topic_session_id: str, request: Request, topics_data: dict):
    """Import topics configuration from backup"""
    user_id = get_user_id(request)
    validate_topic_session_access(topic_session_id, user_id)

    # Validate imported data
    if "suggested_topics" not in topics_data:
        raise HTTPException(status_code=400, detail="Invalid topics data")

    topics = topics_data["suggested_topics"]
    if not topic_service.validate_topics(topics):
        raise HTTPException(status_code=400, detail="Invalid topic format or weights")

    try:
        from ..database.crud import update_topic_session

        update_topic_session(
            topic_session_id,
            suggested_topics=topics,
            desired_topic_count=topics_data.get("desired_topic_count", len(topics)),
        )

        log_activity(
            user_id,
            "topics_imported",
            {"topic_session_id": topic_session_id, "topic_count": len(topics)},
        )

        return {
            "success": True,
            "message": "Topics imported successfully",
            "imported_topics": len(topics),
        }

    except Exception as e:
        logger.error(f"Failed to import topics: {e}")
        raise HTTPException(status_code=500, detail="Failed to import topics")


@router.get("/topics/{topic_session_id}/validate")
async def validate_topics_endpoint(topic_session_id: str, request: Request):
    """Validate current topics configuration"""
    user_id = get_user_id(request)
    topic_session = validate_topic_session_access(topic_session_id, user_id)

    topics = topic_session.suggested_topics or []
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
