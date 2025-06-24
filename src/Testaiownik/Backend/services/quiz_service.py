# src/Testaiownik/Backend/services/quiz_service.py
from typing import List, Dict, Any, Optional
import asyncio
import json
import uuid
from datetime import datetime

from Agent.runner import TestaiownikRunner
from Agent.TopicSelection import create_agent_graph, AgentState
from Agent.Quiz import create_quiz_graph, create_initial_quiz_state, QuizState
from Agent.Shared import WeightedTopic
from RAG.Retrieval import RAGRetriever
from RAG.qdrant_manager import QdrantManager

from ..database.crud import (
    create_topic_session,
    get_topic_session,
    update_topic_session,
    create_quiz_session,
    get_quiz_session,
    update_quiz_session,
    update_quiz_status,
    log_activity,
    get_quiz,
)
from utils import logger


class QuizService:
    """Service layer for quiz operations integrating with TestaiownikRunner"""

    def __init__(self):
        self.active_topic_graphs = {}  # topic_session_id -> graph instance
        self.active_quiz_graphs = {}  # quiz_session_id -> graph instance
        self.qdrant_manager = QdrantManager()

        # Background task tracking for cleanup
        self.background_tasks = set()

    def _cleanup_task(self, task):
        """Remove completed background task from tracking"""
        self.background_tasks.discard(task)

    def _create_background_task(self, coro):
        """Create and track background task"""
        task = asyncio.create_task(coro)
        self.background_tasks.add(task)
        task.add_done_callback(self._cleanup_task)
        return task

    # Topic Selection Phase
    async def start_topic_analysis(
        self, quiz_id: str, user_id: str, desired_topic_count: int = 10  # ✅ Changed
    ) -> str:
        """Start topic analysis using LangGraph agent"""
        try:
            # Create topic session in database
            topic_session = create_topic_session(quiz_id, desired_topic_count)
            topic_session_id = topic_session.topic_session_id

            # Create RAG retriever for this quiz
            collection_name = f"quiz_{quiz_id}"
            retriever = RAGRetriever(collection_name, self.qdrant_manager)

            # Create topic selection graph
            topic_graph = create_agent_graph(retriever)

            # Store graph instance
            self.active_topic_graphs[topic_session_id] = {
                "graph": topic_graph,
                "config": {"configurable": {"thread_id": topic_session_id}},
                "retriever": retriever,
            }

            # Initial state
            initial_state = {
                "suggested_topics": [],
                "rejected_topics": [],
                "confirmed_topics": [],
                "subtopics": {},
                "user_input": None,
                "feedback_request": None,
                "conversation_history": [],
                "next_node": "",
                "messages": [],
                "desired_topic_count": desired_topic_count,
            }

            # Start analysis
            update_topic_session(topic_session_id, status="analyzing")

            # Run in background task
            self._create_background_task(
                self._run_topic_analysis(topic_session_id, initial_state)
            )

            log_activity(
                user_id,  # ✅ Changed
                "topic_analysis_started",
                {"topic_session_id": topic_session_id},
            )
            return topic_session_id

        except Exception as e:
            logger.error(f"Failed to start topic analysis: {e}")
            raise

    async def _run_topic_analysis(self, topic_session_id: str, initial_state: Dict):
        """Background task to run topic analysis"""
        try:
            graph_data = self.active_topic_graphs[topic_session_id]
            graph = graph_data["graph"]
            config = graph_data["config"]

            # Start the graph
            result = graph.invoke(initial_state, config)

            # Get current state
            current_state = graph.get_state(config)

            # Properly serialize topics (handle WeightedTopic objects)
            suggested_topics = []
            if current_state.values.get("suggested_topics"):
                for topic in current_state.values["suggested_topics"]:
                    if hasattr(topic, "dict"):
                        suggested_topics.append(topic.dict())
                    elif hasattr(topic, "model_dump"):
                        suggested_topics.append(topic.model_dump())
                    elif isinstance(topic, dict):
                        suggested_topics.append(topic)
                    else:
                        # Convert to dict format
                        suggested_topics.append(
                            {
                                "topic": getattr(topic, "topic", str(topic)),
                                "weight": getattr(topic, "weight", 1.0),
                            }
                        )

            # Serialize complete state for restoration
            serialized_state = self._serialize_langgraph_state(current_state)

            # Update database with results
            update_topic_session(
                topic_session_id,
                status="awaiting_feedback",
                suggested_topics=suggested_topics,
                feedback_request=current_state.values.get("feedback_request"),
                conversation_history=current_state.values.get(
                    "conversation_history", []
                ),
                langgraph_state=serialized_state,
            )

            logger.info(f"Topic analysis completed for session {topic_session_id}")

        except Exception as e:
            logger.error(f"Topic analysis failed for session {topic_session_id}: {e}")
            # Update status to failed
            update_topic_session(topic_session_id, status="failed")

    def _serialize_langgraph_state(self, state) -> Dict:
        """Serialize LangGraph state for database storage"""
        try:
            # Extract serializable data from state
            return {
                "values": self._serialize_dict(state.values),
                "next": state.next,
                "config": state.config,
            }
        except Exception as e:
            logger.warning(f"Failed to serialize state: {e}")
            return {}

    def _serialize_dict(self, data) -> Dict:
        """Recursively serialize dictionary for JSON storage"""
        result = {}
        for key, value in data.items():
            try:
                if hasattr(value, "dict"):
                    result[key] = value.dict()
                elif hasattr(value, "model_dump"):
                    result[key] = value.model_dump()
                elif isinstance(value, (dict, list, str, int, float, bool, type(None))):
                    result[key] = value
                else:
                    result[key] = str(value)
            except Exception:
                result[key] = str(value)
        return result

    def get_topic_session_status(self, topic_session_id: str) -> Optional[Dict]:
        """Get topic session status and data"""
        try:
            topic_session = get_topic_session(topic_session_id)
            if not topic_session:
                return None

            return {
                "topic_session_id": topic_session_id,
                "status": topic_session.status,
                "suggested_topics": topic_session.suggested_topics or [],
                "feedback_request": topic_session.feedback_request,
                "conversation_history": topic_session.conversation_history or [],
            }

        except Exception as e:
            logger.error(f"Failed to get topic session status: {e}")
            return None

    async def submit_topic_feedback(
        self, topic_session_id: str, user_input: str, user_id: str  # ✅ Changed
    ) -> Dict:
        """Process user feedback on topics"""
        try:
            topic_session = get_topic_session(topic_session_id)
            if not topic_session:
                raise ValueError("Topic session not found")

            # Get graph instance
            if topic_session_id not in self.active_topic_graphs:
                # Try to restore from database state
                if not self._restore_topic_session(topic_session_id):
                    raise ValueError("Cannot restore topic session")

            graph_data = self.active_topic_graphs[topic_session_id]
            graph = graph_data["graph"]
            config = graph_data["config"]

            # Submit feedback to graph
            feedback_state = {"user_input": user_input}
            result = graph.invoke(feedback_state, config)

            # Get updated state
            current_state = graph.get_state(config)

            # Process and update database (similar to _run_topic_analysis)
            suggested_topics = self._extract_topics_from_state(current_state)
            serialized_state = self._serialize_langgraph_state(current_state)

            update_topic_session(
                topic_session_id,
                suggested_topics=suggested_topics,
                feedback_request=current_state.values.get("feedback_request"),
                conversation_history=current_state.values.get(
                    "conversation_history", []
                ),
                langgraph_state=serialized_state,
            )

            log_activity(
                user_id,  # ✅ Changed
                "topic_feedback_submitted",
                {"topic_session_id": topic_session_id},
            )

            return {
                "feedback_processed": True,
                "action_taken": "modify",
                "next_step": "analyze_documents",
                "message": "Feedback received, updating topics...",
            }

        except Exception as e:
            logger.error(f"Failed to submit topic feedback: {e}")
            raise

    def _extract_topics_from_state(self, state) -> List[Dict]:
        """Extract and normalize topics from graph state"""
        topics = []
        if state.values.get("suggested_topics"):
            for topic in state.values["suggested_topics"]:
                if hasattr(topic, "dict"):
                    topics.append(topic.dict())
                elif isinstance(topic, dict):
                    topics.append(topic)
                else:
                    topics.append({"topic": str(topic), "weight": 1.0})
        return topics

    def _restore_topic_session(self, topic_session_id: str) -> bool:
        """Restore topic session from database state"""
        try:
            topic_session = get_topic_session(topic_session_id)
            if not topic_session or not topic_session.langgraph_state:
                return False

            # Recreate graph and config
            quiz = get_quiz(topic_session.quiz_id)
            collection_name = f"quiz_{quiz.quiz_id}"
            retriever = RAGRetriever(collection_name, self.qdrant_manager)
            topic_graph = create_agent_graph(retriever)

            config = {"configurable": {"thread_id": topic_session_id}}

            self.active_topic_graphs[topic_session_id] = {
                "graph": topic_graph,
                "config": config,
                "retriever": retriever,
            }

            return True

        except Exception as e:
            logger.error(f"Failed to restore topic session: {e}")
            return False

    def confirm_topics(self, topic_session_id: str, user_id: str) -> Dict:  # ✅ Changed
        """Confirm final topic selection"""
        try:
            topic_session = get_topic_session(topic_session_id)
            if not topic_session:
                raise ValueError("Topic session not found")

            if not topic_session.suggested_topics:
                raise ValueError("No topics available to confirm")

            # Confirm topics
            confirmed_topics = topic_session.suggested_topics.copy()

            update_topic_session(
                topic_session_id, confirmed_topics=confirmed_topics, status="completed"
            )

            log_activity(
                user_id,  # ✅ Changed
                "topics_confirmed",
                {"topic_session_id": topic_session_id},
            )

            return {
                "confirmed_topics": confirmed_topics,
                "total_topics": len(confirmed_topics),
                "ready_for_quiz": True,
                "quiz_id": topic_session.quiz_id,
            }

        except Exception as e:
            logger.error(f"Failed to confirm topics: {e}")
            raise

    # Quiz Execution Phase
    async def start_quiz(
        self,
        quiz_id: str,
        confirmed_topics: List[Dict],
        total_questions: int,
        difficulty: str,
        user_questions: List[str],
        user_id: str,  # ✅ Changed from session_id
    ) -> str:
        """Start quiz execution with confirmed topics"""
        try:
            # Create quiz session
            quiz_session = create_quiz_session(quiz_id, total_questions, difficulty)
            quiz_session_id = quiz_session.quiz_session_id

            # Start quiz generation in background
            self._create_background_task(
                self._generate_quiz_questions(
                    quiz_session_id, confirmed_topics, user_questions
                )
            )

            log_activity(
                user_id,  # ✅ Changed
                "quiz_started",
                {"quiz_session_id": quiz_session_id},
            )

            return quiz_session_id

        except Exception as e:
            logger.error(f"Failed to start quiz: {e}")
            raise

    async def _generate_quiz_questions(
        self,
        quiz_session_id: str,
        confirmed_topics: List[Dict],
        user_questions: List[str],
    ):
        """Background task to generate quiz questions"""
        try:
            # Implementation would generate questions using Agent/Quiz
            # For now, placeholder
            questions_data = {
                "all_generated_questions": [],
                "user_questions": user_questions,
                "topics": confirmed_topics,
            }

            update_quiz_session(
                quiz_session_id, status="active", questions_data=questions_data
            )

            logger.info(f"Quiz questions generated for session {quiz_session_id}")

        except Exception as e:
            logger.error(f"Failed to generate quiz questions: {e}")
            update_quiz_session(quiz_session_id, status="failed")

    def get_current_question(self, quiz_session_id: str) -> Optional[Dict]:
        """Get current question for quiz session"""
        try:
            quiz_session = get_quiz_session(quiz_session_id)
            if not quiz_session:
                return None

            # Implementation would return current question
            # For now, placeholder
            return {
                "current_question": None,
                "progress": {
                    "current_question_number": 0,
                    "total_questions": quiz_session.total_questions,
                    "answered": 0,
                    "correct": 0,
                },
                "status": quiz_session.status,
            }

        except Exception as e:
            logger.error(f"Failed to get current question: {e}")
            return None

    async def submit_answer(
        self, quiz_session_id: str, selected_choices: List[int], question_id: str
    ) -> Dict:
        """Submit answer to current question"""
        try:
            # Implementation would process answer
            # For now, placeholder
            return {
                "correct": True,
                "explanation": "Placeholder explanation",
                "selected_answers": ["Option 1"],
                "correct_answers": ["Option 1"],
                "next_question_available": True,
                "progress": {"answered": 1, "correct": 1},
            }

        except Exception as e:
            logger.error(f"Failed to submit answer: {e}")
            raise

    def cleanup_user_sessions(self, user_id: str):  # ✅ Changed from session_id
        """Clean up user-related graph instances"""
        # Clean up topic graphs
        topic_sessions_to_remove = []
        for topic_session_id, graph_data in self.active_topic_graphs.items():
            # Check if this topic session belongs to the user
            topic_session = get_topic_session(topic_session_id)
            if topic_session:
                quiz = get_quiz(topic_session.quiz_id)
                if quiz and quiz.user_id == user_id:  # ✅ Changed
                    topic_sessions_to_remove.append(topic_session_id)

        for topic_session_id in topic_sessions_to_remove:
            del self.active_topic_graphs[topic_session_id]
            logger.info(f"Cleaned up topic graph for session {topic_session_id}")

        # Clean up quiz graphs
        quiz_sessions_to_remove = []
        for quiz_session_id, graph_data in self.active_quiz_graphs.items():
            quiz_session = get_quiz_session(quiz_session_id)
            if quiz_session:
                quiz = get_quiz(quiz_session.quiz_id)
                if quiz and quiz.user_id == user_id:  # ✅ Changed
                    quiz_sessions_to_remove.append(quiz_session_id)

        for quiz_session_id in quiz_sessions_to_remove:
            del self.active_quiz_graphs[quiz_session_id]
            logger.info(f"Cleaned up quiz graph for session {quiz_session_id}")

    def get_quiz_session(self, quiz_session_id: str):
        """Get quiz session from database"""
        return get_quiz_session(quiz_session_id)
