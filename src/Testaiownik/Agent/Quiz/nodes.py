from typing import Dict, Any, List
import random
from datetime import datetime
from .state import QuizState, prepare_state_for_persistence
from .models import (
    QuizSession,
    Question,
    QuestionType,
    QuestionChoice,
    QuestionGeneration,
    QuizResults,
    UserAnswer,
    WeightedTopic,
    UserQuestionResponse,
)

from AzureModels import get_llm
from utils.logger import logger


def initialize_quiz(state: QuizState) -> QuizState:
    """Initialize quiz session from configuration"""
    config = state["quiz_config"]
    if not config:
        raise ValueError("Quiz configuration is required")

    logger.info(
        f"Initializing quiz with {config.total_questions} questions, difficulty: {config.difficulty}"
    )

    # Calculate questions per topic based on weights
    questions_per_topic = {}
    for topic in config.topics:
        count = max(1, round(config.total_questions * topic.weight))
        questions_per_topic[topic.topic] = count

    # Create quiz session
    quiz_session = QuizSession(
        topics=config.topics,
        total_questions=config.total_questions,
        difficulty=config.difficulty,
        batch_size=config.batch_size,
        max_incorrect_recycles=config.max_incorrect_recycles,
        quiz_mode=config.quiz_mode,
        questions_per_topic=questions_per_topic,
        user_id=config.user_id,
    )

    logger.info(f"Questions per topic: {questions_per_topic}")

    return {
        **state,
        "quiz_session": quiz_session,
        "questions_to_generate": questions_per_topic.copy(),
        "current_topic_batch": None,
        "next_node": "load_or_generate_questions",
    }


def load_or_generate_questions(state: QuizState) -> QuizState:
    """Load existing questions or start generation based on quiz mode"""
    session = state["quiz_session"]
    if not session:
        raise ValueError("Quiz session not initialized")

    if session.quiz_mode == "fresh":
        logger.info("Starting fresh question generation")
        return {**state, "next_node": "generate_all_questions"}
    elif session.quiz_mode in ["retry_same", "retry_failed"]:
        # TODO: Implement loading from previous session
        logger.info(
            f"Quiz mode {session.quiz_mode} - would load from previous session TODO."
        )
        # For now, fall back to fresh generation
        return {**state, "next_node": "generate_all_questions"}
    else:
        raise ValueError(f"Unknown quiz mode: {session.quiz_mode}")


def generate_all_questions(state: QuizState) -> QuizState:
    """Generate ALL questions before starting quiz"""
    session = state["quiz_session"]
    questions_to_generate = state["questions_to_generate"]
    config = state["quiz_config"]

    if not session or not questions_to_generate:
        return {**state, "next_node": "present_question"}

    logger.info("Starting complete question generation for all topics")

    # 1. Process user-provided questions first
    user_questions = []
    if config and config.user_questions:
        logger.info(f"Processing {len(config.user_questions)} user-provided questions")
        user_questions = _process_user_questions(
            config.user_questions, session.topics, session.difficulty
        )
        session.all_generated_questions.extend(user_questions)
        logger.info(f"Added {len(user_questions)} user questions")

    # 2. Generate LLM questions in batches for each topic
    all_generated = []
    for topic, count in questions_to_generate.items():
        logger.info(f"Generating {count} questions for topic: {topic}")

        # Generate in batches to avoid token limits
        remaining = count
        while remaining > 0:
            batch_size = min(session.batch_size, remaining)

            batch_questions = _generate_questions_for_topic(
                topic=topic,
                count=batch_size,
                difficulty=session.difficulty,
                context=state.get("document_context", []),
            )

            all_generated.extend(batch_questions)
            remaining -= batch_size
            logger.info(
                f"Generated {batch_size} questions for {topic}, {remaining} remaining"
            )

    # 3. Add all generated questions to session
    session.all_generated_questions.extend(all_generated)

    # 4. Create shuffled active question pool
    all_question_ids = [q.id for q in session.all_generated_questions]
    random.shuffle(all_question_ids)  # Shuffle for better question distribution
    session.active_question_pool = all_question_ids

    logger.info(
        f"Generated total {len(session.all_generated_questions)} questions "
        f"({len(user_questions)} user + {len(all_generated)} LLM)"
    )

    return {
        **state,
        "quiz_session": session,
        "questions_to_generate": {},  # All done
        "current_topic_batch": None,
        "next_node": "present_question",
    }


