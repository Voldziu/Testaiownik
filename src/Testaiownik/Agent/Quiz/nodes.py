from typing import Dict, Any, List
import random
from datetime import datetime
from .state import QuizState, prepare_state_for_persistence
from .models import (
    QuizSession,
    Question,
    QuestionChoice,
    QuestionGeneration,
    QuizResults,
    UserAnswer,
    WeightedTopic,
    UserQuestionResponse,
)
from RAG.Retrieval import DocumentRetriever

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
        # TODO: Implement loading from previous session when RAG is implemented
        logger.info(
            f"Quiz mode {session.quiz_mode} - would load from previous session TODO."
        )
        # For now, fall back to fresh generation
        return {**state, "next_node": "generate_all_questions"}
    else:
        raise ValueError(f"Unknown quiz mode: {session.quiz_mode}")


def generate_all_questions(
    state: QuizState, retriever: DocumentRetriever = None
) -> QuizState:
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
    # Track questions per topic to prevent cross-batch duplicates
    topic_questions_tracker = {}
    all_generated = []
    for topic, count in questions_to_generate.items():
        logger.info(f"Generating {count} questions for topic: {topic}")
        topic_questions_tracker[topic] = []

        # Generate in batches to avoid token limits
        remaining = count
        while remaining > 0:
            batch_size = min(session.batch_size, remaining)

            batch_questions = _generate_questions_for_topic(
                topic=topic,
                count=batch_size,
                difficulty=session.difficulty,
                retriever=retriever,
                existing_questions=topic_questions_tracker[
                    topic
                ].copy(),  # Pass existing questions to avoid duplicates
            )

            # Update the tracker with newly generated questions
            topic_questions_tracker[topic].extend(
                [q.question_text for q in batch_questions]
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
    logger.debug(
        f"All generated questions: {[q.question_text for q in session.all_generated_questions]}"
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
    user_input = state.get("user_input")  # Expecting list of ints

    if not session or not current_question:
        return {**state, "next_node": "present_question"}

    if not user_input:
        logger.warning("No user input provided")
        return {**state, "next_node": "present_question"}

    # Validate list of indices

    if not isinstance(user_input, list):
        logger.warning(f"User input not a list type")
        return {
            **state,
            "feedback_request": "User input not a list type",
            "next_node": "present_question",
        }

    selected_indices = []
    for index in user_input:
        if not isinstance(index, int):
            raise ValueError(f"Invalid input type: {type(index)}, expected int")
        if index < 0 or index >= len(current_question.choices):
            raise ValueError(f"Index {index} out of range")
        selected_indices.append(index)

    # Remove duplicates and sort
    selected_indices = sorted(list(set(selected_indices)))

    if not selected_indices:
        logger.warning(f"No valid answers provided")
        return {
            **state,
            "feedback_request": "No valid answers provided",
            "next_node": "present_question",
        }

    # Check if answer is correct using Question's built-in method
    is_correct = current_question.is_answer_correct(selected_indices)

    # Create answer record
    attempt_number = session.incorrect_recycle_count.get(current_question.id, 0) + 1
    answer = UserAnswer(
        question_id=current_question.id,
        selected_choice_indices=selected_indices,
        is_correct=is_correct,
        attempt_number=attempt_number,
    )

    # Add answer and handle recycling
    session.add_answer(answer)

    # Prepare feedback
    feedback = _create_answer_feedback(current_question, selected_indices, is_correct)

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


# TODO: optimze calling llm (batch it)
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
1. The correct answer(s) - provide as a list even if single answer
2. Provide 2-4 plausible but incorrect options
3. Whether this question allows multiple correct answers (is_multi_choice)
4. Detailed explanation of why the answer(s) are correct
5. Which topic from the available list best fits this question

For simple True/False questions:
- Provide exactly 2 options: the correct answer and its opposite
- Set is_multi_choice to False

For complex questions:
- Provide 3-4 total options
- Can have multiple correct answers if the question naturally allows it

Provide structured response."""

            response = llm.invoke(prompt)

            # Create choices from structured response
            choices = []

            # Add correct answers
            for correct_answer in response.correct_answers:
                choices.append(QuestionChoice(text=correct_answer, is_correct=True))

            # Add wrong options
            for wrong_option in response.wrong_options:
                choices.append(QuestionChoice(text=wrong_option, is_correct=False))

            # Ensure at least 2 choices
            if len(choices) < 2:
                choices.append(QuestionChoice(text="False", is_correct=False))

            question = Question(
                topic=response.assigned_topic,
                question_text=question_text,
                choices=choices,
                explanation=response.explanation,
                difficulty=difficulty,
                is_multi_choice=response.is_multi_choice,
            )

            processed_questions.append(question)
            logger.info(f"Processed user question {i+1}: {question_text[:50]}...")

        except Exception as e:
            logger.error(f"Failed to process user question '{question_text}': {e}")
            # Create fallback question
            fallback_question = Question(
                topic=available_topics[0] if available_topics else "General",
                question_text=question_text,
                choices=[
                    QuestionChoice(text="True", is_correct=True),
                    QuestionChoice(text="False", is_correct=False),
                ],
                explanation="This question was provided by the user. Please verify the answer.",
                difficulty=difficulty,
                is_multi_choice=False,
            )
            processed_questions.append(fallback_question)

    return processed_questions


def _generate_questions_for_topic(
    topic: str,
    count: int,
    difficulty: str,
    retriever: DocumentRetriever = None,
    existing_questions: List[str] = [],
) -> List[Question]:
    """Generate questions for a specific topic using LLM with RAG context"""
    llm = get_llm().with_structured_output(QuestionGeneration)

    # Get relevant context using RAG search
    context_text = ""
    if retriever:
        search_results = retriever.search_in_collection(query=f"{topic}", limit=20)

        if search_results:
            relevant_chunks = [
                result.payload.get("text", "") for result in search_results
            ]
            context_text = (
                f"\n\nRELEVANT DOCUMENT CONTEXT:\n{chr(10).join(relevant_chunks)}"
            )
            logger.info(
                f"Using {len(relevant_chunks)} RAG chunks for {topic} questions"
            )
        else:
            logger.info(f"No relevant chunks found for {topic}")
    else:
        logger.info(
            f"RAG not available, generating questions for {topic} without context"
        )

    # Create blacklist section if we have existing questions
    created_questions_text = ""
    if existing_questions:
        created_questions_text = f"""
            AVOID THESE ALREADY CREATED QUESTIONS:
            {chr(10).join([f"- {q}" for q in existing_questions])}

            DO NOT create questions similar to the above. Focus on different concepts, angles, and wording.
            """

    prompt = f"""Create {count} educational assessment questions for: {topic}
Focus on:
- Different concepts/subtopics
- Different question types (definition, application, analysis)
- Different difficulty angles
 
Purpose: Academic Assessment
Level: {difficulty}

Question Format:
- 30% binary choice (2 options)
- 70% multiple choice (3-4 options)
- Include answer explanations
- Mark multi-answer questions with is_multi_choice=True

Quality Standards:
- {difficulty}-appropriate content
- Educational focus on {topic}
- Questions can't be general, they must be very specific.
- Clear question wording
- Test comprehension over memorization
- Provide realistic answer options

DUPLICATE PREVENTION:
- Each question must cover different concepts/aspects
- Vary question wording and structure significantly
- Focus on distinct learning objectives
- Ensure no overlapping answer patterns

{created_questions_text}

{context_text}

Output exactly {count} unique questions following above specifications."""

    try:
        result = llm.invoke(prompt)
        questions = []

        for i, q in enumerate(result.questions):
            # Ensure proper structure
            q.topic = topic
            q.difficulty = difficulty

            # Create explanation with chunk metadata
            explanation = "Explanation generated from the context:\n"

            # Use search_in_collection with the question as query
            if retriever:
                search_results = retriever.search_in_collection(query=q.question_text, limit=1)  # Search using question text and limit to 1 result

                if search_results:
                    # The best match is the first result (since limit=1)
                    best_match = search_results[0].payload  # Get the metadata of the best match

                    # Retrieve chunk metadata
                    chunk_source = best_match.get("source", "Nieznane źródło")
                    page = best_match.get("page", None)
                    slide = best_match.get("slide", None)

                    # Add chunk metadata to explanation
                    explanation += f"\nŹródło: {chunk_source}"

                    # Add page or slide if available
                    if page:
                        explanation += f"\nStrona (PDF): {page}"
                    elif slide:
                        explanation += f"\nSlajd (PPTX): {slide}"

            # Adding the original explanation from the LLM
            explanation += f"\n\nOriginal explanation: {q.explanation}"

            # Update the explanation with chunk details
            q.explanation = explanation


            # Validate choices
            if len(q.choices) < 2:
                logger.warning(
                    f"Question has fewer than 2 choices, adding fallback choices"
                )
                q.choices.extend(
                    [
                        QuestionChoice(text="Option A True", is_correct=True),
                        QuestionChoice(text="Option B False", is_correct=False),
                    ]
                )

            # Ensure at least one correct answer
            if not any(choice.is_correct for choice in q.choices):
                logger.warning(
                    f"Question has no correct answer, marking first as correct"
                )
                q.choices[0].is_correct = True

            questions.append(q)

        # Remove duplicates post-processing
        unique_questions = _remove_duplicate_questions(questions)

        # If we lost questions due to duplicates, log it
        if len(unique_questions) < len(questions):
            logger.warning(
                f"Removed {len(questions) - len(unique_questions)} duplicate questions"
            )

        logger.info(f"Generated {len(unique_questions)} unique questions for {topic}")
        return unique_questions

    except Exception as e:
        logger.error(f"Question generation failed for {topic}: {e}")
        return _create_fallback_questions(topic, count, difficulty)


def _remove_duplicate_questions(questions: List[Question]) -> List[Question]:
    """Remove duplicate questions based on text similarity"""
    from difflib import SequenceMatcher

    unique_questions = []
    seen_questions = []

    for question in questions:
        is_duplicate = False

        for seen_q in seen_questions:
            # Check question text similarity
            similarity = SequenceMatcher(
                None, question.question_text.lower().strip(), seen_q.lower().strip()
            ).ratio()

            if similarity > 0.7:  # 70% similarity threshold
                is_duplicate = True
                break

        if not is_duplicate:
            unique_questions.append(question)
            seen_questions.append(question.question_text.lower().strip())

    return unique_questions


def _create_fallback_questions(
    topic: str, count: int, difficulty: str
) -> List[Question]:
    """Create fallback questions when LLM generation fails"""
    questions = []
    for i in range(count):
        if i % 3 == 0:
            # Simple choice (like True/False)
            question = Question(
                topic=topic,
                question_text=f"{topic} Fallback true/false",
                choices=[
                    QuestionChoice(text="True", is_correct=True),
                    QuestionChoice(text="False", is_correct=False),
                ],
                explanation=f"True, {topic} is indeed important in computer science.",
                difficulty=difficulty,
                is_multi_choice=False,
            )
        else:
            # Multi-choice
            question = Question(
                topic=topic,
                question_text=f"{topic} Fallback multi-choice",
                choices=[
                    QuestionChoice(text="True", is_correct=True),
                    QuestionChoice(text="True", is_correct=True),
                    QuestionChoice(text="False", is_correct=False),
                    QuestionChoice(text="False", is_correct=False),
                ],
                explanation=f"Characteristics A and B are both relevant to {topic}.",
                difficulty=difficulty,
                is_multi_choice=True,
            )
        questions.append(question)

    return questions


def _format_question_for_user(question: Question) -> str:
    """Format question for user presentation"""
    choices_text = "\n".join(
        [f"{i+1}. {choice.text}" for i, choice in enumerate(question.choices)]
    )

    instruction = ""
    if question.is_multi_choice:
        instruction = "\n(Multiple answers allowed - enter numbers separated by commas, e.g., 1,3)"
    else:
        instruction = "\n(Select one answer)"

    return f"""
Question: {question.question_text}

{choices_text}
{instruction}

Enter your choice(s): """


def _create_answer_feedback(
    question: Question, selected_indices: List[int], is_correct: bool
) -> str:
    """Create feedback for user's answer"""
    selected_choices = [question.choices[i] for i in selected_indices]
    selected_texts = [choice.text for choice in selected_choices]

    if is_correct:
        feedback = f"✓ Correct! You selected: {', '.join(selected_texts)}"
    else:
        correct_choices = [choice for choice in question.choices if choice.is_correct]
        correct_texts = [choice.text for choice in correct_choices]
        feedback = f"✗ Incorrect. You selected: {', '.join(selected_texts)}\nCorrect answer(s): {', '.join(correct_texts)}"

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
    logger.debug(f"Routing to: {next_node}")
    return next_node if next_node != "END" else "__end__"
