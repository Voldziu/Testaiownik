from typing import List
import random
from .state import QuizState
from .models import (
    QuizSession,
    Question,
    QuestionChoice,
    QuestionGeneration,
    QuizResults,
    UserAnswer,
    WeightedTopic,
    UserQuestionResponse,
    SourceMetadata,
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

    questions_per_topic = {}
    for topic in config.topics:
        count = max(1, round(config.total_questions * topic.weight))
        questions_per_topic[topic.topic] = count

    existing_session = state.get("quiz_session")
    if existing_session and config.quiz_mode in ["retry_same", "retry_failed"]:
        logger.info(f"Preserving existing session: {existing_session.session_id}")
        return {
            **state,
            "quiz_session": existing_session,  
            "questions_to_generate": {},  
            "current_topic_batch": None,
            "next_node": "load_or_generate_questions",
        }

    quiz_session = QuizSession(
        topics=config.topics,
        total_questions=config.total_questions,
        difficulty=config.difficulty,
        batch_size=config.batch_size,
        copies_per_incorrect_answer=config.copies_per_incorrect_answer,
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
        logger.debug(f"Session: {session}")
        if (
            session.all_generated_questions
            and len(session.all_generated_questions) > 0
            and session.active_question_pool
            and len(session.active_question_pool) > 0
        ):
            logger.info(
                f"Quiz mode {session.quiz_mode} - questions already exist, skipping generation. "
                f"Found {len(session.all_generated_questions)} questions, "
                f"active pool: {len(session.active_question_pool)}"
            )
            return {**state, "next_node": "present_question"}
        else:
            logger.info(
                f"Quiz mode {session.quiz_mode} - no existing questions found, generating new ones"
            )
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

    user_questions = []
    if config and config.user_questions:
        logger.info(f"Processing {len(config.user_questions)} user-provided questions")
        user_questions = _process_user_questions(
            config.user_questions, session.topics, session.difficulty
        )
        session.all_generated_questions.extend(user_questions)
        logger.info(f"Added {len(user_questions)} user questions")

    topic_questions_tracker = {}
    all_generated = []
    for topic, count in questions_to_generate.items():
        logger.info(f"Generating {count} questions for topic: {topic}")
        topic_questions_tracker[topic] = []

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
                ].copy(),  
            )

            topic_questions_tracker[topic].extend(
                [q.question_text for q in batch_questions]
            )

            all_generated.extend(batch_questions)
            remaining -= batch_size
            logger.info(
                f"Generated {batch_size} questions for {topic}, {remaining} remaining"
            )

    session.all_generated_questions.extend(all_generated)

    for idx, question in enumerate(session.all_generated_questions, start=1):
        question.id = f"q{idx}"

    all_question_ids = [q.id for q in session.all_generated_questions]
    random.shuffle(all_question_ids)  
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
        "questions_to_generate": {},  
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
    user_input = state.get("user_input")  

    if not session or not current_question:
        return {**state, "next_node": "present_question"}

    if not user_input:
        logger.warning("No user input provided")
        return {**state, "next_node": "present_question"}

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

    selected_indices = sorted(list(set(selected_indices)))

    if not selected_indices:
        logger.warning(f"No valid answers provided")
        return {
            **state,
            "feedback_request": "No valid answers provided",
            "next_node": "present_question",
        }

    is_correct = current_question.is_answer_correct(selected_indices)

    attempt_number = (
        len([a for a in session.user_answers if a.question_id == current_question.id])
        + 1
    )

    answer = UserAnswer(
        question_id=current_question.id,
        selected_choice_indices=selected_indices,
        is_correct=is_correct,
        attempt_number=attempt_number,
    )

    session.add_answer(answer)

    feedback = _create_answer_feedback(current_question, selected_indices, is_correct)

    session.get_next_question()

    logger.info(
        f"Answer processed: {'✓' if is_correct else '✗'} "
        f"Question {session.current_question_index}/{len(session.active_question_pool)}"
        f"{f' (added {session.copies_per_incorrect_answer} copies)' if not is_correct else ''}"
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

    total_answered = len([a for a in session.user_answers if a.attempt_number == 1])
    correct_answers = len(
        [a for a in session.user_answers if a.is_correct and a.attempt_number == 1]
    )
    score_percentage = (
        (correct_answers / total_answered * 100) if total_answered > 0 else 0
    )

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



def _process_user_questions(
    user_questions: List[str],
    topics: List[WeightedTopic],
    difficulty: str,
    retriever: DocumentRetriever = None,
) -> List[Question]:
    """Process user-provided questions into Question objects"""
    if not user_questions:
        return []

    logger.info(f"Processing {len(user_questions)} user questions")

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

Quality Standards:
- {difficulty}-appropriate content
- Questions can't be general, they must be very specific.
- Clear question wording
- Test comprehension over memorization
- Provide realistic answer options


For simple True/False questions:
- Provide exactly 2 options: the correct answer and its opposite
- Set is_multi_choice to False

For complex questions:
- Provide 3-4 total options
- Can have multiple correct answers if the question naturally allows it

Provide structured response."""

            response = llm.invoke(prompt)

            choices = []

            for correct_answer in response.correct_answers:
                choices.append(QuestionChoice(text=correct_answer, is_correct=True))

            for wrong_option in response.wrong_options:
                choices.append(QuestionChoice(text=wrong_option, is_correct=False))

            if len(choices) < 2:
                choices.append(QuestionChoice(text="False", is_correct=False))

            source_metadata = None
            if retriever:
                search_results = retriever.search_in_collection(
                    query=question_text, limit=1
                )  
                if search_results:
                    best_match = search_results[0].payload

                    source_metadata = SourceMetadata(
                        source=best_match.get("source", "Unknown source"),
                        page=best_match.get("page", None),
                        slide=best_match.get("slide", None),
                        chunk_text=best_match.get("text", None),
                    )

            question = Question(
                topic=response.assigned_topic,
                question_text=question_text,
                choices=choices,
                explanation=response.explanation,
                difficulty=difficulty,
                is_multi_choice=response.is_multi_choice,
                source_metadata=source_metadata,
            )

            processed_questions.append(question)
            logger.info(f"Processed user question {i + 1}: {question_text[:50]}...")

        except Exception as e:
            logger.error(f"Failed to process user question '{question_text}': {e}")
            fallback_source_metadata = None
            if retriever:
                try:
                    search_results = retriever.search_in_collection(
                        query=question_text, limit=1
                    )
                    if search_results:
                        best_match = search_results[0].payload
                        fallback_source_metadata = SourceMetadata(
                            source=best_match.get("source", "Nieznane źródło"),
                            page=best_match.get("page", None),
                            slide=best_match.get("slide", None),
                            chunk_text=best_match.get("text", None),
                        )
                except Exception as search_error:
                    logger.warning(
                        f"Could not get source metadata for fallback question: {search_error}"
                    )

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
                source_metadata=fallback_source_metadata,
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

Language: Same language as the topic.

{created_questions_text}

{context_text}

Output exactly {count} unique questions following above specifications."""

    try:
        result = llm.invoke(prompt)
        questions = []

        for i, q in enumerate(result.questions):
            q.topic = topic
            q.difficulty = difficulty

            source_metadata = None

            if retriever:
                search_results = retriever.search_in_collection(
                    query=q.question_text, limit=1
                )  

                if search_results:
                    best_match = search_results[0].payload

                    source_metadata = SourceMetadata(
                        source=best_match.get("source", "Unknown source"),
                        page=best_match.get("page", None),
                        slide=best_match.get("slide", None),
                        chunk_text=best_match.get(
                            "text", None
                        ), 
                    )

            q.source_metadata = source_metadata
            logger.debug(f"Source metadata: {source_metadata}")


            questions.append(q)

        unique_questions = _remove_duplicate_questions(questions)

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
            similarity = SequenceMatcher(
                None, question.question_text.lower().strip(), seen_q.lower().strip()
            ).ratio()

            if similarity > 0.7: 
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
        [f"{i + 1}. {choice.text}" for i, choice in enumerate(question.choices)]
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