def present_question(state: QuizState) -> QuizState:
    """Present current question to user"""
    session = state["quiz_session"]
    if not session:
        raise ValueError("Quiz session not initialized")

    current_question = session.get_current_question()
    if not current_question:
        logger.info("No more questions, finalizing quiz")
        return {**state, "next_node": "finalize_results"}

    session.status = "active"

    # Format question for presentation
    question_text = _format_question_for_user(current_question)

    logger.info(
        f"Presenting question {session.current_question_index + 1}/{len(session.active_question_pool)}"
    )

    return {
        **state,
        "quiz_session": session,
        "current_question": current_question,
        "feedback_request": question_text,
        "next_node": "process_answer",
    }


def process_answer(state: QuizState) -> QuizState:
    """Process user's answer and advance quiz"""
    session = state["quiz_session"]
    current_question = state["current_question"]
    user_input = state.get("user_input", "")

    if not session or not current_question:
        return {**state, "next_node": "present_question"}

    if not user_input:
        logger.warning("No user input provided")
        return {**state, "next_node": "present_question"}

    # Parse answer
    try:
        selected_index = int(user_input.strip()) - 1  # Convert to 0-based index
        if selected_index < 0 or selected_index >= len(current_question.choices):
            raise ValueError("Invalid choice index")
    except (ValueError, IndexError):
        logger.warning(f"Invalid answer format: {user_input}")
        return {
            **state,
            "feedback_request": "Invalid answer. Please enter a number corresponding to your choice.",
            "next_node": "present_question",
        }

    # Check if answer is correct
    is_correct = current_question.choices[selected_index].is_correct

    # Create answer record
    attempt_number = session.incorrect_recycle_count.get(current_question.id, 0) + 1
    answer = UserAnswer(
        question_id=current_question.id,
        selected_choice_index=selected_index,
        is_correct=is_correct,
        attempt_number=attempt_number,
    )

    # Add answer and handle recycling
    session.add_answer(answer)

    # Prepare feedback
    feedback = _create_answer_feedback(current_question, selected_index, is_correct)

    # Move to next question
    session.get_next_question()

    logger.info(
        f"Answer processed: {'✓' if is_correct else '✗'} "
        f"Question {session.current_question_index}/{len(session.active_question_pool)}"
    )

    return {
        **state,
        "quiz_session": session,
        "user_input": None,
        "feedback_request": feedback,
        "next_node": "check_completion",
    }


def check_completion(state: QuizState) -> QuizState:
    """Check if quiz is completed"""
    session = state["quiz_session"]
    if not session:
        return {**state, "next_node": "finalize_results"}

    if session.is_completed():
        logger.info("Quiz completed!")
        return {**state, "next_node": "finalize_results"}
    else:
        return {**state, "next_node": "present_question"}


def finalize_results(state: QuizState) -> QuizState:
    """Calculate and present final quiz results"""
    session = state["quiz_session"]
    if not session:
        raise ValueError("Quiz session not initialized")

    # Calculate results
    total_answered = len([a for a in session.user_answers if a.attempt_number == 1])
    correct_answers = len(
        [a for a in session.user_answers if a.is_correct and a.attempt_number == 1]
    )
    score_percentage = (
        (correct_answers / total_answered * 100) if total_answered > 0 else 0
    )

    # Calculate per-topic scores
    topic_scores = {}
    for topic in session.topics:
        topic_questions = [
            q for q in session.all_generated_questions if q.topic == topic.topic
        ]
        topic_answers = [
            a
            for a in session.user_answers
            if a.question_id in [q.id for q in topic_questions]
            and a.attempt_number == 1
        ]

        if topic_answers:
            topic_correct = len([a for a in topic_answers if a.is_correct])
            topic_scores[topic.topic] = {
                "correct": topic_correct,
                "total": len(topic_answers),
                "percentage": (topic_correct / len(topic_answers) * 100),
            }

    quiz_results = QuizResults(
        session_id=session.session_id,
        total_questions=total_answered,
        correct_answers=correct_answers,
        score_percentage=score_percentage,
        topic_scores=topic_scores,
    )

    session.status = "completed"

    # Format results for user
    results_text = _format_quiz_results(quiz_results)

    logger.info(
        f"Quiz finalized: {correct_answers}/{total_answered} ({score_percentage:.1f}%)"
    )

    return {
        **state,
        "quiz_session": session,
        "quiz_results": quiz_results,
        "quiz_complete": True,
        "feedback_request": results_text,
        "next_node": "END",
    }


