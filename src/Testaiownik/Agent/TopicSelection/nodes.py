from trustcall import create_extractor
from typing import Dict, Any, List
from collections import namedtuple
from .state import AgentState
from .models import (
    BatchAnalysis,
    FeedbackInterpretation,
    TopicConsolidation,
    UserFeedback,
)
from AzureModels import get_llm
from RAG.Retrieval import DocumentRetriever, MockRetriever
from utils.logger import logger


def _process_batch(batch_text: str, previous_context: str, extractor) -> Dict[str, Any]:
    """Extract topics from a single batch of documents"""
    prompt = f"""
    {previous_context}
    
    Analyze this batch of educational documents:
    {batch_text}
    
    Extract topics consistent with previous findings and create summaries.
    
    IMPORTANT FOR TOPIC WEIGHTS:
    - Assign weights [0,1] to each topic based on its importance/coverage in the content
    - Weights must sum to exactly 1.0
    - More prominent/frequently discussed topics get higher weights
    - Less important or briefly mentioned topics get lower weights
    - Dont count duplicates, only unique topics


    LANGUAGE: Same as documents language, do not translate.
    """

    result = extractor.invoke({"messages": [prompt]})
    logger.debug(f"Batch analysis result: {result}")
    logger.debug(
        f"Batch analysis return dict: {result['messages'][0].tool_calls[0]['args']}"
    )
    return result["messages"][0].tool_calls[0]["args"]


def _process_single_batch(
    batch_chunks: List[Dict],
    batch_number: int,
    all_topics: List[Dict],
    extractor,
    accumulated_summary: str,
) -> str:
    """Process a single batch of chunks"""

    # Extract text from chunk dictionaries
    batch_texts = [chunk["text"] for chunk in batch_chunks]
    batch_text = "\n---\n".join(batch_texts)

    previous_context = (
        f"Previous topics found: {[t['topic'] for t in all_topics]}\nPrevious summary: {accumulated_summary}"
        if accumulated_summary
        else "This is the first batch."
    )

    logger.debug(f"Processing batch {batch_number} with {len(batch_chunks)} chunks")

    batch_analysis = _process_batch(batch_text, previous_context, extractor)
    all_topics.extend(batch_analysis["current_topics"])

    # Update accumulated summary
    accumulated_summary = batch_analysis["accumulated_summary"]

    logger.info(
        f"Batch {batch_number}: found {len(batch_analysis['current_topics'])} topics"
    )

    return accumulated_summary


def _process_batches(
    retriever: DocumentRetriever,
    batch_size: int,
    all_topics: List[Dict],
    extractor,
    accumulated_summary: str,
    processed_chunks: List[Dict],
) -> None:
    """Process chunks in streaming batches without loading all into memory"""

    current_batch = []
    batch_number = 1

    # Stream chunks and process in batches
    for chunk in retriever.get_all_chunks():
        current_batch.append(chunk)
        processed_chunks.append(chunk)  # Keep track for final state

        # When we have a full batch, process it
        if len(current_batch) >= batch_size:
            _process_single_batch(
                current_batch, batch_number, all_topics, extractor, accumulated_summary
            )
            current_batch.clear()  # Free memory
            batch_number += 1

    # Process any remaining chunks in the last partial batch
    if current_batch:
        _process_single_batch(
            current_batch, batch_number, all_topics, extractor, accumulated_summary
        )

    logger.info(
        f"Total topics found: {len(all_topics)}. Accumulated summary: {accumulated_summary}"
    )

    # Normalize weights
    total_weight = sum(topic["weight"] for topic in all_topics)
    if total_weight > 0:
        for topic in all_topics:
            topic["weight"] = round(topic["weight"] / total_weight, 2)


# _prepare_history_fields output
HistoryFields = namedtuple(
    "HistoryFields",
    [
        "history_context",
        "latest_user_feedback",
        "information_about_feedback",
        "additional_instructions",
    ],
)


