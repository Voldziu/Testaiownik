# src/Testaiownik/Backend/services/topic_service.py
from typing import List, Dict, Optional

from sqlalchemy.orm import Session

from ..models.responses import TopicUpdateResponse

from ..database.crud import get_quiz, update_topic_data, log_activity

from utils import logger


class TopicService:
    """Simplified service for topic management operations using quiz_id only"""

    def normalize_weights(self, topics: List[Dict]) -> List[Dict]:
        """Normalize topic weights to sum to 1.0"""
        if not topics:
            return topics

        total_weight = sum(topic.get("weight", 0) for topic in topics)
        if total_weight == 0:
            # Assign equal weights
            weight = 1.0 / len(topics)
            for topic in topics:
                topic["weight"] = weight
        elif abs(total_weight - 1.0) > 0.01:  # Need normalization
            for topic in topics:
                topic["weight"] = round(topic["weight"] / total_weight, 2)
        return topics

    def add_topic(
        self,
        quiz_id: str,
        topic_name: str,
        weight: float,
        user_id: str,
        db: Session,
    ) -> Dict:
        """Add a custom topic to suggestions"""
        try:
            quiz = get_quiz(db, quiz_id)
            if not quiz:
                raise ValueError("Quiz not found")

            current_topics = quiz.suggested_topics or []

            # Check if topic already exists
            existing_names = [topic.get("topic", "") for topic in current_topics]
            if topic_name in existing_names:
                raise ValueError("Topic already exists")

            # Add new topic
            new_topic = {"topic": topic_name, "weight": weight}
            current_topics.append(new_topic)

            # Normalize weights
            normalized_topics = self.normalize_weights(current_topics)

            # Update database
            update_topic_data(quiz_id, suggested_topics=normalized_topics)

            log_activity(
                db,
                user_id,
                "topic_added",
                {"quiz_id": quiz_id, "topic_name": topic_name},
            )

            return {
                "success": True,
                "added_topic": {
                    "topic": topic_name,
                    "weight": normalized_topics[-1]["weight"],
                },
                "total_topics": len(normalized_topics),
                "weights_normalized": True,
            }

        except Exception as e:
            logger.error(f"Failed to add topic: {e}")
            raise

    def delete_topic(
        self, quiz_id: str, topic_name: str, user_id: str, db: Session
    ) -> Dict:
        """Remove a topic from suggestions"""
        try:
            quiz = get_quiz(db, quiz_id)
            if not quiz:
                raise ValueError("Quiz not found")

            current_topics = quiz.suggested_topics or []

            # Find and remove topic
            updated_topics = [
                topic for topic in current_topics if topic.get("topic") != topic_name
            ]

            if len(updated_topics) == len(current_topics):
                raise ValueError("Topic not found")

            if not updated_topics:
                raise ValueError("Cannot delete all topics")

            # Normalize weights
            normalized_topics = self.normalize_weights(updated_topics)

            # Update database
            update_topic_data(db, quiz_id, suggested_topics=normalized_topics)

            log_activity(
                db,
                user_id,
                "topic_deleted",
                {"quiz_id": quiz_id, "topic_name": topic_name},
            )

            return {
                "success": True,
                "deleted_topic": topic_name,
                "remaining_topics": len(normalized_topics),
                "weights_redistributed": True,
            }

        except Exception as e:
            logger.error(f"Failed to delete topic: {e}")
            raise

    def update_topic(
        self,
        quiz_id: str,
        current_topic_name: str,
        db: Session,
        new_name: Optional[str] = None,
        new_weight: Optional[float] = None,
        user_id: str = None,
    ) -> TopicUpdateResponse:
        """Update topic name and/or weight"""
        try:
            quiz = get_quiz(db, quiz_id)
            if not quiz:
                raise ValueError("Quiz not found")

            current_topics = quiz.suggested_topics or []

            # Find topic to update
            topic_index = None
            for i, topic in enumerate(current_topics):
                if topic.get("topic") == current_topic_name:
                    topic_index = i
                    break

            if topic_index is None:
                raise ValueError("Topic not found")

            # Update topic
            updated_topic = current_topics[topic_index].copy()

            if new_name:
                # Check if new name already exists
                existing_names = [
                    topic.get("topic", "")
                    for i, topic in enumerate(current_topics)
                    if i != topic_index
                ]
                if new_name in existing_names:
                    raise ValueError("Topic name already exists")
                updated_topic["topic"] = new_name

            if new_weight is not None:
                updated_topic["weight"] = new_weight

            # Replace topic in list
            current_topics[topic_index] = updated_topic

            # Normalize weights
            normalized_topics = self.normalize_weights(current_topics)

            # Update database
            update_topic_data(db, quiz_id, suggested_topics=normalized_topics)

            log_activity(
                db,
                user_id,
                "topic_updated",
                {
                    "quiz_id": quiz_id,
                    "old_name": current_topic_name,
                    "new_name": new_name,
                    "new_weight": new_weight,
                },
            )

            updated_quiz = get_quiz(db, quiz_id)
            logger.info(f"Updated topics in DB: {updated_quiz.suggested_topics}")

            return TopicUpdateResponse(
                success=True,
                old_topic=current_topic_name,
                new_topic=normalized_topics[topic_index],
                weights_normalized=True,
            )

        except Exception as e:
            logger.error(f"Failed to update topic: {e}")
            raise

    def set_topic_count(
        self, quiz_id: str, desired_count: int, user_id: str, db: Session
    ) -> Dict:
        """Set desired topic count for analysis"""
        try:
            quiz = get_quiz(db, quiz_id)
            if not quiz:
                raise ValueError("Quiz not found")

            old_count = quiz.desired_topic_count

            # Update database
            update_topic_data(db, quiz_id, desired_topic_count=desired_count)

            log_activity(
                db,
                user_id,
                "topic_count_updated",
                {
                    "quiz_id": quiz_id,
                    "old_count": old_count,
                    "new_count": desired_count,
                },
            )

            return {
                "success": True,
                "new_count": desired_count,
                "reanalysis_required": desired_count != old_count,
            }

        except Exception as e:
            logger.error(f"Failed to set topic count: {e}")
            raise

    def validate_topics(self, topics: List[Dict]) -> bool:
        """Validate topic configuration"""
        if not topics:
            return False

        total_weight = sum(topic.get("weight", 0) for topic in topics)

        # Check if all topics have valid names and weights
        for topic in topics:
            if not topic.get("topic", "").strip():
                return False
            if topic.get("weight", 0) <= 0:
                return False

        # Check if weights are reasonable (sum close to 1.0)
        return abs(total_weight - 1.0) < 0.01

    # TODO: INTEGRATE AI TOPIC SUGGESTIONS
    async def generate_topic_suggestions(
        self,
        quiz_id: str,
        db: Session,
        count: int = 5,
    ) -> List[Dict]:
        """Generate AI-based topic suggestions"""
        try:
            quiz = get_quiz(db, quiz_id)
            if not quiz or not quiz.collection_name:
                return []

            # This would integrate with your AI topic generation
            # For now, return placeholder suggestions
            suggestions = [
                {"topic": "Machine Learning Basics", "weight": 1.0},
                {"topic": "Data Structures", "weight": 1.0},
                {"topic": "Algorithms", "weight": 1.0},
                {"topic": "System Design", "weight": 1.0},
                {"topic": "Database Concepts", "weight": 1.0},
            ]

            return suggestions[:count]

        except Exception as e:
            logger.error(f"Failed to generate topic suggestions: {e}")
            return []

    def confirm_topic_selection(self, quiz_id: str, db: Session) -> Dict:
        """Confirm topic selection and prepare for quiz generation"""
        try:
            quiz = get_quiz(db, quiz_id)
            if not quiz:
                raise ValueError("Quiz not found")

            if not quiz.suggested_topics:
                raise ValueError("No topics available to confirm")

            # Move topics from suggested to confirmed
            confirmed_topics = quiz.suggested_topics.copy()

            # Update database
            from ..database.crud import confirm_quiz_topics

            success = confirm_quiz_topics(db, quiz_id, confirmed_topics)

            if not success:
                raise ValueError("Failed to confirm topics in database")

            return {
                "confirmed_topics": confirmed_topics,
                "total_topics": len(confirmed_topics),
                "ready_for_quiz": True,
                "quiz_id": quiz_id,
            }

        except Exception as e:
            logger.error(f"Failed to confirm topic selection: {e}")
            raise

    def get_topic_analysis_status(self, quiz_id: str, db: Session) -> Dict:
        """Get topic analysis status for quiz"""
        try:
            quiz = get_quiz(db, quiz_id)
            if not quiz:
                raise ValueError("Quiz not found")

            return {
                "quiz_id": quiz_id,
                "status": quiz.status,
                "suggested_topics": quiz.suggested_topics or [],
                "confirmed_topics": quiz.confirmed_topics or [],
                "desired_topic_count": quiz.desired_topic_count,
                "feedback_request": quiz.topic_feedback_request,
                "conversation_history": quiz.topic_conversation_history or [],
            }

        except Exception as e:
            logger.error(f"Failed to get topic analysis status: {e}")
            raise

    def export_topics(self, quiz_id: str, db: Session) -> Dict:
        """Export current topic configuration for backup"""
        try:
            quiz = get_quiz(db, quiz_id)
            if not quiz:
                raise ValueError("Quiz not found")

            export_data = {
                "quiz_id": quiz_id,
                "suggested_topics": quiz.suggested_topics,
                "confirmed_topics": quiz.confirmed_topics,
                "desired_topic_count": quiz.desired_topic_count,
                "status": quiz.status,
                "exported_at": quiz.updated_at.isoformat() if quiz.updated_at else None,
            }

            return {
                "success": True,
                "export_data": export_data,
                "message": "Topics exported successfully",
            }

        except Exception as e:
            logger.error(f"Failed to export topics: {e}")
            raise

    def import_topics(
        self,
        quiz_id: str,
        topics_data: Dict,
        user_id: str,
        db: Session,
    ) -> Dict:
        """Import topics configuration from backup"""
        try:
            # Validate imported data
            if "suggested_topics" not in topics_data:
                raise ValueError("Invalid topics data - missing suggested_topics")

            topics = topics_data["suggested_topics"]
            if not self.validate_topics(topics):
                raise ValueError("Invalid topic format or weights")

            # Update database
            update_topic_data(
                db,
                quiz_id,
                suggested_topics=topics,
                desired_topic_count=topics_data.get("desired_topic_count", len(topics)),
            )

            log_activity(
                db,
                user_id,
                "topics_imported",
                {"quiz_id": quiz_id, "topic_count": len(topics)},
            )

            return {
                "success": True,
                "message": "Topics imported successfully",
                "imported_topics": len(topics),
            }

        except Exception as e:
            logger.error(f"Failed to import topics: {e}")
            raise

    def reset_topic_analysis(self, quiz_id: str, user_id: str, db: Session) -> Dict:
        """Reset topic analysis to start over"""
        try:
            # Reset topic data
            update_topic_data(
                db,
                quiz_id,
                status="documents_indexed",
                suggested_topics=None,
                confirmed_topics=None,
                topic_feedback_request=None,
                topic_conversation_history=[],
                langgraph_topic_state=None,
            )

            log_activity(
                db,
                user_id,
                "topic_analysis_reset",
                {"quiz_id": quiz_id},
            )

            return {
                "success": True,
                "message": "Topic analysis reset successfully",
                "new_status": "documents_indexed",
            }

        except Exception as e:
            logger.error(f"Failed to reset topic analysis: {e}")
            raise