# Helper functions


def _process_user_questions(
    user_questions: List[str], topics: List[WeightedTopic], difficulty: str
) -> List[Question]:
    """Process user-provided questions into Question objects"""
    if not user_questions:
        return []

    logger.info(f"Processing {len(user_questions)} user questions")

    # Use LLM with structured output to process user questions
    llm = get_llm().with_structured_output(UserQuestionResponse)

    processed_questions = []
    available_topics = [t.topic for t in topics]

    for i, question_text in enumerate(user_questions):
        try:
            prompt = f"""Analyze this student question: "{question_text}"

Available topics: {available_topics}
Difficulty level: {difficulty}

Determine:
1. Whether this is naturally a True/False question or needs multiple choice options
2. The correct answer
3. If multiple choice: provide 3 plausible but incorrect options
4. Detailed explanation of why the answer is correct
5. Which topic from the available list best fits this question

Provide structured response."""

            response = llm.invoke(prompt)

            # Create choices based on structured response
            if response.is_true_false:
                is_true_answer = response.correct_answer.lower() in [
                    "true",
                    "yes",
                    "correct",
                    "tak",
                ]
                choices = [
                    QuestionChoice(text="True", is_correct=is_true_answer),
                    QuestionChoice(text="False", is_correct=not is_true_answer),
                ]
                question_type = QuestionType.TRUE_FALSE
            else:
                choices = [
                    QuestionChoice(text=response.correct_answer, is_correct=True)
                ]
                # Add up to 3 wrong options
                for wrong_option in response.wrong_options[:3]:
                    choices.append(QuestionChoice(text=wrong_option, is_correct=False))
                question_type = QuestionType.MULTIPLE_CHOICE

            question = Question(
                topic=response.assigned_topic,
                type=question_type,
                question_text=question_text,
                choices=choices,
                explanation=response.explanation,
                difficulty=difficulty,
            )

            processed_questions.append(question)
            logger.info(f"Processed user question {i+1}: {question_text[:50]}...")

        except Exception as e:
            logger.error(f"Failed to process user question '{question_text}': {e}")
            # Create fallback question
            fallback_question = Question(
                topic=available_topics[0] if available_topics else "General",
                type=QuestionType.TRUE_FALSE,
                question_text=question_text,
                choices=[
                    QuestionChoice(text="True", is_correct=True),
                    QuestionChoice(text="False", is_correct=False),
                ],
                explanation="This question was provided by the user. Please verify the answer.",
                difficulty=difficulty,
            )
            processed_questions.append(fallback_question)

    return processed_questions


