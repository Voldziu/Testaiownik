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
    get_quiz,
    update_quiz,
    update_topic_data,
    confirm_quiz_topics,
    start_quiz_execution,
    update_quiz_progress,
    complete_quiz,
    log_activity,
)
from utils import logger


class QuizService:
    """Simplified service layer for quiz operations using quiz_id only"""

    def __init__(self):
        self.active_topic_graphs = {}  # quiz_id -> graph instance
        self.active_quiz_graphs = {}  # quiz_id -> graph instance
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
        self, quiz_id: str, user_id: str, desired_topic_count: int = 10
    ) -> bool:
        """Start topic analysis using LangGraph agent"""
        try:
            quiz = get_quiz(quiz_id)
            if not quiz:
                raise ValueError("Quiz not found")

            # Initialize topic analysis in database
            from ..database.crud import start_topic_analysis

            success = start_topic_analysis(quiz_id, desired_topic_count)

            if not success:
                raise ValueError("Failed to initialize topic analysis")

            # Create RAG retriever for this quiz
            collection_name = quiz.collection_name
            if not collection_name:
                raise ValueError("Quiz collection not found")

            retriever = RAGRetriever(collection_name, self.qdrant_manager)

            # Create topic selection graph
            topic_graph = create_agent_graph(retriever)

            # Store graph instance
            self.active_topic_graphs[quiz_id] = {
                "graph": topic_graph,
                "config": {"configurable": {"thread_id": quiz_id}},
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

            # Run in background task
            self._create_background_task(
                self._run_topic_analysis(quiz_id, initial_state)
            )

            log_activity(
                user_id,
                "topic_analysis_started",
                {"quiz_id": quiz_id},
            )
            return True

        except Exception as e:
            logger.error(f"Failed to start topic analysis: {e}")
            # Update quiz status to failed
            update_quiz(quiz_id, status="failed")
            raise

    async def _run_topic_analysis(self, quiz_id: str, initial_state: Dict):
        """Background task to run topic analysis"""
        try:
            graph_data = self.active_topic_graphs[quiz_id]
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
            update_topic_data(
                quiz_id,
                status="topic_feedback",
                suggested_topics=suggested_topics,
                topic_feedback_request=current_state.values.get("feedback_request"),
                topic_conversation_history=current_state.values.get(
                    "conversation_history", []
                ),
                langgraph_topic_state=serialized_state,
            )

            logger.info(f"Topic analysis completed for quiz {quiz_id}")

        except Exception as e:
            logger.error(f"Topic analysis failed for quiz {quiz_id}: {e}")
            # Update status to failed
            update_quiz(quiz_id, status="failed")

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
                if hasattr(value, "model_dump"):
                    result[key] = value.model_dump()
                elif hasattr(value, "dict"):
                    result[key] = value.dict()
                elif isinstance(value, list):
                    # Handle lists recursively
                    result[key] = [self._serialize_value(item) for item in value]
                elif isinstance(value, dict):
                    result[key] = self._serialize_dict(value)
                elif isinstance(value, (str, int, float, bool, type(None))):
                    result[key] = value
                else:
                    result[key] = str(value)
            except Exception:
                result[key] = str(value)
        return result

    def _serialize_value(self, value):
        """Serialize individual values"""
        if hasattr(value, "model_dump"):
            return value.model_dump()
        elif hasattr(value, "dict"):
            return value.dict()
        elif isinstance(value, list):
            return [self._serialize_value(item) for item in value]
        elif isinstance(value, dict):
            return self._serialize_dict(value)
        elif isinstance(value, (str, int, float, bool, type(None))):
            return value
        else:
            return str(value)

    async def submit_topic_feedback(
        self, quiz_id: str, user_input: str, user_id: str
    ) -> Dict:
        """Process user feedback on topics"""
        try:
            quiz = get_quiz(quiz_id)
            if not quiz:
                raise ValueError("Quiz not found")

            # Get graph instance
            if quiz_id not in self.active_topic_graphs:
                # Try to restore from database state
                if not self._restore_topic_session(quiz_id):
                    raise ValueError("Cannot restore topic session")

            graph_data = self.active_topic_graphs[quiz_id]
            graph = graph_data["graph"]
            config = graph_data["config"]

            # Submit feedback to graph
            feedback_state = {"user_input": user_input}
            result = graph.invoke(feedback_state, config)

            # Get updated state
            current_state = graph.get_state(config)

            # Process and update database
            suggested_topics = self._extract_topics_from_state(current_state)
            serialized_state = self._serialize_langgraph_state(current_state)

            update_topic_data(
                quiz_id,
                suggested_topics=suggested_topics,
                topic_feedback_request=current_state.values.get("feedback_request"),
                topic_conversation_history=current_state.values.get(
                    "conversation_history", []
                ),
                langgraph_topic_state=serialized_state,
            )

            log_activity(
                user_id,
                "topic_feedback_submitted",
                {"quiz_id": quiz_id},
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

    def _restore_topic_session(self, quiz_id: str) -> bool:
        """Restore topic session from database state"""
        try:
            quiz = get_quiz(quiz_id)
            if not quiz or not quiz.langgraph_topic_state:
                return False

            # Recreate graph and config
            collection_name = quiz.collection_name
            retriever = RAGRetriever(collection_name, self.qdrant_manager)
            topic_graph = create_agent_graph(retriever)

            config = {"configurable": {"thread_id": quiz_id}}

            self.active_topic_graphs[quiz_id] = {
                "graph": topic_graph,
                "config": config,
                "retriever": retriever,
            }

            return True

        except Exception as e:
            logger.error(f"Failed to restore topic session: {e}")
            return False

    def confirm_topics(self, quiz_id: str, user_id: str) -> Dict:
        """Confirm final topic selection"""
        try:
            quiz = get_quiz(quiz_id)
            if not quiz:
                raise ValueError("Quiz not found")

            if not quiz.suggested_topics:
                raise ValueError("No topics available to confirm")

            # Confirm topics
            confirmed_topics = quiz.suggested_topics.copy()

            success = confirm_quiz_topics(quiz_id, confirmed_topics)
            if not success:
                raise ValueError("Failed to confirm topics")

            log_activity(
                user_id,
                "topics_confirmed",
                {"quiz_id": quiz_id},
            )

            return {
                "confirmed_topics": confirmed_topics,
                "total_topics": len(confirmed_topics),
                "ready_for_quiz": True,
                "quiz_id": quiz_id,
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
        user_id: str,
    ) -> bool:
        """Start quiz execution with confirmed topics"""
        try:
            # Initialize quiz execution in database
            success = start_quiz_execution(quiz_id, total_questions, difficulty)
            if not success:
                raise ValueError("Failed to start quiz execution")

            # Start quiz generation in background
            self._create_background_task(
                self._generate_quiz_questions(quiz_id, confirmed_topics, user_questions)
            )

            log_activity(
                user_id,
                "quiz_started",
                {"quiz_id": quiz_id},
            )

            return True

        except Exception as e:
            logger.error(f"Failed to start quiz: {e}")
            raise

    async def _generate_quiz_questions(
        self, quiz_id: str, confirmed_topics: List[Dict], user_questions: List[str]
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

            update_quiz_progress(quiz_id, questions_data=questions_data)

            # Update status to active when ready
            update_quiz(quiz_id, status="quiz_active")

            logger.info(f"Quiz questions generated for {quiz_id}")

        except Exception as e:
            logger.error(f"Failed to generate quiz questions: {e}")
            update_quiz(quiz_id, status="failed")

    def get_current_question(self, quiz_id: str) -> Optional[Dict]:
        """Get current question for quiz"""
        try:
            quiz = get_quiz(quiz_id)
            if not quiz:
                return None

            # Implementation would return current question
            # For now, placeholder
            return {
                "current_question": None,
                "progress": {
                    "current_question_number": quiz.current_question_index,
                    "total_questions": quiz.total_questions or 0,
                    "answered": len(quiz.user_answers or []),
                    "correct": sum(
                        1
                        for a in (quiz.user_answers or [])
                        if isinstance(a, dict) and a.get("is_correct")
                    ),
                },
                "status": quiz.status,
            }

        except Exception as e:
            logger.error(f"Failed to get current question: {e}")
            return None

    async def submit_answer(
        self, quiz_id: str, selected_choices: List[int], question_id: str
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

    def get_quiz_results(self, quiz_id: str) -> Optional[Dict]:
        """Get quiz results and statistics"""
        try:
            quiz = get_quiz(quiz_id)
            if not quiz or quiz.status != "quiz_completed":
                return None

            # Calculate results from quiz data
            total_questions = quiz.total_questions or 0
            user_answers = quiz.user_answers or []

            correct_answers = sum(
                1
                for answer in user_answers
                if isinstance(answer, dict) and answer.get("is_correct")
            )

            score_percentage = (
                (correct_answers / total_questions * 100) if total_questions > 0 else 0
            )

            # Calculate topic scores
            topic_scores = {}
            if quiz.confirmed_topics:
                for topic_data in quiz.confirmed_topics:
                    topic_name = topic_data.get("topic", "Unknown")
                    topic_scores[topic_name] = {
                        "correct": 0,  # Would calculate from answers
                        "total": 0,  # Would calculate from questions
                        "percentage": 0.0,
                    }

            return {
                "quiz_results": {
                    "session_id": quiz_id,
                    "total_questions": total_questions,
                    "correct_answers": correct_answers,
                    "score_percentage": score_percentage,
                    "topic_scores": topic_scores,
                    "completed_at": quiz.quiz_completed_at or datetime.now(),
                },
                "status": "completed",
            }

        except Exception as e:
            logger.error(f"Failed to get quiz results: {e}")
            return None

    def get_quiz_preview(self, quiz_id: str) -> Dict:
        """Get quiz preview data"""
        try:
            quiz = get_quiz(quiz_id)
            if not quiz:
                raise ValueError("Quiz not found")

            topics = quiz.confirmed_topics or []

            return {
                "total_questions": quiz.total_questions or 20,
                "difficulty": quiz.difficulty or "medium",
                "topics": [
                    {
                        "topic": topic.get("topic", "Unknown"),
                        "question_count": int(
                            (topic.get("weight", 0) * (quiz.total_questions or 20))
                        ),
                    }
                    for topic in topics
                ],
            }

        except Exception as e:
            logger.error(f"Failed to get quiz preview: {e}")
            return {}

    def pause_quiz(self, quiz_id: str) -> bool:
        """Pause active quiz"""
        try:
            return update_quiz(quiz_id, status="paused")
        except Exception as e:
            logger.error(f"Failed to pause quiz: {e}")
            return False

    def resume_quiz(self, quiz_id: str) -> bool:
        """Resume paused quiz"""
        try:
            return update_quiz(quiz_id, status="quiz_active")
        except Exception as e:
            logger.error(f"Failed to resume quiz: {e}")
            return False

    def cleanup_user_sessions(self, user_id: str):
        """Clean up user-related graph instances"""
        # Clean up topic graphs for user's quizzes
        from ..database.crud import get_quizzes_by_user

        user_quizzes = get_quizzes_by_user(user_id)
        quiz_ids_to_clean = [quiz.quiz_id for quiz in user_quizzes]

        for quiz_id in quiz_ids_to_clean:
            if quiz_id in self.active_topic_graphs:
                del self.active_topic_graphs[quiz_id]
                logger.info(f"Cleaned up topic graph for quiz {quiz_id}")

            if quiz_id in self.active_quiz_graphs:
                del self.active_quiz_graphs[quiz_id]
                logger.info(f"Cleaned up quiz graph for quiz {quiz_id}")
