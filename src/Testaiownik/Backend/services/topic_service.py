# src/Testaiownik/Backend/services/topic_service.py
from typing import List, Dict, Any, Optional
import json

from Agent.Shared import WeightedTopic
from ..database.crud import get_topic_session, update_topic_session, log_activity
from utils import logger


class TopicService:
    """Service for topic management operations"""

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
                topic["weight"] = topic.get("weight", 0) / total_weight

        return topics

    def add_topic(
        self,
        topic_session_id: str,
        topic_name: str,
        weight: float,
        user_id: str,  # ✅ Changed
    ) -> Dict:
        """Add a custom topic to suggestions"""
        try:
            topic_session = get_topic_session(topic_session_id)
            if not topic_session:
                raise ValueError("Topic session not found")

            current_topics = topic_session.suggested_topics or []

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
            update_topic_session(topic_session_id, suggested_topics=normalized_topics)

            log_activity(
                user_id,  # ✅ Changed
                "topic_added",
                {"topic_session_id": topic_session_id, "topic_name": topic_name},
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
        self, topic_session_id: str, topic_name: str, user_id: str  # ✅ Changed
    ) -> Dict:
        """Remove a topic from suggestions"""
        try:
            topic_session = get_topic_session(topic_session_id)
            if not topic_session:
                raise ValueError("Topic session not found")

            current_topics = topic_session.suggested_topics or []

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
            update_topic_session(topic_session_id, suggested_topics=normalized_topics)

            log_activity(
                user_id,  # ✅ Changed
                "topic_deleted",
                {"topic_session_id": topic_session_id, "topic_name": topic_name},
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
        topic_session_id: str,
        current_topic_name: str,
        new_name: Optional[str] = None,
        new_weight: Optional[float] = None,
        user_id: str = None,  # ✅ Changed
    ) -> Dict:
        """Update topic name and/or weight"""
        try:
            topic_session = get_topic_session(topic_session_id)
            if not topic_session:
                raise ValueError("Topic session not found")

            current_topics = topic_session.suggested_topics or []

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
            update_topic_session(topic_session_id, suggested_topics=normalized_topics)

            log_activity(
                user_id,  # ✅ Changed
                "topic_updated",
                {
                    "topic_session_id": topic_session_id,
                    "old_name": current_topic_name,
                    "new_name": new_name,
                    "new_weight": new_weight,
                },
            )

            return {
                "success": True,
                "old_topic": current_topic_name,
                "new_topic": normalized_topics[topic_index],
                "weights_normalized": True,
            }

        except Exception as e:
            logger.error(f"Failed to update topic: {e}")
            raise

    def set_topic_count(
        self, topic_session_id: str, desired_count: int, user_id: str  # ✅ Changed
    ) -> Dict:
        """Set desired topic count for analysis"""
        try:
            topic_session = get_topic_session(topic_session_id)
            if not topic_session:
                raise ValueError("Topic session not found")

            old_count = topic_session.desired_topic_count

            # Update database
            update_topic_session(topic_session_id, desired_topic_count=desired_count)

            log_activity(
                user_id,  # ✅ Changed
                "topic_count_updated",
                {
                    "topic_session_id": topic_session_id,
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

    async def generate_topic_suggestions(
        self, quiz_id: str, count: int = 5
    ) -> List[Dict]:
        """Generate AI-based topic suggestions"""
        try:
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

    def get_latest_topic_session(self, quiz_id: str):
        """Get the most recent topic session for a quiz"""
        try:
            # This would need a database function to get latest topic session by quiz_id
            # For now, placeholder implementation
            from ..database.crud import get_quiz

            quiz = get_quiz(quiz_id)
            if quiz and hasattr(quiz, "topic_sessions") and quiz.topic_sessions:
                return quiz.topic_sessions[-1]  # Get the latest one
            return None

        except Exception as e:
            logger.error(f"Failed to get latest topic session: {e}")
            return None

    def confirm_topic_selection(self, topic_session_id: str) -> Dict:
        """Confirm topic selection and prepare for quiz generation"""
        try:
            topic_session = get_topic_session(topic_session_id)
            if not topic_session:
                raise ValueError("Topic session not found")

            if not topic_session.suggested_topics:
                raise ValueError("No topics available to confirm")

            # Move topics from suggested to confirmed
            confirmed_topics = topic_session.suggested_topics.copy()

            # Update database
            update_topic_session(
                topic_session_id, confirmed_topics=confirmed_topics, status="completed"
            )

            return {
                "confirmed_topics": confirmed_topics,
                "total_topics": len(confirmed_topics),
                "ready_for_quiz": True,
                "quiz_id": topic_session.quiz_id,
            }

        except Exception as e:
            logger.error(f"Failed to confirm topic selection: {e}")
            raise