def _generate_questions_for_topic(
    topic: str, count: int, difficulty: str, context: List[str]
) -> List[Question]:
    """Generate questions for a specific topic using LLM"""
    llm = get_llm().with_structured_output(QuestionGeneration)

    # Prepare context for RAG (if available)
    context_text = ""
    if context:
        context_text = f"\n\nRELEVANT DOCUMENT CONTEXT:\n{chr(10).join(context[:3])}"  # Limit to 3 chunks

    # Determine question types distribution
    mc_count = max(1, count // 2)  # At least 1 multiple choice
    tf_count = count - mc_count

    prompt = f"""Generate {count} educational questions about: {topic}

REQUIREMENTS:
- Difficulty level: {difficulty}
- Generate {mc_count} multiple choice questions (4 options each)
- Generate {tf_count} true/false questions
- Questions should test understanding, not memorization
- Include clear explanations for correct answers
- Ensure variety in question types and concepts

{context_text}

QUESTION QUALITY GUIDELINES:
- {difficulty} level appropriate for educational assessment
- Clear, unambiguous wording
- Realistic distractors for multiple choice
- Comprehensive explanations
- Focus on key concepts and practical applications

Generate exactly {count} questions total."""

    try:
        result = llm.invoke(prompt)
        questions = []

        for i, q in enumerate(result.questions):
            # Ensure correct type assignment
            if i < mc_count:
                q.type = QuestionType.MULTIPLE_CHOICE
            else:
                q.type = QuestionType.TRUE_FALSE
                # Ensure true/false has exactly 2 choices
                if len(q.choices) != 2:
                    q.choices = [
                        QuestionChoice(text="True", is_correct=q.choices[0].is_correct),
                        QuestionChoice(
                            text="False", is_correct=not q.choices[0].is_correct
                        ),
                    ]

            q.topic = topic
            q.difficulty = difficulty
            questions.append(q)

        logger.info(f"Generated {len(questions)} questions for {topic}")
        return questions

    except Exception as e:
        logger.error(f"Question generation failed for {topic}: {e}")
        # Return fallback questions
        return _create_fallback_questions(topic, count, difficulty)


def _create_fallback_questions(
    topic: str, count: int, difficulty: str
) -> List[Question]:
    """Create fallback questions when LLM generation fails"""
    questions = []
    for i in range(count):
        if i % 2 == 0:
            # Multiple choice
            question = Question(
                topic=topic,
                type=QuestionType.MULTIPLE_CHOICE,
                question_text=f"Which of the following is most relevant to {topic}?",
                choices=[
                    QuestionChoice(text="Option A", is_correct=True),
                    QuestionChoice(text="Option B", is_correct=False),
                    QuestionChoice(text="Option C", is_correct=False),
                    QuestionChoice(text="Option D", is_correct=False),
                ],
                explanation=f"This is a fallback question about {topic}.",
                difficulty=difficulty,
            )
        else:
            # True/False
            question = Question(
                topic=topic,
                type=QuestionType.TRUE_FALSE,
                question_text=f"{topic} is an important concept in computer science.",
                choices=[
                    QuestionChoice(text="True", is_correct=True),
                    QuestionChoice(text="False", is_correct=False),
                ],
                explanation=f"True, {topic} is indeed important.",
                difficulty=difficulty,
            )
        questions.append(question)

    return questions


def _format_question_for_user(question: Question) -> str:
    """Format question for user presentation"""
    choices_text = "\n".join(
        [f"{i+1}. {choice.text}" for i, choice in enumerate(question.choices)]
    )

    return f"""
Question: {question.question_text}

{choices_text}

Enter your choice (number): """


def _create_answer_feedback(
    question: Question, selected_index: int, is_correct: bool
) -> str:
    """Create feedback for user's answer"""
    selected_choice = question.choices[selected_index]

    if is_correct:
        feedback = f"✓ Correct! You selected: {selected_choice.text}"
    else:
        correct_choice = next(c for c in question.choices if c.is_correct)
        feedback = f"✗ Incorrect. You selected: {selected_choice.text}\nCorrect answer: {correct_choice.text}"

    feedback += f"\n\nExplanation: {question.explanation}\n"
    return feedback


def _format_quiz_results(results: QuizResults) -> str:
    """Format quiz results for user presentation"""
    text = f"""
🎯 Quiz Complete!

Overall Score: {results.correct_answers}/{results.total_questions} ({results.score_percentage:.1f}%)

Topic Breakdown:
"""

    for topic, scores in results.topic_scores.items():
        text += f"• {topic}: {scores['correct']}/{scores['total']} ({scores['percentage']:.1f}%)\n"

    if results.score_percentage >= 80:
        text += "\n🌟 Excellent work!"
    elif results.score_percentage >= 60:
        text += "\n👍 Good job!"
    else:
        text += "\n📚 Keep studying!"

    return text


def route_next(state: QuizState) -> str:
    """Route to next node based on state"""
    next_node = state.get("next_node", "END")
    logger.info(f"Routing to: {next_node}")
    return next_node if next_node != "END" else "__end__"
