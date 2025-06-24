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
from models.responses import (
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


def get_session_id(request: Request) -> str:
    """Extract session ID from request"""
    session_id = getattr(request.state, "session_id", None)
    if not session_id:
        raise HTTPException(status_code=401, detail="Session ID required")
    return session_id


def validate_quiz_access(quiz_id: str, session_id: str):
    """Validate that quiz belongs to session"""
    quiz = get_quiz(quiz_id)
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    if quiz.session_id != session_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return quiz


def validate_topic_session_access(topic_session_id: str, session_id: str):
    """Validate that topic session belongs to session"""
    topic_session = get_topic_session(topic_session_id)
    if not topic_session:
        raise HTTPException(status_code=404, detail="Topic session not found")

    # Check if the quiz belongs to the session
    quiz = get_quiz(topic_session.quiz_id)
    if not quiz or quiz.session_id != session_id:
        raise HTTPException(status_code=403, detail="Access denied")

    return topic_session


@router.post("/topics/{quiz_id}/start", response_model=TopicAnalysisStartResponse)
async def start_topic_analysis(
    quiz_id: str,
    request: Request,
    analysis_request: TopicAnalysisRequest = TopicAnalysisRequest(),
):
    """Starts topic analysis process for quiz documents"""
    session_id = get_session_id(request)
    quiz = validate_quiz_access(quiz_id, session_id)

    # Check if quiz has documents
    if not quiz.documents:
        raise HTTPException(status_code=400, detail="Quiz has no documents to analyze")

    # Check if documents are indexed
    if not quiz.collection_name:
        raise HTTPException(
            status_code=400, detail="Documents must be indexed before topic analysis"
        )

    try:
        topic_session_id = await quiz_service.start_topic_analysis(
            quiz_id=quiz_id,
            session_id=session_id,
            desired_topic_count=analysis_request.desired_topic_count,
            batch_size=analysis_request.batch_size,
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


@router.get(
    "/topics/session/{topic_session_id}", response_model=TopicSessionStatusResponse
)
async def get_topic_session_status(topic_session_id: str, request: Request):
    """Gets current state of topic selection process"""
    session_id = get_session_id(request)
    validate_topic_session_access(topic_session_id, session_id)

    try:
        status_data = quiz_service.get_topic_session_status(topic_session_id)

        if not status_data:
            raise HTTPException(status_code=404, detail="Topic session not found")

        return TopicSessionStatusResponse(
            topic_session_id=status_data["topic_session_id"],
            status=status_data["status"],
            suggested_topics=[
                WeightedTopicResponse(**topic)
                for topic in status_data["suggested_topics"]
            ],
            feedback_request=status_data["feedback_request"],
            conversation_history=status_data["conversation_history"],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get topic session status: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to get topic session status"
        )


@router.post(
    "/topics/session/{topic_session_id}/feedback", response_model=TopicFeedbackResponse
)
async def submit_topic_feedback(
    topic_session_id: str, feedback_request: TopicFeedbackRequest, request: Request
):
    """Submits user feedback on suggested topics"""
    session_id = get_session_id(request)
    validate_topic_session_access(topic_session_id, session_id)

    try:
        result = await quiz_service.submit_topic_feedback(
            topic_session_id=topic_session_id,
            user_input=feedback_request.user_input,
            session_id=session_id,
        )

        return TopicFeedbackResponse(**result)

    except Exception as e:
        logger.error(f"Failed to submit topic feedback: {e}")
        raise HTTPException(status_code=500, detail="Failed to submit topic feedback")


@router.post(
    "/topics/session/{topic_session_id}/confirm", response_model=TopicConfirmResponse
)
async def confirm_topics(topic_session_id: str, request: Request):
    """Confirms final topic selection and prepares for quiz"""
    session_id = get_session_id(request)
    validate_topic_session_access(topic_session_id, session_id)

    try:
        result = quiz_service.confirm_topics(topic_session_id, session_id)

        return TopicConfirmResponse(
            confirmed_topics=[
                WeightedTopicResponse(**topic) for topic in result["confirmed_topics"]
            ],
            total_topics=result["total_topics"],
            ready_for_quiz=result["ready_for_quiz"],
            quiz_id=result["quiz_id"],
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to confirm topics: {e}")
        raise HTTPException(status_code=500, detail="Failed to confirm topics")


# Topic Management Endpoints


@router.post("/topics/count", response_model=BaseResponse)
async def set_topic_count(count_request: TopicCountRequest, request: Request):
    """Sets desired number of topics for analysis"""
    session_id = get_session_id(request)
    validate_topic_session_access(count_request.topic_session_id, session_id)

    try:
        result = topic_service.set_topic_count(
            topic_session_id=count_request.topic_session_id,
            desired_count=count_request.desired_count,
            session_id=session_id,
        )

        return BaseResponse(**result)

    except Exception as e:
        logger.error(f"Failed to set topic count: {e}")
        raise HTTPException(status_code=500, detail="Failed to set topic count")


@router.delete(
    "/topics/{topic_session_id}/topic/{topic_name}", response_model=TopicDeleteResponse
)
async def delete_topic(topic_session_id: str, topic_name: str, request: Request):
    """Removes specific topic from suggestions"""
    session_id = get_session_id(request)
    validate_topic_session_access(topic_session_id, session_id)

    try:
        result = topic_service.delete_topic(
            topic_session_id=topic_session_id,
            topic_name=topic_name,
            session_id=session_id,
        )

        return TopicDeleteResponse(**result)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to delete topic: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete topic")


@router.post("/topics/{topic_session_id}/add", response_model=TopicAddResponse)
async def add_topic(
    topic_session_id: str, add_request: AddTopicRequest, request: Request
):
    """Adds custom topic to suggestions"""
    session_id = get_session_id(request)
    validate_topic_session_access(topic_session_id, session_id)

    try:
        result = topic_service.add_topic(
            topic_session_id=topic_session_id,
            topic_name=add_request.topic_name,
            weight=add_request.weight,
            session_id=session_id,
        )

        return TopicAddResponse(
            added_topic=WeightedTopicResponse(**result["added_topic"]),
            total_topics=result["total_topics"],
            weights_normalized=result["weights_normalized"],
        )

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
    update_request: UpdateTopicRequest,
    request: Request,
):
    """Renames topic and/or changes its weight"""
    session_id = get_session_id(request)
    validate_topic_session_access(topic_session_id, session_id)

    if not update_request.new_name and update_request.new_weight is None:
        raise HTTPException(
            status_code=400, detail="Either new_name or new_weight must be provided"
        )

    try:
        result = topic_service.update_topic(
            topic_session_id=topic_session_id,
            current_topic_name=topic_name,
            new_name=update_request.new_name,
            new_weight=update_request.new_weight,
            session_id=session_id,
        )

        return TopicUpdateResponse(
            old_topic=result["old_topic"],
            new_topic=WeightedTopicResponse(**result["new_topic"]),
            weights_normalized=result["weights_normalized"],
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update topic: {e}")
        raise HTTPException(status_code=500, detail="Failed to update topic")


@router.get(
    "/topics/{topic_session_id}/suggestions", response_model=TopicSuggestionsResponse
)
async def get_topic_suggestions(
    topic_session_id: str, request: Request, count: Optional[int] = None
):
    """Gets AI-generated topic suggestions based on documents"""
    session_id = get_session_id(request)
    validate_topic_session_access(topic_session_id, session_id)

    if count is not None and (count <= 0 or count > 20):
        raise HTTPException(status_code=400, detail="Count must be between 1 and 20")

    try:
        result = topic_service.get_topic_suggestions(
            topic_session_id=topic_session_id, count=count
        )

        return TopicSuggestionsResponse(**result)

    except Exception as e:
        logger.error(f"Failed to get topic suggestions: {e}")
        raise HTTPException(status_code=500, detail="Failed to get topic suggestions")


# Utility endpoints


@router.get("/topics/{topic_session_id}/export")
async def export_topics(topic_session_id: str, request: Request):
    """Export topics configuration for backup/sharing"""
    session_id = get_session_id(request)
    topic_session = validate_topic_session_access(topic_session_id, session_id)

    return {
        "topic_session_id": topic_session_id,
        "quiz_id": topic_session.quiz_id,
        "suggested_topics": topic_session.suggested_topics,
        "confirmed_topics": topic_session.confirmed_topics,
        "desired_topic_count": topic_session.desired_topic_count,
        "status": topic_session.status,
        "created_at": topic_session.created_at,
        "conversation_history": topic_session.conversation_history,
    }


@router.post("/topics/{topic_session_id}/import")
async def import_topics(topic_session_id: str, request: Request, topics_data: dict):
    """Import topics configuration from backup"""
    session_id = get_session_id(request)
    validate_topic_session_access(topic_session_id, session_id)

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
            session_id,
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
    session_id = get_session_id(request)
    topic_session = validate_topic_session_access(topic_session_id, session_id)

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
