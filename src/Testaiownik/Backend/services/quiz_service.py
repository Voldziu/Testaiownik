# src/Testaiownik/Backend/services/quiz_service.py
from typing import List, Dict, Optional, Any
import asyncio

import uuid
from datetime import datetime
from sqlalchemy.orm import Session


from Agent.TopicSelection import create_agent_graph
from Agent.Quiz import create_quiz_graph, create_initial_quiz_state
from Agent.Shared import WeightedTopic
from Agent.Quiz.models import SourceMetadata as AgentSourceMetadata
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
    reset_quiz_execution,
    soft_reset_quiz_execution,
)

from ..models.responses import (
    QuizCurrentResponse,
    QuizAnswerResponse,
    QuizResultsResponse,
    QuestionResponse,
    QuestionChoice,
    QuizProgressResponse,
    QuizResults,
    TopicScore,
    SourceMetadata,
)
from utils import logger


class QuizService:
    """Service layer for quiz operations with actual LangGraph integration"""

    def __init__(self):
        self.active_topic_graphs = {}  
        self.active_quiz_graphs = {}  
        self.qdrant_manager = QdrantManager()

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

    def start_topic_analysis(
        self, quiz_id: str, user_id: str, db: Session, desired_topic_count: int = 10
    ) -> Dict:
        """Start topic analysis using LangGraph agent"""
        try:
            quiz = get_quiz(db, quiz_id)
            if not quiz:
                raise ValueError("Quiz not found")

            from ..database.crud import start_topic_analysis

            success = start_topic_analysis(db, quiz_id, desired_topic_count)
            if not success:
                raise ValueError("Failed to initialize topic analysis")

            collection_name = quiz.collection_name
            if not collection_name:
                raise ValueError("Quiz collection not found")

            retriever = RAGRetriever(collection_name, self.qdrant_manager)

            topic_graph = create_agent_graph(retriever)
            config = {"configurable": {"thread_id": quiz_id}}

            self.active_topic_graphs[quiz_id] = {
                "graph": topic_graph,
                "config": config,
                "retriever": retriever,
            }

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

            logger.info(f"Running topic analysis for quiz {quiz_id}")
            result = topic_graph.invoke(initial_state, config)

            current_state = topic_graph.get_state(config)

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
                        suggested_topics.append(
                            {
                                "topic": getattr(topic, "topic", str(topic)),
                                "weight": getattr(topic, "weight", 1.0),
                            }
                        )

            serialized_state = self._serialize_langgraph_state(current_state)

            update_topic_data(
                db,
                quiz_id,
                status="topic_feedback",
                suggested_topics=suggested_topics,
                topic_feedback_request=current_state.values.get("feedback_request"),
                topic_conversation_history=current_state.values.get(
                    "conversation_history", []
                ),
                langgraph_topic_state=serialized_state,
            )
            db.refresh(quiz)  

            log_activity(
                db,
                user_id,
                "topic_analysis_completed", 
                {"quiz_id": quiz_id, "topic_count": len(suggested_topics)},
            )

            logger.info(
                f"Topic analysis completed for quiz {quiz_id}. Found {len(suggested_topics)} topics"
            )

            return {
                "quiz_id": quiz_id,
                "status": "topic_feedback",
                "suggested_topics": suggested_topics,
                "feedback_request": current_state.values.get("feedback_request"),
            }

        except Exception as e:
            logger.error(f"Failed to start topic analysis: {e}")
            update_quiz(db, quiz_id, status="failed")
            raise

    def _serialize_langgraph_state(self, state) -> Dict:
        """Serialize LangGraph state for database storage"""
        try:
            return {
                "values": self._serialize_dict(state.values),
                "next": state.next,
                "config": state.config,
            }
        except Exception as e:
            logger.warning(f"Failed to serialize state: {e}")
            return {}

    def _serialize_dict(self, data) -> Dict:
        """Recursively serialize dictionary for JSON storage with proper datetime handling"""
        if not isinstance(data, dict):
            return self._serialize_value(data)

        result = {}
        for key, value in data.items():
            try:
                result[key] = self._serialize_value(value)
            except Exception as e:
                logger.warning(f"Failed to serialize key '{key}': {e}")
                result[key] = str(value)
        logger.debug(f"Succesfully serialized dict: {result}")
        return result

    def _serialize_value(self, value):
        """Serialize individual values with comprehensive type handling"""
        try:
            if value is None:
                return None

            if isinstance(value, datetime):
                return value.isoformat()

            if hasattr(value, "model_dump"):
                serialized = value.model_dump()
                return self._serialize_dict(serialized)

            if hasattr(value, "dict"):
                serialized = value.dict()
                return self._serialize_dict(serialized)

            if isinstance(value, list):
                return [self._serialize_value(item) for item in value]

            if isinstance(value, dict):
                return self._serialize_dict(value)

            if isinstance(value, (str, int, float, bool)):
                return value

            return str(value)

        except Exception as e:
            logger.warning(f"Failed to serialize value {type(value)}: {e}")
            return str(value)

    async def submit_topic_feedback(
        self, quiz_id: str, user_input: str, user_id: str, db: Session
    ) -> Dict:
        """Process user feedback on topics"""
        try:
            quiz = get_quiz(db, quiz_id)
            if not quiz:
                raise ValueError("Quiz not found")

            if quiz_id not in self.active_topic_graphs:
                if not self._restore_topic_session(quiz_id, db):
                    raise ValueError("Cannot restore topic session")

            graph_data = self.active_topic_graphs[quiz_id]
            graph = graph_data["graph"]
            config = graph_data["config"]

            graph.update_state(config, {"user_input": user_input})
            result = graph.invoke(None, config)

            current_state = graph.get_state(config)

            suggested_topics = self._extract_topics_from_state(current_state)
            serialized_state = self._serialize_langgraph_state(current_state)

            conversation_history = current_state.values.get("conversation_history", [])
            serialized_history = []

            for item in conversation_history:
                try:
                    if isinstance(item, dict):
                        serialized_item = {}
                        for k, v in item.items():
                            if k == "suggested_topics" and isinstance(v, list):
                                serialized_topics = []
                                for topic in v:
                                    try:
                                        if hasattr(topic, "model_dump"):
                                            serialized_topics.append(topic.model_dump())
                                        elif hasattr(topic, "dict"):
                                            serialized_topics.append(topic.dict())
                                        elif isinstance(topic, dict):
                                            serialized_topics.append(topic)
                                        else:
                                            serialized_topics.append(
                                                {
                                                    "topic": getattr(
                                                        topic, "topic", str(topic)
                                                    ),
                                                    "weight": getattr(
                                                        topic, "weight", 1.0
                                                    ),
                                                }
                                            )
                                    except Exception as e:
                                        logger.warning(
                                            f"Failed to serialize topic in history: {e}"
                                        )
                                        serialized_topics.append(
                                            {"topic": str(topic), "weight": 1.0}
                                        )
                                serialized_item[k] = serialized_topics
                            else:
                                serialized_item[k] = self._serialize_value(v)
                        serialized_history.append(serialized_item)
                    else:
                        serialized_history.append(self._serialize_value(item))
                except Exception as e:
                    logger.warning(f"Failed to serialize history item: {e}")
                    serialized_history.append(str(item))

            update_topic_data(
                db,
                quiz_id,
                suggested_topics=suggested_topics,
                topic_feedback_request=current_state.values.get("feedback_request"),
                topic_conversation_history=serialized_history,
                langgraph_topic_state=serialized_state,
            )

            log_activity(
                db,
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
                try:
                    if hasattr(topic, "model_dump"):
                        topics.append(topic.model_dump())
                    elif hasattr(topic, "dict"):
                        topics.append(topic.dict())
                    elif isinstance(topic, dict):
                        topics.append(topic)
                    else:
                        topic_dict = {
                            "topic": getattr(topic, "topic", str(topic)),
                            "weight": getattr(topic, "weight", 1.0),
                        }
                        topics.append(topic_dict)
                except Exception as e:
                    logger.warning(f"Failed to serialize topic {topic}: {e}")
                    topics.append({"topic": str(topic), "weight": 1.0})
        return topics

    def _restore_topic_session(self, quiz_id: str, db: Session) -> bool:
        """Restore topic session from database state"""
        try:
            quiz = get_quiz(db, quiz_id)
            if not quiz or not quiz.langgraph_topic_state:
                return False

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

    def confirm_topics(self, quiz_id: str, user_id: str, db: Session) -> Dict:
        """Confirm final topic selection"""
        try:
            quiz = get_quiz(db, quiz_id)
            if not quiz:
                raise ValueError("Quiz not found")

            if not quiz.suggested_topics:
                raise ValueError("No topics available to confirm")

            confirmed_topics = quiz.suggested_topics.copy()

            success = confirm_quiz_topics(db, quiz_id, confirmed_topics)
            if not success:
                raise ValueError("Failed to confirm topics")

            log_activity(
                db,
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

    async def start_quiz(
        self,
        quiz_id: str,
        confirmed_topics: List[Dict],
        total_questions: int,
        difficulty: str,
        user_questions: List[str],
        user_id: str,
        db: Session,
    ) -> bool:
        """Start quiz execution with confirmed topics"""
        try:
            success = start_quiz_execution(db, quiz_id, total_questions, difficulty)
            if not success:
                raise ValueError("Failed to start quiz execution")

            self._create_background_task(
                self._generate_quiz_questions(
                    quiz_id,
                    user_id,
                    confirmed_topics,
                    total_questions,
                    difficulty,
                    user_questions,
                    db,
                )
            )

            log_activity(
                db,
                user_id,
                "quiz_started",
                {"quiz_id": quiz_id},
            )

            return True

        except Exception as e:
            logger.error(f"Failed to start quiz: {e}")
            raise

    async def _generate_quiz_questions(
        self,
        quiz_id: str,
        user_id: str,
        confirmed_topics: List[Dict],
        total_questions: int,
        difficulty: str,
        user_questions: List[str],
        db: Session,
    ):
        """Background task to generate quiz questions using LangGraph"""
        try:
            logger.info(f"Starting question generation for quiz {quiz_id}")

            quiz = get_quiz(db, quiz_id)
            if not quiz:
                raise ValueError("Quiz not found")

            collection_name = quiz.collection_name
            if not collection_name:
                raise ValueError("Quiz collection not found")

            retriever = RAGRetriever(collection_name, self.qdrant_manager)

            weighted_topics = []
            for topic_data in confirmed_topics:
                weighted_topics.append(
                    WeightedTopic(
                        topic=topic_data.get("topic", ""),
                        weight=topic_data.get("weight", 1.0),
                    )
                )

            quiz_graph = create_quiz_graph(retriever)
            config = {"configurable": {"thread_id": f"quiz_{quiz_id}"}}

            quiz_state = create_initial_quiz_state(
                confirmed_topics=weighted_topics,
                total_questions=total_questions,
                difficulty=difficulty,
                batch_size=5,
                copies_per_incorrect_answer=2,
                quiz_mode="fresh",
                user_questions=user_questions,
                user_id=user_id,
            )

            self.active_quiz_graphs[quiz_id] = {
                "graph": quiz_graph,
                "config": config,
                "retriever": retriever,
            }

            logger.info(f"Running quiz graph until first interrupt...")

            result = quiz_graph.invoke(quiz_state, config)

            final_state = quiz_graph.get_state(config)

            if final_state.next and "process_answer" in final_state.next:
                logger.info(
                    "Quiz graph correctly interrupted at process_answer - questions generated and first question presented"
                )
            else:
                logger.warning(
                    f"Quiz graph in unexpected state after interrupt: {final_state.next}"
                )

            quiz_session = final_state.values.get("quiz_session")

            if not quiz_session:
                logger.error("Quiz session not found in interrupted state")
                logger.debug(
                    f"Available state keys: {list(final_state.values.keys()) if final_state.values else 'No values'}"
                )
                raise ValueError("Quiz session not created")

            if not quiz_session.all_generated_questions:
                raise ValueError("No questions were generated")

            if not quiz_session.active_question_pool:
                raise ValueError("No active question pool created")

            logger.info(
                f"Quiz ready - questions generated and first question presented. Graph is correctly interrupted and waiting for user input."
            )

            questions_data = {
                "session_id": quiz_session.session_id,
                "all_generated_questions": [
                    self._serialize_question(q)
                    for q in quiz_session.all_generated_questions
                ],
                "active_question_pool": quiz_session.active_question_pool,
                "questions_per_topic": quiz_session.questions_per_topic,
            }

            serialized_questions = self._serialize_dict(questions_data)
            serialized_state = self._serialize_dict(
                self._serialize_langgraph_state(final_state)
            )

            update_quiz_progress(
                db,
                quiz_id,
                questions_data=serialized_questions,
                current_question_index=0,  
                langgraph_quiz_state=serialized_state,
            )

            update_quiz(db, quiz_id, status="quiz_active")

            logger.info(
                f"Quiz questions generated successfully for {quiz_id}. "
                f"Total questions: {len(quiz_session.all_generated_questions)}, "
                f"Active pool: {len(quiz_session.active_question_pool)}"
            )

        except Exception as e:
            logger.error(f"Failed to generate quiz questions for {quiz_id}: {e}")
            update_quiz(db, quiz_id, status="failed")
            if quiz_id in self.active_quiz_graphs:
                del self.active_quiz_graphs[quiz_id]
            raise

    def _serialize_question(self, question) -> Dict:
        """Serialize Question object for database storage"""


        if hasattr(question, "model_dump"):
            data = question.model_dump()
            if "generated_at" in data and hasattr(data["generated_at"], "isoformat"):
                data["generated_at"] = data["generated_at"].isoformat()

            return data

        elif hasattr(question, "dict"):
            data = question.dict()
            if "generated_at" in data and hasattr(data["generated_at"], "isoformat"):
                data["generated_at"] = data["generated_at"].isoformat()
            return data
        else:
            generated_at = getattr(question, "generated_at", datetime.now())
            generated_at_str = (
                generated_at.isoformat()
                if hasattr(generated_at, "isoformat")
                else str(datetime.now())
            )

            source_metadata = getattr(question, "source_metadata", None)
            serialized_source_metadata = None

            if source_metadata:
                if hasattr(source_metadata, "model_dump"):
                    serialized_source_metadata = source_metadata.model_dump()
                elif hasattr(source_metadata, "dict"):
                    serialized_source_metadata = source_metadata.dict()
                elif isinstance(source_metadata, dict):
                    serialized_source_metadata = source_metadata
                else:
                    serialized_source_metadata = {
                        "source": getattr(source_metadata, "source", "Unknown"),
                        "page": getattr(source_metadata, "page", None),
                        "slide": getattr(source_metadata, "slide", None),
                        "chunk_text": getattr(source_metadata, "chunk_text", None),
                    }
           

            return {
                "id": getattr(question, "id", str(uuid.uuid4())),
                "topic": getattr(question, "topic", ""),
                "question_text": getattr(question, "question_text", ""),
                "choices": [
                    {
                        "text": choice.text if hasattr(choice, "text") else str(choice),
                        "is_correct": getattr(choice, "is_correct", False),
                    }
                    for choice in getattr(question, "choices", [])
                ],
                "explanation": getattr(question, "explanation", ""),
                "difficulty": getattr(question, "difficulty", "medium"),
                "is_multi_choice": getattr(question, "is_multi_choice", False),
                "generated_at": generated_at_str,
                "source_metadata": serialized_source_metadata,
            }

    def get_quiz_progress(self, quiz) -> Dict:
        questions_data = quiz.questions_data or {}
        all_questions = questions_data.get("all_generated_questions", [])
        user_answers = quiz.user_answers or []
        active_pool = questions_data.get("active_question_pool", [])

        total_attempts = len(user_answers)
        correct_attempts = sum(1 for answer in user_answers if answer.get("is_correct"))

        answered_unique_questions = set()
        correct_unique_questions = set()

        for answer in user_answers:
            question_id = answer.get("question_id")

            answered_unique_questions.add(question_id)
            if answer.get("is_correct"):
                correct_unique_questions.add(question_id)

        total_unique_questions = len(set(active_pool))  
        unique_answered = len(answered_unique_questions)
        unique_correct = len(correct_unique_questions)
        remaining_unique = max(0, total_unique_questions - unique_answered)

        attempt_success_rate = (
            (correct_attempts / total_attempts * 100) if total_attempts > 0 else 0
        )
        unique_question_success_rate = (
            (unique_correct / unique_answered * 100) if unique_answered > 0 else 0
        )

        current_position = min(quiz.current_question_index + 1, total_unique_questions)

        topic_progress = {}
        if quiz.confirmed_topics and all_questions:
            question_to_topic = {q.get("id"): q.get("topic") for q in all_questions}

            for topic_data in quiz.confirmed_topics:
                topic_name = topic_data.get("topic", "Unknown")

                topic_questions_in_pool = [
                    q_id
                    for q_id in set(active_pool)
                    if question_to_topic.get(q_id) == topic_name
                ]

                topic_attempts = 0
                topic_correct_attempts = 0
                topic_unique_answered = set()
                topic_unique_correct = set()

                for answer in user_answers:
                    question_id = answer.get("question_id")
                    if question_id in topic_questions_in_pool:
                        topic_attempts += 1
                        if answer.get("is_correct"):
                            topic_correct_attempts += 1

                        if answer.get("attempt_number", 1) == 1:
                            topic_unique_answered.add(question_id)
                            if answer.get("is_correct"):
                                topic_unique_correct.add(question_id)

                topic_total_unique = len(topic_questions_in_pool)
                topic_answered_unique = len(topic_unique_answered)
                topic_correct_unique = len(topic_unique_correct)

                topic_progress[topic_name] = {
                    "unique_answered": topic_answered_unique,
                    "unique_correct": topic_correct_unique,
                    "total_unique": topic_total_unique,
                    "remaining_unique": max(
                        0, topic_total_unique - topic_answered_unique
                    ),
                    "total_attempts": topic_attempts,
                    "correct_attempts": topic_correct_attempts,
                    "unique_success_rate": (
                        (topic_correct_unique / topic_answered_unique * 100)
                        if topic_answered_unique > 0
                        else 0
                    ),
                    "attempt_success_rate": (
                        (topic_correct_attempts / topic_attempts * 100)
                        if topic_attempts > 0
                        else 0
                    ),
                }

        time_elapsed_seconds = 0
        if quiz.quiz_started_at:
            time_elapsed_seconds = int(
                (datetime.now() - quiz.quiz_started_at).total_seconds()
            )

        avg_time_per_attempt = (
            (time_elapsed_seconds / total_attempts) if total_attempts > 0 else 0
        )
        avg_time_per_unique = (
            (time_elapsed_seconds / unique_answered) if unique_answered > 0 else 0
        )

        total_incorrect_attempts = sum(
            1 for answer in user_answers if not answer.get("is_correct")
        )

        return {
            "progress": {
                "total_questions_in_pool": len(active_pool),  
                "remaining_questions": max(
                    0, len(active_pool) - total_attempts
                ), 
                "total_attemps": total_attempts,
                "total_incorrect_attemps": total_incorrect_attempts,
                "total_corrent_attemps": correct_attempts,
                "current_question": current_position,
                "total_unique_questions": total_unique_questions,
                "unique_answered": unique_answered,
                "unique_correct": unique_correct,
                "remaining_unique": remaining_unique,
                "unique_success_rate": round(unique_question_success_rate, 1),
                "attempt_success_rate": round(attempt_success_rate, 1),
                "time_elapsed_seconds": time_elapsed_seconds,
                "average_time_per_attempt": round(avg_time_per_attempt, 1),
                "average_time_per_unique_question": round(avg_time_per_unique, 1),
                "topic_progress": topic_progress,
            },
            "status": quiz.status,
            "quiz_metadata": {
                "difficulty": quiz.difficulty,
                "total_questions_generated": len(all_questions),
                "recycling_enabled": True,
            },
        }

    def get_current_question(
        self, quiz_id: str, db: Session
    ) -> Optional[QuizCurrentResponse]:
        """Get current question for quiz using interrupt system"""
        try:
            quiz = get_quiz(db, quiz_id)
            if not quiz:
                return None

            if quiz_id in self.active_quiz_graphs:
                graph_data = self.active_quiz_graphs[quiz_id]
                graph = graph_data["graph"]
                config = graph_data["config"]

                try:
                    current_state = graph.get_state(config)

                    if current_state.next and "process_answer" in current_state.next:
                        quiz_session = current_state.values.get("quiz_session")
                        current_question = current_state.values.get("current_question")

                        if quiz_session and current_question:
                            return self._format_current_question_response(
                                current_question, quiz_session
                            )

                except Exception as e:
                    logger.warning(
                        f"Could not get question from interrupted graph state: {e}"
                    )

            questions_data = quiz.questions_data
            if not questions_data or not questions_data.get("all_generated_questions"):
                return None

            current_index = quiz.current_question_index
            active_pool = questions_data.get("active_question_pool", [])

            if current_index >= len(active_pool):
                return None

            current_question_id = active_pool[current_index]

            current_question_data = None
            for q in questions_data.get("all_generated_questions", []):
                if q.get("id") == current_question_id:
                    current_question_data = q
                    break

            if not current_question_data:
                return None

            choices = [
                QuestionChoice(
                    text=choice.get("text", ""),
                    is_correct=choice.get("is_correct", False),
                )
                for choice in current_question_data.get("choices", [])
            ]

            logger.debug(
                f"Get current question question.source_metadata: {current_question_data['source_metadata']}"
            )

            source_metadata = self._parse_source_metadata(
                current_question_data.get("source_metadata")
            )

            logger.debug(f"Get current question source_metadata: {source_metadata}")

            current_question = QuestionResponse(
                id=current_question_data.get("id"),
                topic=current_question_data.get("topic"),
                question_text=current_question_data.get("question_text"),
                choices=choices,
                is_multi_choice=current_question_data.get("is_multi_choice", False),
                difficulty=current_question_data.get("difficulty", "medium"),
                source_metadata=source_metadata,
            )

            total_questions = len(active_pool)
            answered_unique = len(
                set(
                    answer.get("question_id")
                    for answer in (quiz.user_answers or [])
                    if answer.get("attempt_number", 1) == 1
                )
            )
            correct_unique = len(
                set(
                    answer.get("question_id")
                    for answer in (quiz.user_answers or [])
                    if answer.get("attempt_number", 1) == 1 and answer.get("is_correct")
                )
            )

            progress = QuizProgressResponse(
                current_question_number=current_index + 1,
                total_questions=total_questions,
                answered=answered_unique,
                correct=correct_unique,
            )

            return QuizCurrentResponse(
                current_question=current_question, progress=progress, status=quiz.status
            )

        except Exception as e:
            logger.error(f"Failed to get current question: {e}")
            return None

    def _format_current_question_response(
        self, question, quiz_session
    ) -> QuizCurrentResponse:
        """Format current question response from LangGraph question object"""
        try:
            choices = [
                QuestionChoice(text=choice.text, is_correct=choice.is_correct)
                for choice in question.choices
            ]

            logger.debug(f"Question: {question}")

            source_metadata = None
            logger.debug(
                f"Source_metadata from question.source_metadata: {question.source_metadata}"
            )
            if hasattr(question, "source_metadata") and question.source_metadata:
                source_metadata = self._parse_source_metadata(question.source_metadata)

            logger.debug(
                f"Source metadata from _format_current_question_response: {source_metadata}"
            )

            current_question = QuestionResponse(
                id=question.id,
                topic=question.topic,
                question_text=question.question_text,
                choices=choices,
                is_multi_choice=question.is_multi_choice,
                difficulty=question.difficulty,
                source_metadata=source_metadata,
            )

            total_questions = len(set(quiz_session.active_question_pool))
            answered_unique = len(
                set(
                    answer.question_id
                    for answer in quiz_session.user_answers
                    if answer.attempt_number == 1
                )
            )
            correct_unique = len(
                set(
                    answer.question_id
                    for answer in quiz_session.user_answers
                    if answer.attempt_number == 1 and answer.is_correct
                )
            )

            progress = QuizProgressResponse(
                current_question_number=quiz_session.current_question_index + 1,
                total_questions=total_questions,
                answered=answered_unique,
                correct=correct_unique,
            )

            return QuizCurrentResponse(
                current_question=current_question,
                progress=progress,
                status=quiz_session.status,
            )

        except Exception as e:
            logger.error(f"Failed to format current question response: {e}")
            raise

    async def submit_answer(
        self, quiz_id: str, selected_choices: List[int], question_id: str, db: Session
    ) -> QuizAnswerResponse:
        """Submit answer to current question using LangGraph interrupt system"""
        try:
            quiz = get_quiz(db, quiz_id)
            if not quiz:
                raise ValueError("Quiz not found")

            if quiz_id not in self.active_quiz_graphs:
                if not await self._restore_quiz_session(quiz_id, db):
                    raise ValueError("Cannot restore quiz session")

            graph_data = self.active_quiz_graphs[quiz_id]
            graph = graph_data["graph"]
            config = graph_data["config"]

            current_state = graph.get_state(config)

            if not current_state.next or "process_answer" not in current_state.next:
                raise ValueError(
                    f"Quiz graph not in expected interrupted state. Current: {current_state.next}"
                )

            graph.update_state(config, {"user_input": selected_choices})

            result = graph.invoke(None, config)

            updated_state = graph.get_state(config)

            if not updated_state.next or updated_state.next == ():
                is_interrupted_again = False
                is_completed = True
            else:
                is_interrupted_again = "process_answer" in updated_state.next
                is_completed = False

            quiz_session = updated_state.values.get("quiz_session")
            if not quiz_session:
                raise ValueError("Quiz session lost during processing")

            feedback_request = updated_state.values.get("feedback_request", "")

            latest_answer = None
            if quiz_session.user_answers:
                latest_answer = quiz_session.user_answers[-1]

            if not latest_answer:
                raise ValueError("No answer recorded")

            await self._update_quiz_from_session(
                quiz_id, quiz_session, updated_state, db
            )

            if is_completed:
                complete_quiz(db, quiz_id)
                logger.info(f"Quiz {quiz_id} completed")

            return await self._format_answer_response(
                latest_answer,
                feedback_request,
                is_interrupted_again,
                quiz_session,
                question_id,
            )

        except Exception as e:
            logger.error(f"Failed to submit answer: {e}")
            raise

    async def _restore_quiz_session(self, quiz_id: str, db: Session) -> bool:
        """Restore quiz session from database state"""
        try:
            quiz = get_quiz(db, quiz_id)
            if not quiz:
                return False

            if not quiz.langgraph_quiz_state:
                if quiz.questions_data:
                    return await self._restore_from_questions_data(quiz_id, quiz, db)
                else:
                    logger.warning(
                        f"No state or questions data found for quiz {quiz_id}"
                    )
                    return False

            collection_name = quiz.collection_name
            if not collection_name:
                return False

            retriever = RAGRetriever(collection_name, self.qdrant_manager)

            quiz_graph = create_quiz_graph(retriever)
            config = {"configurable": {"thread_id": f"quiz_{quiz_id}"}}

            try:
                questions_data = quiz.questions_data or {}
                user_answers = quiz.user_answers or []

                from Agent.Quiz.models import QuizSession, UserAnswer, Question
                from Agent.Shared import WeightedTopic
                from datetime import datetime

                topics = []
                if quiz.confirmed_topics:
                    for topic_data in quiz.confirmed_topics:
                        topics.append(
                            WeightedTopic(
                                topic=topic_data.get("topic", ""),
                                weight=topic_data.get("weight", 1.0),
                            )
                        )

                all_questions = []
                if questions_data.get("all_generated_questions"):
                    for q_data in questions_data["all_generated_questions"]:
                        from Agent.Quiz.models import QuestionChoice

                        choices = [
                            QuestionChoice(
                                text=choice.get("text", ""),
                                is_correct=choice.get("is_correct", False),
                            )
                            for choice in q_data.get("choices", [])
                        ]

                        generated_at = datetime.now()
                        if q_data.get("generated_at"):
                            try:
                                generated_at = datetime.fromisoformat(
                                    q_data["generated_at"]
                                )
                            except:
                                pass

                        question = Question(
                            id=q_data.get("id", ""),
                            topic=q_data.get("topic", ""),
                            question_text=q_data.get("question_text", ""),
                            choices=choices,
                            explanation=q_data.get("explanation", ""),
                            difficulty=q_data.get("difficulty", "medium"),
                            is_multi_choice=q_data.get("is_multi_choice", False),
                            generated_at=generated_at,
                        )
                        all_questions.append(question)

                quiz_user_answers = []
                for answer_data in user_answers:
                    try:
                        answered_at = datetime.now()
                        if answer_data.get("answered_at"):
                            try:
                                answered_at = datetime.fromisoformat(
                                    answer_data["answered_at"]
                                )
                            except:
                                pass

                        user_answer = UserAnswer(
                            question_id=answer_data.get("question_id", ""),
                            selected_choice_indices=answer_data.get(
                                "selected_choice_indices", []
                            ),
                            is_correct=answer_data.get("is_correct", False),
                            answered_at=answered_at,
                            attempt_number=answer_data.get("attempt_number", 1),
                        )
                        quiz_user_answers.append(user_answer)
                    except Exception as e:
                        logger.warning(f"Could not restore user answer: {e}")
                        continue

                quiz_session = QuizSession(
                    session_id=questions_data.get("session_id", f"session_{quiz_id}"),
                    topics=topics,
                    total_questions=quiz.total_questions or 20,
                    difficulty=quiz.difficulty or "medium",
                    batch_size=5,
                    copies_per_incorrect_answer=2,
                    quiz_mode="fresh",
                    questions_per_topic=questions_data.get("questions_per_topic", {}),
                    all_generated_questions=all_questions,
                    active_question_pool=questions_data.get("active_question_pool", []),
                    current_question_index=quiz.current_question_index,
                    user_answers=quiz_user_answers,
                    status="active" if quiz.status == "quiz_active" else "completed",
                    user_id=quiz.user_id,
                )

                quiz_state = {
                    "quiz_session": quiz_session,
                    "session_snapshot": None,
                    "current_question": quiz_session.get_current_question(),
                    "user_input": None,
                    "questions_to_generate": None,
                    "current_topic_batch": None,
                    "quiz_results": None,
                    "quiz_complete": quiz.status == "quiz_completed",
                    "next_node": (
                        "present_question"
                        if not quiz_session.is_completed()
                        else "finalize_results"
                    ),
                    "quiz_config": None,
                    "confirmed_topics": topics,
                }

                quiz_graph.update_state(config, quiz_state)

                if (
                    quiz.status == "quiz_active"
                    and quiz_session.get_current_question()
                    and not quiz_session.is_completed()
                ):
                    try:
                        quiz_graph.invoke(None, config)

                        current_state = quiz_graph.get_state(config)
                        if not (
                            current_state.next
                            and "process_answer" in current_state.next
                        ):
                            logger.warning(
                                f"Graph not in expected interrupted state after restoration: {current_state.next}"
                            )

                    except Exception as e:
                        logger.warning(f"Could not restore to interrupted state: {e}")

                self.active_quiz_graphs[quiz_id] = {
                    "graph": quiz_graph,
                    "config": config,
                    "retriever": retriever,
                }

                logger.info(f"Successfully restored quiz session for {quiz_id}")
                return True

            except Exception as e:
                logger.error(f"Failed to reconstruct quiz session: {e}")
                return False

        except Exception as e:
            logger.error(f"Failed to restore quiz session: {e}")
            return False

    async def _restore_from_questions_data(
        self, quiz_id: str, quiz, db: Session
    ) -> bool:
        """Restore quiz session from questions_data after soft reset"""
        try:
            collection_name = quiz.collection_name
            if not collection_name:
                return False

            retriever = RAGRetriever(collection_name, self.qdrant_manager)

            quiz_graph = create_quiz_graph(retriever)
            config = {"configurable": {"thread_id": f"quiz_{quiz_id}"}}

            questions_data = quiz.questions_data or {}

            logger.info(f"Questions data keys: {questions_data.keys()}")
            logger.debug(f"Session id: {questions_data['session_id']}")
            logger.debug(
                f"All generated questions count: {len(questions_data.get('all_generated_questions', []))}"
            )
            logger.debug(
                f"Active question pool: {questions_data.get('active_question_pool', [])}"
            )

            from Agent.Quiz.models import (
                QuizSession,
                Question,
                QuestionChoice,
                QuizConfiguration,
            )
            from Agent.Shared import WeightedTopic
            from datetime import datetime

            topics = []
            if quiz.confirmed_topics:
                for topic_data in quiz.confirmed_topics:
                    topics.append(
                        WeightedTopic(
                            topic=topic_data.get("topic", ""),
                            weight=topic_data.get("weight", 1.0),
                        )
                    )

            all_questions = []
            if questions_data.get("all_generated_questions"):
                for q_data in questions_data["all_generated_questions"]:
                    choices = [
                        QuestionChoice(
                            text=choice.get("text", ""),
                            is_correct=choice.get("is_correct", False),
                        )
                        for choice in q_data.get("choices", [])
                    ]

                    generated_at = datetime.now()
                    if q_data.get("generated_at"):
                        try:
                            generated_at = datetime.fromisoformat(
                                q_data["generated_at"]
                            )
                        except:
                            pass

                    question = Question(
                        id=q_data.get("id", ""),
                        topic=q_data.get("topic", ""),
                        question_text=q_data.get("question_text", ""),
                        choices=choices,
                        explanation=q_data.get("explanation", ""),
                        difficulty=q_data.get("difficulty", "medium"),
                        is_multi_choice=q_data.get("is_multi_choice", False),
                        generated_at=generated_at,
                    )
                    all_questions.append(question)

            quiz_session = QuizSession(
                session_id=questions_data.get("session_id", f"session_{quiz_id}"),
                topics=topics,
                total_questions=quiz.total_questions or 20,
                difficulty=quiz.difficulty or "medium",
                batch_size=5,
                copies_per_incorrect_answer=2,
                quiz_mode="retry_same",
                questions_per_topic=questions_data.get("questions_per_topic", {}),
                all_generated_questions=all_questions.copy(),
                active_question_pool=self.deduplicate_pool(
                    questions_data.get("active_question_pool", []), quiz_id=quiz_id
                ),
                current_question_index=0,  
                user_answers=[],  
                status="active",
                user_id=quiz.user_id,
            )
            logger.debug(f"Created session with id: {quiz_session.session_id} ")

            logger.debug(
                f"Created session with {len(quiz_session.all_generated_questions)} questions"
            )
            logger.debug(
                f"Created session with active pool: {quiz_session.active_question_pool}"
            )
            logger.debug(f"Session quiz_mode: {quiz_session.quiz_mode}")

            update_quiz_progress(
                db,
                quiz_id,
                current_question_index=quiz_session.current_question_index,
            )
            logger.info(
                f"Synced database current_question_index to {quiz_session.current_question_index}"
            )

            quiz_config = QuizConfiguration(
                topics=topics,
                total_questions=quiz.total_questions,
                difficulty=quiz.difficulty,
                batch_size=5,
                copies_per_incorrect_answer=2,
                quiz_mode="retry_same",
                user_questions=[],
                user_id=quiz.user_id,
            )

            quiz_state = {
                "quiz_session": quiz_session,
                "session_snapshot": None,
                "current_question": quiz_session.get_current_question(),
                "user_input": None,
                "questions_to_generate": None,
                "current_topic_batch": None,
                "quiz_results": None,
                "quiz_complete": False,
                "next_node": "present_question",
                "quiz_config": quiz_config,
                "confirmed_topics": topics,
            }

            quiz_graph.update_state(config, quiz_state)

            quiz_graph.invoke(None, config)

            current_state = quiz_graph.get_state(config)
            logger.debug(f"Graph state after manual setup: {current_state.next}")
            if not (current_state.next and "process_answer" in current_state.next):
                logger.warning(
                    f"Graph not in expected interrupted state after restoration: {current_state.next}"
                )
            quiz_session = current_state.values.get("quiz_session")

            self.active_quiz_graphs[quiz_id] = {
                "graph": quiz_graph,
                "config": config,
                "retriever": retriever,
            }

            logger.info(
                f"Successfully restored quiz session from questions data for {quiz_id}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to restore from questions data: {e}")
            return False

    def deduplicate_pool(self, active_question_pool: List, quiz_id: str = None):
        import random
        import hashlib

        logger.info(f"Original active question pool: {active_question_pool}")

        seen = set()
        deduplicated_pool = []

        for question_id in active_question_pool:
            if question_id not in seen:
                seen.add(question_id)
                deduplicated_pool.append(question_id)

        logger.info(f"Deduplicated active question pool: {deduplicated_pool}")
        if (
            deduplicated_pool
            and quiz_id
            and len(deduplicated_pool) != len(active_question_pool)
        ):
            seed = int(hashlib.md5(quiz_id.encode()).hexdigest()[:8], 16)
            random.seed(seed)
            random.shuffle(deduplicated_pool)
            random.seed()  
            logger.info(f"Shuffled with seed {seed}: {deduplicated_pool}")
        return deduplicated_pool

    async def _update_quiz_from_session(
        self, quiz_id: str, quiz_session, graph_state, db: Session
    ):
        """Update database from quiz session state"""
        try:
            questions_data = {
                "session_id": quiz_session.session_id,
                "all_generated_questions": [
                    self._serialize_question(q)
                    for q in quiz_session.all_generated_questions
                ],
                "active_question_pool": quiz_session.active_question_pool,
                "questions_per_topic": quiz_session.questions_per_topic,
            }

            user_answers = []
            for answer in quiz_session.user_answers:
                answered_at = answer.answered_at
                if isinstance(answered_at, datetime):
                    answered_at_str = answered_at.isoformat()
                else:
                    answered_at_str = str(answered_at)

                user_answers.append(
                    {
                        "question_id": answer.question_id,
                        "selected_choice_indices": answer.selected_choice_indices,
                        "is_correct": answer.is_correct,
                        "answered_at": answered_at_str,
                        "attempt_number": answer.attempt_number,
                    }
                )

            serialized_state = self._serialize_langgraph_state(graph_state)

            update_quiz_progress(
                db,
                quiz_id,
                questions_data=questions_data,
                user_answers=user_answers,
                current_question_index=quiz_session.current_question_index,
                langgraph_quiz_state=serialized_state,
            )

        except Exception as e:
            logger.error(f"Failed to update quiz from session: {e}")
            raise

    async def _format_answer_response(
        self,
        latest_answer,
        feedback_request: str,
        next_available: bool,
        quiz_session,
        question_id: str,
    ) -> QuizAnswerResponse:
        """Format the answer response from quiz session data"""
        try:
            answered_question = None
            for q in quiz_session.all_generated_questions:
                if q.id == question_id:
                    answered_question = q
                    break

            if not answered_question:
                raise ValueError("Answered question not found")

            selected_texts = []
            for idx in latest_answer.selected_choice_indices:
                if idx < len(answered_question.choices):
                    selected_texts.append(answered_question.choices[idx].text)

            correct_texts = []
            for choice in answered_question.choices:
                if choice.is_correct:
                    correct_texts.append(choice.text)

            total_questions = len(set(quiz_session.active_question_pool))
            answered_unique = len(
                set(
                    answer.question_id
                    for answer in quiz_session.user_answers
                    if answer.attempt_number == 1
                )
            )
            correct_unique = len(
                set(
                    answer.question_id
                    for answer in quiz_session.user_answers
                    if answer.attempt_number == 1 and answer.is_correct
                )
            )

            progress = QuizProgressResponse(
                current_question_number=min(
                    quiz_session.current_question_index + 1, total_questions
                ),
                total_questions=total_questions,
                answered=answered_unique,
                correct=correct_unique,
            )

            return QuizAnswerResponse(
                correct=latest_answer.is_correct,
                explanation=(
                    feedback_request
                    if feedback_request
                    else answered_question.explanation
                ),
                selected_answers=selected_texts,
                correct_answers=correct_texts,
                next_question_available=next_available,
                progress=progress,
            )

        except Exception as e:
            logger.error(f"Failed to format answer response: {e}")
            raise

    def get_quiz_results(
        self, quiz_id: str, db: Session
    ) -> Optional[QuizResultsResponse]:
        """Get quiz results and statistics"""
        try:
            quiz = get_quiz(db, quiz_id)
            if not quiz or quiz.status != "quiz_completed":
                return None

            questions_data = quiz.questions_data or {}
            total_questions = len(questions_data.get("active_question_pool", []))
            user_answers = quiz.user_answers or []

            correct_answers = sum(
                1
                for answer in user_answers
                if isinstance(answer, dict) and answer.get("is_correct")
            )

            score_percentage = (
                (correct_answers / total_questions * 100) if total_questions > 0 else 0
            )

            topic_scores = {}
            if quiz.confirmed_topics:
                for topic_data in quiz.confirmed_topics:
                    topic_name = topic_data.get("topic", "Unknown")

                    topic_questions = [
                        q
                        for q in questions_data.get("all_generated_questions", [])
                        if q.get("topic") == topic_name
                    ]

                    topic_question_ids = [q.get("id") for q in topic_questions]
                    topic_answers = [
                        a
                        for a in user_answers
                        if a.get("question_id") in topic_question_ids
                    ]

                    topic_correct = sum(1 for a in topic_answers if a.get("is_correct"))

                    topic_scores[topic_name] = TopicScore(
                        correct=topic_correct,
                        total=len(topic_answers),
                        percentage=(
                            (topic_correct / len(topic_answers) * 100)
                            if topic_answers
                            else 0
                        ),
                    )

            quiz_results = QuizResults(
                quiz_id=quiz_id,
                total_questions=total_questions,
                correct_answers=correct_answers,
                score_percentage=score_percentage,
                topic_scores=topic_scores,
                completed_at=quiz.quiz_completed_at or datetime.now(),
            )

            return QuizResultsResponse(quiz_results=quiz_results, status="completed")

        except Exception as e:
            logger.error(f"Failed to get quiz results: {e}")
            return None

    def get_quiz_preview(self, quiz_id: str, db: Session) -> Dict:
        """Get quiz preview data with actual questions"""
        try:
            quiz = get_quiz(db, quiz_id)
            if not quiz:
                raise ValueError("Quiz not found")

            topics = quiz.confirmed_topics or []
            total_questions = quiz.total_questions or 20

            if quiz.questions_data and quiz.questions_data.get(
                "all_generated_questions"
            ):
                all_questions = quiz.questions_data.get("all_generated_questions", [])

                topics_with_questions = []
                for topic in topics:
                    topic_name = topic.get("topic", "Unknown")

                    topic_questions = [
                        {
                            "id": q.get("id"),
                            "question_text": q.get("question_text"),
                            "difficulty": q.get("difficulty", "medium"),
                            "is_multi_choice": q.get("is_multi_choice", False),
                            "choices_count": len(q.get("choices", [])),
                        }
                        for q in all_questions
                        if q.get("topic") == topic_name
                    ]

                    topics_with_questions.append(
                        {
                            "topic": topic_name,
                            "question_count": len(topic_questions),
                            "questions": topic_questions,
                        }
                    )

                return {
                    "total_questions": len(all_questions),
                    "difficulty": quiz.difficulty or "medium",
                    "topics": topics_with_questions,
                    "has_generated_questions": True,
                }

            else:
                topics_preview = []
                for topic in topics:
                    count = round(total_questions * topic.get("weight", 0))
                    topics_preview.append(
                        {
                            "topic": topic.get("topic", "Unknown"),
                            "question_count": count,
                            "questions": [],  
                        }
                    )

                return {
                    "total_questions": total_questions,
                    "difficulty": quiz.difficulty or "medium",
                    "topics": topics_preview,
                    "has_generated_questions": False,
                }

        except Exception as e:
            logger.error(f"Failed to get quiz preview: {e}")
            return {}

    def pause_quiz(self, quiz_id: str, db: Session) -> bool:
        """Pause active quiz"""
        try:
            return update_quiz(db, quiz_id, status="paused")
        except Exception as e:
            logger.error(f"Failed to pause quiz: {e}")
            return False

    def resume_quiz(self, quiz_id: str, db: Session) -> bool:
        """Resume paused quiz"""
        try:
            return update_quiz(db, quiz_id, status="quiz_active")
        except Exception as e:
            logger.error(f"Failed to resume quiz: {e}")
            return False

    def _parse_source_metadata(self, source_metadata_data) -> Optional[SourceMetadata]:
        """Convert source metadata from dict/object to SourceMetadata instance"""
        if not source_metadata_data:
            return None

        try:
            if isinstance(source_metadata_data, SourceMetadata):
                return source_metadata_data

            elif isinstance(source_metadata_data, dict):
                return SourceMetadata(
                    source=source_metadata_data.get("source", "Unknown"),
                    page=source_metadata_data.get("page"),
                    slide=source_metadata_data.get("slide"),
                    chunk_text=source_metadata_data.get("chunk_text"),
                )

            elif hasattr(source_metadata_data, "source"):
                return SourceMetadata(
                    source=getattr(source_metadata_data, "source", "Unknown"),
                    page=getattr(source_metadata_data, "page", None),
                    slide=getattr(source_metadata_data, "slide", None),
                    chunk_text=getattr(source_metadata_data, "chunk_text", None),
                )

            else:
                if hasattr(source_metadata_data, "__dict__"):
                    metadata_dict = source_metadata_data.__dict__
                    return SourceMetadata(
                        source=metadata_dict.get("source", "Unknown"),
                        page=metadata_dict.get("page"),
                        slide=metadata_dict.get("slide"),
                        chunk_text=metadata_dict.get("chunk_text"),
                    )

                logger.warning(
                    f"Unknown source_metadata_data type: {type(source_metadata_data)}"
                )
                return None

        except Exception as e:
            logger.error(f"Error parsing source metadata: {e}")
            logger.error(f"Source metadata data type: {type(source_metadata_data)}")
            logger.error(f"Source metadata data: {source_metadata_data}")
            return None

    def get_explanation_context(
        self, document_service, quiz_id: str, question_id: str, limit: int, db: Session
    ) -> Optional[Dict[str, Any]]:
        """Get explanation context from vector store for specific question"""
        try:
            quiz = get_quiz(db, quiz_id)
            if not quiz:
                return None

            if not quiz.questions_data or not quiz.questions_data.get(
                "all_generated_questions"
            ):
                return None

            question_data = None
            for q in quiz.questions_data.get("all_generated_questions", []):
                if q.get("id") == question_id:
                    question_data = q
                    break

            if not question_data:
                return None

            if not question_data.get("explanation"):
                return None

            search_result = document_service.search_documents(
                query=question_data["explanation"],
                quiz_id=quiz_id,
                limit=limit,  
            )

            source_chunks = []
            for result in search_result["results"]:
                source_chunks.append(
                    {
                        "text": result["text"],
                        "source": result["source"],
                        "page": result.get("page"),
                        "slide": result.get("slide"),
                        "relevance_score": result["relevance_score"],
                    }
                )

            return {
                "question_id": question_id,
                "explanation": question_data["explanation"],
                "source_chunks": source_chunks,
                "additional_context": question_data.get("topic", ""),
            }

        except Exception as e:
            logger.error(f"Failed to get explanation context: {e}")
            return None

    def restart_quiz(self, quiz_id: str, hard: bool, db: Session) -> Dict[str, Any]:
        """Restart quiz with proper cleanup"""

        if quiz_id in self.active_quiz_graphs:
            del self.active_quiz_graphs[quiz_id]
            logger.info(f"Cleaned up active graph for quiz {quiz_id}")

        if hard:
            success = reset_quiz_execution(db, quiz_id)
            reset_type = "hard"
            message = "Quiz reset successfully. Start again to generate new questions."
            regenerated_questions = False  
        else:

            quiz = get_quiz(db, quiz_id)
            if quiz and quiz.questions_data:
                deduplicated_active_question_pool = self.deduplicate_pool(
                    quiz.questions_data["active_question_pool"], quiz_id=quiz_id
                )
                updated_questions_data = quiz.questions_data.copy()
                updated_questions_data["active_question_pool"] = (
                    deduplicated_active_question_pool
                )
                quiz.questions_data = updated_questions_data
                logger.debug(f"Question data in restart quiz: {quiz.questions_data}")
                db.commit()
                db.refresh(quiz)

            success = soft_reset_quiz_execution(db, quiz_id, updated_questions_data)

            reset_type = "soft"
            message = "Quiz progress reset. Questions preserved."
            regenerated_questions = False  

        return {
            "success": success,
            "reset_type": reset_type,
            "message": message,
            "regenerated_questions": regenerated_questions,
        }