def _prepare_history_fields(history: List[Dict]) -> HistoryFields:
    history_context = "CONVERSATION HISTORY:\n".join(
        [
            f"Iteration {i + 1}: Generated {len(h['suggested_topics'])} topics, User said: '{h['user_feedback']}'"
            for i, h in enumerate(history)
        ]
    )
    latest_user_feedback = f"Latest user feedback: {history[-1]['user_feedback']}"
    information_about_feedback = """  Information about feedback:
                            1. User feedback preferences are provided in the conversation history.
                            2. User feedback is used to refine topic selection and importance.
                            3. User feedback can suggest adding a topic, deleting a topic, or modifying existing topics."""
    additional_instructions = """ and
                                        Full conversation evolution
                                        User feedback preferences
                                    """

    return HistoryFields(
        history_context,
        latest_user_feedback,
        information_about_feedback,
        additional_instructions,
    )


def _consolidate_topics_with_history(
    all_topics: List[Dict],
    rejected_topics: List[str],
    history: List[Dict],
    desired_topic_count: int = 10,
) -> List[Dict[str, Any]]:
    """Consolidate topics considering conversation history"""

    consolidation_llm = get_llm().with_structured_output(TopicConsolidation)

    # History texts
    history_context = ""
    latest_user_feedback = ""
    information_about_feedback = ""
    additional_instructions = ""

    logger.debug(f"History: {history}")
    if history:
        (
            history_context,
            latest_user_feedback,
            information_about_feedback,
            additional_instructions,
        ) = _prepare_history_fields(history)

    topics_with_weights = [
        f"{t['topic']} (weight: {t['weight']:.2f})" for t in all_topics
    ]

    prompt = f"""
    {history_context}
    
    Current extracted topics with weights: {topics_with_weights}
    {latest_user_feedback}



    {information_about_feedback}
    

    

    Information about topics:
    1. They are extracted from indepentent batches of documents
    2. They have weights assigned batch-wise.

    Avoid those topics, they were blacklisted by a user:
    {rejected_topics}
    
    Generate consolidated topics considering:
    
    1. Topic importance weights from content analysis
    1. Avoiding duplicates

    {additional_instructions}


    IMPORTANT:
    1. Try to match the number of topics to: {desired_topic_count}
   


    OUTPUT FORMAT:
    In "topic" section please include only topic name, nothing more, especially NO WEIGHTS.
    
    IMPORTANT FOR WEIGHTS:
    - Assign weights [0,1] based on topic importance and user preferences
    - Higher weights for topics that are more frequently mentioned or referenced.
    - Weights must sum to exactly 1.0
    - Consider original content coverage when assigning weights


    LANGUAGE: Same as documents language, do not translate.

    PLEASE REASSIGN WEIGHTS TO TOPICS, DO NOT USE PREVIOUS WEIGHTS. YOU CAN SUM PREVIOUS WEIGHTS AND REASSIGN THEM PROPORTIONALLY SUMMING TO 1.0.
    """

    consolidation_result = consolidation_llm.invoke(prompt)

    topics = consolidation_result.consolidated_topics
    total_weight = sum(topic["weight"] for topic in all_topics)
    if total_weight > 0:
        for topic in all_topics:
            topic["weight"] = round(topic["weight"] / total_weight, 2)

    return topics


def analyze_documents(
    state: AgentState,
    retriever: DocumentRetriever = None,
    batch_size: int = 40,  # 50 is too much.
) -> AgentState:
    """Main document analysis orchestrator"""
    if retriever is None:
        retriever = MockRetriever()

    chunk_count = retriever.get_chunk_count()
    logger.info(f"Processing {chunk_count} chunks in batches of {batch_size}.")

    # Setup extraction
    llm = get_llm()
    extractor = create_extractor(
        llm, tools=[BatchAnalysis], tool_choice="BatchAnalysis"
    )

    all_topics = []  # List to accumulate topics with weights
    accumulated_summary = ""
    processed_chunks = []

    # Process in batches

    _process_batches(
        retriever,
        batch_size,
        all_topics,
        extractor,
        accumulated_summary,
        processed_chunks,
    )

    history = state.get("conversation_history", [])
    rejected_topics = state.get("rejected_topics", [])
    desired_topic_count = state.get("desired_topic_count", 10)
    # Consolidate topics with conversation history
    final_topics = _consolidate_topics_with_history(
        all_topics, rejected_topics, history, desired_topic_count
    )

    return {
        **state,
        "suggested_topics": final_topics,
        "user_input": None,
        "next_node": "request_feedback",
    }


