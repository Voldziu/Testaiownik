from trustcall import create_extractor
from typing import Dict, Any, List
from .state import AgentState
from .models import BatchAnalysis, FeedbackInterpretation, TopicConsolidation
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
    """

    result = extractor.invoke({"messages": [prompt]})
    logger.debug(f"Batch analysis result: {result}")
    logger.debug(
        f"Batch analysis return dict: {result['messages'][0].tool_calls[0]['args']}"
    )
    return result["messages"][0].tool_calls[0]["args"]


def _process_batches(
    chunks: List[str],
    batch_size: int,
    all_topics: List[Dict],
    extractor,
    accumulated_summary: str,
) -> None:
    # Process in batches, returns to
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        batch_text = "\n---\n".join(batch)

        previous_context = (
            f"Previous topics found: {[t['topic'] for t in all_topics]}\nPrevious summary: {accumulated_summary}"
            if accumulated_summary
            else "This is the first batch."
        )

        batch_analysis = _process_batch(batch_text, previous_context, extractor)
        all_topics.extend(batch_analysis["current_topics"])
        accumulated_summary = batch_analysis["accumulated_summary"]

        logger.info(
            f"Batch {i//batch_size + 1}: found {len(batch_analysis['current_topics'])} topics"
        )
    logger.info(
        f"Total topics found: {len(all_topics)}. Accumulated summary: {accumulated_summary}"
    )

    total_weight = sum(topic["weight"] for topic in all_topics)
    if total_weight > 0:
        for topic in all_topics:
            topic["weight"] /= total_weight


def _consolidate_topics_with_history(
    all_topics: List[Dict], history: List[Dict]
) -> List[Dict[str, Any]]:
    """Consolidate topics considering conversation history"""
    if not history:
        return [{"topic": t["topic"], "weight": t["weight"]} for t in all_topics]

    consolidation_llm = get_llm().with_structured_output(TopicConsolidation)

    history_context = "\n".join(
        [
            f"Iteration {i+1}: Generated {len(h['suggested_topics'])} topics, User said: '{h['user_feedback']}'"
            for i, h in enumerate(history)
        ]
    )

    topics_with_weights = [
        f"{t['topic']} (weight: {t['weight']:.2f})" for t in all_topics
    ]

    prompt = f"""
    CONVERSATION HISTORY:
    {history_context}
    
    Current extracted topics with weights: {topics_with_weights}
    Latest user feedback: "{history[-1]['user_feedback']}"

    Information about topics:
    1. They are extracted from indepentent batches of documents
    2. They have weights assigned batch-wise.
    
    Generate consolidated topics considering:
    1. Full conversation evolution
    2. User feedback preferences
    3. Topic importance weights from content analysis
    4. Avoiding duplicates


    OUTPUT FORMAT:
    In "topic" section please include only topic name, nothing more, especially NO WEIGHTS.
    
    IMPORTANT FOR WEIGHTS:
    - Assign weights [0,1] based on topic importance and user preferences
    - Higher weights for topics that are more frequently mentioned or referenced.
    - Weights must sum to exactly 1.0
    - Consider original content coverage when assigning weights

    PLEASE REASSIGN WEIGHTS TO TOPICS, DO NOT USE PREVIOUS WEIGHTS. YOU CAN SUM PREVIOUS WEIGHTS AND REASSIGN THEM PROPORTIONALLY SUMMING TO 1.0.
    """

    consolidation_result = consolidation_llm.invoke(prompt)
    return [
        {"topic": t.topic, "weight": t.weight}
        for t in consolidation_result.consolidated_topics
    ]


def analyze_documents(
    state: AgentState, retriever: DocumentRetriever = None, batch_size: int = 10
) -> AgentState:
    """Main document analysis orchestrator"""
    if retriever is None:
        retriever = MockRetriever()

    logger.info(
        f"Processing {retriever.get_chunk_count()} chunks in batches of {batch_size}."
    )

    # Setup extraction
    llm = get_llm()
    extractor = create_extractor(
        llm, tools=[BatchAnalysis], tool_choice="BatchAnalysis"
    )

    chunks = list(retriever.get_all_chunks())
    all_topics = []  # List to accumulate topics with weights
    accumulated_summary = ""

    # Process in batches

    _process_batches(chunks, batch_size, all_topics, extractor, accumulated_summary)

    history = state.get("conversation_history", [])
    # Consolidate topics with conversation history
    final_topics = _consolidate_topics_with_history(all_topics, history)

    return {
        **state,
        "suggested_topics": final_topics,
        "documents": chunks,
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
    """

    logger.info(f"Processing feedback with prompt: {prompt}")

    interpretation = llm.invoke(prompt)

    feedback = interpretation.user_feedback
    logger.info(f"Action: {feedback.action}")

    if feedback.action == "accept":
        return {
            **state,
            "confirmed_topics": feedback.accepted_topics or suggested,
            "conversation_history": history,  # Because history is a copy
            "next_node": "END",
        }
    elif feedback.action == "modify":
        return {
            **state,
            "feedback_request": feedback.modification_request,
            "conversation_history": history,  # Because history is a copy
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
