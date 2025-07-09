"""
Main runner for TESTAIOWNIK - handles both TopicSelection and Quiz phases
"""

from typing import List, Optional
from Agent.TopicSelection import create_agent_graph
from Agent.Quiz import create_quiz_graph, create_initial_quiz_state, Question
from Agent.Shared import WeightedTopic
from RAG.Retrieval import MockRetriever, DocumentRetriever

from utils import logger


class TestaiownikRunner:
    """Main orchestrator for the complete learning assistant workflow"""

    def __init__(self, retriever: Optional[DocumentRetriever] = None):
        self.retriever = retriever or MockRetriever()
        self.topic_graph = create_agent_graph(self.retriever)
        self.quiz_graph = create_quiz_graph(self.retriever)

    def run_complete_workflow(
        self,
        desired_topic_count: int = 10,
        total_questions: int = 20,
        difficulty: str = "very hard",  
        user_questions: Optional[List[str]] = None,
    ) -> None:
        """Run the complete workflow: TopicSelection -> Quiz"""

        print("🎓 Welcome to TESTAIOWNIK - AI-powered Learning Assistant")
        print("=" * 60)

        print("\n📚 PHASE 1: Topic Selection from your materials")
        print("-" * 40)

        confirmed_topics = self._run_topic_selection(desired_topic_count)

        if not confirmed_topics:
            print("❌ No topics confirmed. Exiting...")
            return

        print(f"\n🧠 PHASE 2: Quiz with {total_questions} questions")
        print("-" * 40)

        self._run_quiz(
            confirmed_topics, total_questions, difficulty, user_questions or []
        )

        print("\n🎉 Session completed! Thank you for using TESTAIOWNIK!")

    def _run_topic_selection(self, desired_topic_count: int) -> List[WeightedTopic]:
        """Run topic selection phase"""

        config = {"configurable": {"thread_id": "topic-selection"}}

        initial_state = {
            "documents": [],
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

        self.topic_graph.invoke(initial_state, config)

        while True:
            current_state = self.topic_graph.get_state(config)

            if current_state.next == ():
                final_topics = current_state.values.get("confirmed_topics", [])
                if final_topics:
                    print(f"\n✅ Topics confirmed: {len(final_topics)} topics selected")
                    return final_topics
                else:
                    return []

            feedback_request = current_state.values.get("feedback_request", "")
            if feedback_request:
                print(f"\n{feedback_request}")

            user_input = input("\n👤 Your response: ").strip()

            if user_input.lower() in ["quit", "exit", "q"]:
                print("Exiting topic selection...")
                return []

            self.topic_graph.update_state(config, {"user_input": user_input})
            self.topic_graph.invoke(None, config)  

    def _run_quiz(
        self,
        confirmed_topics: List[WeightedTopic],
        total_questions: int,
        difficulty: str,
        user_questions: List[str],
    ) -> None:
        """Run quiz phase"""

        config = {"configurable": {"thread_id": "quiz-session"}}

        quiz_state = create_initial_quiz_state(
            confirmed_topics=confirmed_topics,
            total_questions=total_questions,
            difficulty=difficulty,
            batch_size=5,
            max_incorrect_recycles=2,
            quiz_mode="fresh",
            user_id="cli-user",
        )

        if user_questions:
            quiz_state["quiz_config"].user_questions = user_questions
            print(f"📝 Including {len(user_questions)} user-provided questions")

        self.quiz_graph.invoke(quiz_state, config)

        while True:
            current_state = self.quiz_graph.get_state(config)

            if current_state.next == ():
                print(
                    f"\n{current_state.values.get('feedback_request', 'Quiz completed!')}"
                )
                break

            current_question = current_state.values.get("current_question")
            if current_question:
                quiz_session = current_state.values.get("quiz_session")
                if quiz_session:
                    question_num = quiz_session.current_question_index + 1
                    total_questions = len(quiz_session.active_question_pool)
                    self._display_question_cli(
                        current_question, question_num, total_questions
                    )
                else:
                    self._display_question_cli(current_question)

            feedback = current_state.values.get("feedback_request", "")
            logger.debug(f"Current feedback: {feedback}")
            if feedback:
                print(f"\n{feedback}")

            if "process_answer" in current_state.next:
                user_input = self._get_quiz_answer_input()

                if user_input is None:  
                    print("Quiz terminated by user.")
                    break

                self.quiz_graph.update_state(config, {"user_input": user_input})

            self.quiz_graph.invoke(None, config)

    def _display_question_cli(
        self,
        question: Question,
        question_number: int = None,
        total_questions: int = None,
    ) -> None:
        if question_number and total_questions:
            progress = f"Question {question_number}/{total_questions}"
            print(f"\n{'=' * 60}")
            print(
                f"📝 {progress} | Topic: {question.topic} | Difficulty: {question.difficulty.upper()}"
            )
            print(f"{'=' * 60}")
        else:
            print(f"\n{'=' * 60}")
            print(
                f"📝 Topic: {question.topic} | Difficulty: {question.difficulty.upper()}"
            )
            print(f"{'=' * 60}")

        print(f"\n❓ {question.question_text}")
        print()

        for i, choice in enumerate(question.choices, 1):
            print(f"   {i}. {choice.text}")

        logger.debug(f"Question explanation: {question.explanation}")

        print()
        if question.is_multi_choice:
            print(
                "💡 Multiple answers allowed - enter numbers separated by commas (e.g., 1,3)"
            )
        else:
            print("💡 Select one answer - enter the number")

        print(f"{'─' * 60}")

    def _get_quiz_answer_input(self) -> Optional[List[int]]:
        """Get user's answer input for quiz questions"""

        while True:
            try:
                response = input(
                    "👤 Your answer (number(s) separated by commas, or 'quit'): "
                ).strip()

                if response.lower() in ["quit", "exit", "q"]:
                    return None

                if "," in response:
                    indices = [
                        int(x.strip()) - 1
                        for x in response.split(",")
                        if x.strip().isdigit()
                    ]
                else:
                    if response.isdigit():
                        indices = [int(response) - 1]
                    else:
                        raise ValueError("Invalid input")

                if not indices:
                    raise ValueError("No valid answers provided")

                return indices

            except ValueError as e:
                print(
                    f"❌ Invalid input. Please enter number(s) (1, 2, 3...) or 'quit'. Error: {e}"
                )
                continue