def request_feedback(state: AgentState) -> AgentState:
    suggested = state.get("suggested_topics", [])

    feedback_request = f"""
    Found topics:
    {chr(10).join(f"{i}: {topic}" for i, topic in enumerate(suggested))}
    
    Provide feedback on given topics please.
    """

    logger.info(f"Feedback request: {feedback_request}")

    return {
        **state,
        "feedback_request": feedback_request,
        "next_node": "process_feedback",
    }


def _calculate_new_topic_count(
    feedback: UserFeedback, current_topics: List[str]
) -> int:
    """Calculate new desired topic count based on user feedback"""

    # Calculate based on modifications
    # Start with topics user wants to keep
    kept_topics = (
        set(feedback.accepted_topics)
        if feedback.accepted_topics
        else set(current_topics)
    )

    # Remove rejected topics
    if feedback.rejected_topics:
        kept_topics -= set(feedback.rejected_topics)

    # Add new topics user wants
    total_wanted = len(kept_topics) + len(feedback.want_to_add_topics or [])

    return max(1, total_wanted)


def process_feedback(state: AgentState) -> AgentState:
    suggested = state.get("suggested_topics", [])
    user_input = state.get("user_input", "")
    history = state.get("conversation_history", [])
    logger.info(f"Processing user input: {user_input}")

    # Add current interaction to history
    if user_input and suggested:
        history.append(
            {
                "suggested_topics": suggested.copy(),
                "user_feedback": user_input,
            }
        )
    logger.info(f"Conversation history: {history}")

    if not user_input:
        return {**state, "next_node": "request_feedback"}

    llm = get_llm().with_structured_output(FeedbackInterpretation)

    prompt = f"""
    Suggested topics: {suggested}
    User feedback: "{user_input}"
    
    Previous conversation history:
    {chr(10).join([f"Topics: {h['suggested_topics']} -> User: {h['user_feedback']}" for h in history[:-1]])}
    
    
    Interpret user intent and extract structured feedback.

    If user wants to accept the topics, return them in "accepted_topics".
    If user wants to modify topics, return modification request in "modification_request":
        1. If user want to reject a topic, consider changing the nummber of desired_topic_count
        2. If user want to add a specific topic, consider changing the number of desired_topic_count
    """

    logger.info(f"Processing feedback with prompt: {prompt}")

    interpretation = llm.invoke(prompt)

    feedback = interpretation.user_feedback
    logger.debug(f"Full feedback: {feedback}")
    logger.info(f"Action: {feedback.action}")

    if feedback.action == "accept":
        return {
            **state,
            "confirmed_topics": suggested,
            "conversation_history": history,  # Because history is a copy
            "next_node": "END",
        }
    elif feedback.action == "modify":
        new_desired_count = _calculate_new_topic_count(
            feedback=feedback,
            current_topics=suggested,
        )
        rejected_topics = state.get("rejected_topics", []).copy()
        rejected_topics.extend(feedback.rejected_topics or [])  # Extend black list

        return {
            **state,
            "feedback_request": feedback.modification_request,
            "rejected_topics": rejected_topics,
            "conversation_history": history,  # Because history is a copy
            "desired_topic_count": new_desired_count,
            "next_node": "analyze_documents",  # loop
        }
    else:
        # Error
        logger.error("Literal of [accept,modify] broken")
        return {**state, "next_node": "request_feedback"}  # loop


# Function to route in conditional edges
def route_next(state: AgentState) -> str:
    next_node = state.get("next_node", "END")
    logger.info(f"Routing to next node: {next_node}")
    return next_node if next_node != "END" else "__end__"


if __name__ == "__main__":
    pass
