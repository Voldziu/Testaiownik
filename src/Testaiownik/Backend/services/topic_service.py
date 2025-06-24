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
        self, topic_session_id: str, topic_name: str, weight: float, session_id: str
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
                session_id,
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
        self, topic_session_id: str, topic_name: str, session_id: str
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
                session_id,
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
        session_id: str = None,
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
                session_id,
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
        self, topic_session_id: str, desired_count: int, session_id: str
    ) -> Dict:
        """Set desired number of topics"""
        try:
            topic_session = get_topic_session(topic_session_id)
            if not topic_session:
                raise ValueError("Topic session not found")

            old_count = topic_session.desired_topic_count

            # Update desired count
            update_topic_session(topic_session_id, desired_topic_count=desired_count)

            log_activity(
                session_id,
                "topic_count_changed",
                {
                    "topic_session_id": topic_session_id,
                    "old_count": old_count,
                    "new_count": desired_count,
                },
            )

            # Check if reanalysis is needed
            current_topics = topic_session.suggested_topics or []
            reanalysis_needed = len(current_topics) != desired_count

            return {
                "success": True,
                "new_count": desired_count,
                "reanalysis_required": reanalysis_needed,
            }

        except Exception as e:
            logger.error(f"Failed to set topic count: {e}")
            raise

    def get_topic_suggestions(
        self, topic_session_id: str, count: Optional[int] = None
    ) -> Dict:
        """Get AI-generated topic suggestions"""
        try:
            topic_session = get_topic_session(topic_session_id)
            if not topic_session:
                raise ValueError("Topic session not found")

            # This is a simplified implementation
            # In a real scenario, you might use the RAG system to analyze documents
            # and suggest additional relevant topics

            current_topics = topic_session.suggested_topics or []
            current_names = [topic.get("topic", "") for topic in current_topics]

            # Sample suggestions based on common academic topics
            # In practice, this would use your LLM and document analysis
            sample_suggestions = [
                {
                    "topic": "Machine Learning",
                    "confidence": 0.85,
                    "reasoning": "Frequently mentioned in uploaded documents",
                },
                {
                    "topic": "Data Structures",
                    "confidence": 0.78,
                    "reasoning": "Core computer science concept detected",
                },
                {
                    "topic": "Algorithms",
                    "confidence": 0.82,
                    "reasoning": "Multiple algorithm examples found",
                },
                {
                    "topic": "Database Systems",
                    "confidence": 0.71,
                    "reasoning": "SQL and database terms identified",
                },
                {
                    "topic": "Software Engineering",
                    "confidence": 0.76,
                    "reasoning": "Development methodologies discussed",
                },
            ]

            # Filter out existing topics
            suggestions = [
                sugg
                for sugg in sample_suggestions
                if sugg["topic"] not in current_names
            ]

            # Limit count if specified
            if count:
                suggestions = suggestions[:count]

            return {"suggestions": suggestions, "total_suggestions": len(suggestions)}

        except Exception as e:
            logger.error(f"Failed to get topic suggestions: {e}")
            raise

    def validate_topics(self, topics: List[Dict]) -> bool:
        """Validate topic list structure and weights"""
        if not topics:
            return False

        try:
            total_weight = 0
            for topic in topics:
                if not isinstance(topic, dict):
                    return False
                if "topic" not in topic or "weight" not in topic:
                    return False
                if not isinstance(topic["topic"], str) or not topic["topic"].strip():
                    return False
                if not isinstance(topic["weight"], (int, float)) or topic["weight"] < 0:
                    return False
                total_weight += topic["weight"]

            # Check if weights sum to approximately 1.0
            return abs(total_weight - 1.0) < 0.01

        except Exception:
            return False
