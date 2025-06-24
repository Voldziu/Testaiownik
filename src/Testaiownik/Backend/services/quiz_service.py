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
        self, quiz_id: str, session_id: str, desired_topic_count: int = 10
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
                session_id,
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
            serialized_state = self._serialize_langgraph_state(current_state.values)

            # Update database with results
            if suggested_topics:
                update_topic_session(
                    topic_session_id,
                    status="awaiting_feedback",
                    suggested_topics=suggested_topics,
                    feedback_request=current_state.values.get("feedback_request"),
                    langgraph_state=serialized_state,
                )
            else:
                # No topics found - still analyzing or failed
                if current_state.values.get("next_node") == "END":
                    update_topic_session(topic_session_id, status="failed")
                else:
                    update_topic_session(
                        topic_session_id,
                        status="analyzing",
                        langgraph_state=serialized_state,
                    )

        except Exception as e:
            logger.error(f"Topic analysis failed: {e}", exc_info=True)
            update_topic_session(topic_session_id, status="failed")

    def get_topic_session_status(self, topic_session_id: str) -> Optional[Dict]:
        """Get current topic selection status"""
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

    async def submit_topic_feedback(
        self, topic_session_id: str, user_input: str, session_id: str
    ) -> Dict:
        """Submit user feedback for topic selection"""
        try:
            if topic_session_id not in self.active_topic_graphs:
                raise ValueError("Topic session not found or expired")

            graph_data = self.active_topic_graphs[topic_session_id]
            graph = graph_data["graph"]
            config = graph_data["config"]

            # Update state with user input
            graph.update_state(config, {"user_input": user_input})

            # Continue processing
            graph.invoke(None, config)

            # Get updated state
            current_state = graph.get_state(config)

            # Check if finished
            if current_state.next == ():
                confirmed_topics = current_state.values.get("confirmed_topics", [])
                if confirmed_topics:
                    # Topic selection completed
                    update_topic_session(
                        topic_session_id,
                        status="completed",
                        confirmed_topics=[topic.dict() for topic in confirmed_topics],
                        langgraph_state=current_state.values,
                    )

                    # Clean up
                    del self.active_topic_graphs[topic_session_id]

                    log_activity(
                        session_id,
                        "topics_confirmed",
                        {"topic_session_id": topic_session_id},
                    )

                    return {
                        "feedback_processed": True,
                        "action_taken": "accept",
                        "next_step": "completed",
                        "message": "Topics confirmed successfully",
                    }

            # Still processing
            update_topic_session(
                topic_session_id,
                suggested_topics=[
                    topic.dict()
                    for topic in current_state.values.get("suggested_topics", [])
                ],
                feedback_request=current_state.values.get("feedback_request"),
                conversation_history=current_state.values.get(
                    "conversation_history", []
                ),
                langgraph_state=current_state.values,
            )

            return {
                "feedback_processed": True,
                "action_taken": "modify",
                "next_step": "analyze_documents",
                "message": "Feedback received, regenerating topics...",
            }

        except Exception as e:
            logger.error(f"Failed to process topic feedback: {e}")
            raise

    def confirm_topics(self, topic_session_id: str, session_id: str) -> Dict:
        """Confirm final topic selection"""
        topic_session = get_topic_session(topic_session_id)
        if not topic_session:
            raise ValueError("Topic session not found")

        if topic_session.status != "completed":
            raise ValueError("Topic selection not completed")

        confirmed_topics = topic_session.confirmed_topics
        if not confirmed_topics:
            raise ValueError("No confirmed topics found")

        # Update quiz status
        update_quiz_status(topic_session.quiz_id, "ready")

        log_activity(session_id, "quiz_ready", {"quiz_id": topic_session.quiz_id})

        return {
            "confirmed_topics": confirmed_topics,
            "total_topics": len(confirmed_topics),
            "ready_for_quiz": True,
            "quiz_id": topic_session.quiz_id,
        }

    def _serialize_langgraph_state(self, state: Dict) -> Dict:
        """Serialize LangGraph state for database storage"""
        try:
            import json
            from datetime import datetime

            def serialize_obj(obj):
                if hasattr(obj, "dict"):
                    return obj.dict()
                elif hasattr(obj, "model_dump"):
                    return obj.model_dump()
                elif isinstance(obj, datetime):
                    return obj.isoformat()
                elif isinstance(obj, (list, dict, str, int, float, bool, type(None))):
                    return obj
                else:
                    # Try to convert to dict or string representation
                    try:
                        return obj.__dict__
                    except:
                        return str(obj)

            # Deep serialize the state
            serialized = {}
            for key, value in state.items():
                if isinstance(value, list):
                    serialized[key] = [serialize_obj(item) for item in value]
                elif isinstance(value, dict):
                    serialized[key] = {k: serialize_obj(v) for k, v in value.items()}
                else:
                    serialized[key] = serialize_obj(value)

            return serialized

        except Exception as e:
            logger.error(f"Failed to serialize state: {e}")
            return state  # Return original if serialization fails

    def _deserialize_langgraph_state(self, serialized_state: Dict) -> Dict:
        """Deserialize LangGraph state from database"""
        try:
            # For now, basic deserialization
            # In full implementation, would recreate proper objects
            return serialized_state
        except Exception as e:
            logger.error(f"Failed to deserialize state: {e}")
            return {}

    async def start_quiz(
        self,
        quiz_id: str,
        confirmed_topics: List[Dict],
        total_questions: int,
        difficulty: str,
        user_questions: List[str],
        session_id: str,
    ) -> str:
        """Start quiz execution using LangGraph agent"""
        try:
            # Create quiz session in database
            quiz_session = create_quiz_session(quiz_id, total_questions, difficulty)
            quiz_session_id = quiz_session.quiz_session_id

            # Convert topics to WeightedTopic objects
            weighted_topics = [WeightedTopic(**topic) for topic in confirmed_topics]

            # Create RAG retriever
            collection_name = f"quiz_{quiz_id}"
            retriever = RAGRetriever(collection_name, self.qdrant_manager)

            # Create quiz graph
            quiz_graph = create_quiz_graph(retriever)

            # Store graph instance
            self.active_quiz_graphs[quiz_session_id] = {
                "graph": quiz_graph,
                "config": {"configurable": {"thread_id": quiz_session_id}},
                "retriever": retriever,
            }

            # Create initial quiz state
            quiz_state = create_initial_quiz_state(
                confirmed_topics=weighted_topics,
                total_questions=total_questions,
                difficulty=difficulty,
                batch_size=5,
                max_incorrect_recycles=2,
                quiz_mode="fresh",
                user_questions=user_questions,
                user_id=session_id,
            )

            # Update status
            update_quiz_session(quiz_session_id, status="generating")

            # Start quiz generation in background
            self._create_background_task(
                self._run_quiz_generation(quiz_session_id, quiz_state)
            )

            log_activity(
                session_id, "quiz_started", {"quiz_session_id": quiz_session_id}
            )
            return quiz_session_id

        except Exception as e:
            logger.error(f"Failed to start quiz: {e}")
            raise

    async def _run_quiz_generation(
        self, quiz_session_id: str, initial_state: QuizState
    ):
        """Background task to generate quiz questions"""
        try:
            graph_data = self.active_quiz_graphs[quiz_session_id]
            graph = graph_data["graph"]
            config = graph_data["config"]

            # Start quiz generation
            result = graph.invoke(initial_state, config)

            # Update database with generated questions
            current_state = graph.get_state(config)

            if current_state.values.get("quiz_session"):
                quiz_session_data = current_state.values["quiz_session"]

                # Serialize quiz session data
                serialized_quiz_data = self._serialize_quiz_session(quiz_session_data)
                serialized_state = self._serialize_langgraph_state(current_state.values)

                # Determine status based on current state
                status = "active"
                if current_state.values.get("quiz_complete"):
                    status = "completed"
                elif current_state.values.get("current_question"):
                    status = "active"
                else:
                    status = "generating"

                # Store questions and state
                update_quiz_session(
                    quiz_session_id,
                    status=status,
                    questions_data=serialized_quiz_data,
                    langgraph_state=serialized_state,
                )

                logger.info(f"Quiz generation completed for session {quiz_session_id}")
            else:
                logger.error("No quiz session data found after generation")
                update_quiz_session(quiz_session_id, status="failed")

        except Exception as e:
            logger.error(f"Quiz generation failed: {e}", exc_info=True)
            update_quiz_session(quiz_session_id, status="failed")

    def _serialize_quiz_session(self, quiz_session_data) -> Dict:
        """Serialize QuizSession object for database storage"""
        try:
            if hasattr(quiz_session_data, "dict"):
                return quiz_session_data.dict()
            elif hasattr(quiz_session_data, "model_dump"):
                return quiz_session_data.model_dump()
            elif isinstance(quiz_session_data, dict):
                return quiz_session_data
            else:
                # Convert object attributes to dict
                result = {}
                for attr in dir(quiz_session_data):
                    if not attr.startswith("_") and not callable(
                        getattr(quiz_session_data, attr)
                    ):
                        try:
                            value = getattr(quiz_session_data, attr)
                            result[attr] = self._serialize_langgraph_state(
                                {"value": value}
                            )["value"]
                        except:
                            continue
                return result
        except Exception as e:
            logger.error(f"Failed to serialize quiz session: {e}")
            return {}

    def get_current_question(self, quiz_session_id: str) -> Optional[Dict]:
        """Get current question for active quiz"""
        try:
            quiz_session = get_quiz_session(quiz_session_id)
            if not quiz_session:
                return None

            # Try to get from active graph first
            if quiz_session_id in self.active_quiz_graphs:
                graph_data = self.active_quiz_graphs[quiz_session_id]
                graph = graph_data["graph"]
                config = graph_data["config"]

                current_state = graph.get_state(config)
                current_question = current_state.values.get("current_question")
                quiz_session_data = current_state.values.get("quiz_session")

            else:
                # Restore from database
                if not self._restore_quiz_session(quiz_session_id):
                    return None

                # Try again after restoration
                if quiz_session_id not in self.active_quiz_graphs:
                    logger.error(f"Failed to restore quiz session {quiz_session_id}")
                    return None

                graph_data = self.active_quiz_graphs[quiz_session_id]
                graph = graph_data["graph"]
                config = graph_data["config"]

                current_state = graph.get_state(config)
                current_question = current_state.values.get("current_question")
                quiz_session_data = current_state.values.get("quiz_session")

            if current_question and quiz_session_data:
                # Extract question data
                question_data = {
                    "id": getattr(current_question, "id", "unknown"),
                    "topic": getattr(current_question, "topic", "Unknown"),
                    "question_text": getattr(current_question, "question_text", ""),
                    "choices": [],
                    "is_multi_choice": getattr(
                        current_question, "is_multi_choice", False
                    ),
                    "difficulty": getattr(current_question, "difficulty", "medium"),
                }

                # Extract choices
                choices = getattr(current_question, "choices", [])
                for choice in choices:
                    choice_data = {
                        "text": getattr(choice, "text", ""),
                        "is_correct": getattr(choice, "is_correct", False),
                    }
                    question_data["choices"].append(choice_data)

                # Calculate progress
                current_index = getattr(quiz_session_data, "current_question_index", 0)
                active_pool = getattr(quiz_session_data, "active_question_pool", [])
                user_answers = getattr(quiz_session_data, "user_answers", [])

                progress = {
                    "current_question_number": current_index + 1,
                    "total_questions": len(active_pool),
                    "answered": current_index,
                    "correct": len(
                        [a for a in user_answers if getattr(a, "is_correct", False)]
                    ),
                }

                return {
                    "current_question": question_data,
                    "progress": progress,
                    "status": quiz_session.status,
                }

            # No current question - check if quiz is completed
            if quiz_session.status == "completed":
                return {
                    "current_question": None,
                    "progress": self._get_final_progress(quiz_session_id),
                    "status": "completed",
                }

            return None

        except Exception as e:
            logger.error(f"Failed to get current question: {e}", exc_info=True)
            return None

    def _get_final_progress(self, quiz_session_id: str) -> Dict:
        """Get final progress for completed quiz"""
        try:
            quiz_session = get_quiz_session(quiz_session_id)
            if not quiz_session or not quiz_session.questions_data:
                return {"answered": 0, "correct": 0, "total_questions": 0}

            questions_data = quiz_session.questions_data
            user_answers = questions_data.get("user_answers", [])

            total_answered = len(
                [a for a in user_answers if a.get("attempt_number", 1) == 1]
            )
            correct_answers = len(
                [
                    a
                    for a in user_answers
                    if a.get("is_correct", False) and a.get("attempt_number", 1) == 1
                ]
            )

            return {
                "answered": total_answered,
                "correct": correct_answers,
                "total_questions": total_answered,
                "score_percentage": (correct_answers / max(total_answered, 1)) * 100,
            }

        except Exception as e:
            logger.error(f"Failed to get final progress: {e}")
            return {"answered": 0, "correct": 0, "total_questions": 0}

    async def submit_answer(
        self,
        quiz_session_id: str,
        selected_choices: List[int],
        question_id: str,
        session_id: str,
    ) -> Dict:
        """Submit answer to current question"""
        try:
            # Ensure graph is available
            if quiz_session_id not in self.active_quiz_graphs:
                if not self._restore_quiz_session(quiz_session_id):
                    raise ValueError("Quiz session not found or expired")

            graph_data = self.active_quiz_graphs[quiz_session_id]
            graph = graph_data["graph"]
            config = graph_data["config"]

            # Get current state before submitting answer
            current_state = graph.get_state(config)
            current_question = current_state.values.get("current_question")

            if not current_question:
                raise ValueError("No current question found")

            # Validate question ID matches
            if getattr(current_question, "id", "") != question_id:
                raise ValueError("Question ID mismatch")

            # Validate selected choices
            choices = getattr(current_question, "choices", [])
            if not choices:
                raise ValueError("Question has no choices")

            for choice_idx in selected_choices:
                if choice_idx < 0 or choice_idx >= len(choices):
                    raise ValueError(f"Choice index {choice_idx} out of range")

            # Determine if answer is correct
            correct_indices = []
            for i, choice in enumerate(choices):
                if getattr(choice, "is_correct", False):
                    correct_indices.append(i)

            is_correct = set(selected_choices) == set(correct_indices)

            # Get selected and correct answer texts
            selected_texts = [
                getattr(choices[i], "text", f"Choice {i+1}") for i in selected_choices
            ]
            correct_texts = [
                getattr(choices[i], "text", f"Choice {i+1}") for i in correct_indices
            ]

            # Submit answer to graph
            graph.update_state(config, {"user_input": selected_choices})
            result = graph.invoke(None, config)

            # Get updated state
            updated_state = graph.get_state(config)
            quiz_session_data = updated_state.values.get("quiz_session")

            # Create detailed feedback
            explanation = getattr(
                current_question, "explanation", "No explanation available"
            )

            feedback_text = ""
            if is_correct:
                feedback_text = f"✅ Correct! You selected: {', '.join(selected_texts)}"
            else:
                feedback_text = f"❌ Incorrect. You selected: {', '.join(selected_texts)}\nCorrect answer(s): {', '.join(correct_texts)}"

            feedback_text += f"\n\n📖 Explanation: {explanation}"

            # Determine if more questions are available
            next_question_available = True
            if quiz_session_data:
                current_index = getattr(quiz_session_data, "current_question_index", 0)
                active_pool = getattr(quiz_session_data, "active_question_pool", [])
                next_question_available = current_index < len(active_pool)

            # Calculate updated progress
            progress = {}
            if quiz_session_data:
                user_answers = getattr(quiz_session_data, "user_answers", [])
                first_attempt_answers = [
                    a for a in user_answers if getattr(a, "attempt_number", 1) == 1
                ]
                correct_first_attempts = [
                    a for a in first_attempt_answers if getattr(a, "is_correct", False)
                ]

                progress = {
                    "answered": len(first_attempt_answers),
                    "correct": len(correct_first_attempts),
                    "total_questions": len(
                        getattr(quiz_session_data, "active_question_pool", [])
                    ),
                    "score_percentage": (
                        len(correct_first_attempts) / max(len(first_attempt_answers), 1)
                    )
                    * 100,
                }

            # Update database with new state
            serialized_state = self._serialize_langgraph_state(updated_state.values)
            serialized_quiz_data = (
                self._serialize_quiz_session(quiz_session_data)
                if quiz_session_data
                else {}
            )

            # Update status if quiz is completed
            status = "active"
            if not next_question_available:
                status = "completed"

            update_quiz_session(
                quiz_session_id,
                status=status,
                questions_data=serialized_quiz_data,
                langgraph_state=serialized_state,
                current_question_index=(
                    getattr(quiz_session_data, "current_question_index", 0)
                    if quiz_session_data
                    else 0
                ),
            )

            # Log activity
            log_activity(
                session_id,
                "answer_submitted",
                {
                    "quiz_session_id": quiz_session_id,
                    "question_id": question_id,
                    "selected_choices": selected_choices,
                    "is_correct": is_correct,
                },
            )

            return {
                "correct": is_correct,
                "explanation": feedback_text,
                "selected_answers": selected_texts,
                "correct_answers": correct_texts,
                "next_question_available": next_question_available,
                "progress": progress,
                "quiz_completed": status == "completed",
            }

        except ValueError as e:
            logger.warning(f"Invalid answer submission: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to submit answer: {e}", exc_info=True)
            raise

    def _restore_quiz_session(self, quiz_session_id: str) -> bool:
        """Restore quiz session from database"""
        try:
            quiz_session = get_quiz_session(quiz_session_id)
            if not quiz_session or not quiz_session.langgraph_state:
                logger.error(f"No quiz session or state found for {quiz_session_id}")
                return False

            # Get the quiz to find collection
            from ..database.crud import get_quiz

            quiz = get_quiz(quiz_session.quiz_id)
            if not quiz or not quiz.collection_name:
                logger.error(
                    f"No quiz or collection found for session {quiz_session_id}"
                )
                return False

            # Recreate RAG retriever
            retriever = RAGRetriever(quiz.collection_name, self.qdrant_manager)

            # Recreate quiz graph
            quiz_graph = create_quiz_graph(retriever)

            # Restore graph config
            config = {"configurable": {"thread_id": quiz_session_id}}

            # Deserialize and restore state
            restored_state = self._deserialize_langgraph_state(
                quiz_session.langgraph_state
            )

            # Try to restore the graph state
            try:
                # Update the graph state with restored data
                graph_state_updates = {}

                # Restore key state components
                if "quiz_session" in restored_state:
                    graph_state_updates["quiz_session"] = restored_state["quiz_session"]
                if "current_question" in restored_state:
                    graph_state_updates["current_question"] = restored_state[
                        "current_question"
                    ]
                if "questions_to_generate" in restored_state:
                    graph_state_updates["questions_to_generate"] = restored_state[
                        "questions_to_generate"
                    ]

                # Update graph state
                if graph_state_updates:
                    quiz_graph.update_state(config, graph_state_updates)

                # Store in active graphs
                self.active_quiz_graphs[quiz_session_id] = {
                    "graph": quiz_graph,
                    "config": config,
                    "retriever": retriever,
                }

                logger.info(f"Successfully restored quiz session {quiz_session_id}")
                return True

            except Exception as e:
                logger.error(f"Failed to restore graph state: {e}")
                # Fallback: create new graph instance but don't fail completely
                self.active_quiz_graphs[quiz_session_id] = {
                    "graph": quiz_graph,
                    "config": config,
                    "retriever": retriever,
                }
                return True

        except Exception as e:
            logger.error(
                f"Failed to restore quiz session {quiz_session_id}: {e}", exc_info=True
            )
            return False

    # Utility Methods
    def get_quiz_session(self, quiz_session_id: str):
        """Get quiz session from database"""
        return get_quiz_session(quiz_session_id)

    def cleanup_session(self, session_id: str):
        """Clean up session-related graph instances"""
        # Clean up topic graphs
        topic_sessions_to_remove = []
        for topic_session_id, graph_data in self.active_topic_graphs.items():
            # Check if this topic session belongs to the session
            topic_session = get_topic_session(topic_session_id)
            if topic_session:
                quiz = get_quiz(topic_session.quiz_id)
                if quiz and quiz.session_id == session_id:
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
                if quiz and quiz.session_id == session_id:
                    quiz_sessions_to_remove.append(quiz_session_id)

        for quiz_session_id in quiz_sessions_to_remove:
            del self.active_quiz_graphs[quiz_session_id]
            logger.info(f"Cleaned up quiz graph for session {quiz_session_id}")

    def cleanup_expired_graphs(self, max_age_hours: int = 24):
        """Clean up graphs that haven't been used recently"""
        from datetime import datetime, timedelta

        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)

        # Clean up old topic graphs
        expired_topic_sessions = []
        for topic_session_id in self.active_topic_graphs.keys():
            topic_session = get_topic_session(topic_session_id)
            if not topic_session or topic_session.updated_at < cutoff_time:
                expired_topic_sessions.append(topic_session_id)

        for topic_session_id in expired_topic_sessions:
            del self.active_topic_graphs[topic_session_id]
            logger.info(f"Cleaned up expired topic graph {topic_session_id}")

        # Clean up old quiz graphs
        expired_quiz_sessions = []
        for quiz_session_id in self.active_quiz_graphs.keys():
            quiz_session = get_quiz_session(quiz_session_id)
            if not quiz_session or quiz_session.updated_at < cutoff_time:
                expired_quiz_sessions.append(quiz_session_id)

        for quiz_session_id in expired_quiz_sessions:
            del self.active_quiz_graphs[quiz_session_id]
            logger.info(f"Cleaned up expired quiz graph {quiz_session_id}")

        logger.info(
            f"Cleanup completed. Active graphs: {len(self.active_topic_graphs)} topic, {len(self.active_quiz_graphs)} quiz"
        )
