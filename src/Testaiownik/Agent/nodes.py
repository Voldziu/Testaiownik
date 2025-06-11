from utils import logger
from trustcall import create_extractor

from Agent.state import AgentState
from Agent.models import BatchAnalysis, FeedbackInterpretation, TopicConsolidation
from AzureModels import get_llm
from RAG.Retrieval import DocumentRetriever, MockRetriever


def analyze_documents(
    state: AgentState, retriever: DocumentRetriever = None, batch_size: int = 2
) -> AgentState:
    if retriever is None:
        retriever = MockRetriever()

    logger.info(
        f"Processing {retriever.get_chunk_count()} chunks in batches of {batch_size}."
    )

    # llm
    # llm = get_llm().with_structured_output(BatchAnalysis)
    llm = get_llm()
    extractor = create_extractor(
        llm, tools=[BatchAnalysis], tool_choice="BatchAnalysis"
    )

    chunks = list(retriever.get_all_chunks())
    all_topics = set()
    accumulated_summary = ""

    # Process in batches
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        batch_text = "\n---\n".join(batch)

        previous_context = (
            f"""
        Previous topics found: {list(all_topics)}
        Previous summary: {accumulated_summary}
        """
            if accumulated_summary
            else "This is the first batch."
        )

        prompt = f"""
        {previous_context}
        
        
        Analyze this batch of educational documents:
        {batch_text}
        
        Extract topics consistent with previous findings and create summaries.
        """

        result = extractor.invoke({"messages": [prompt]})
        # logger.info(f"{result}")
        # logger.info(f"{result.keys()}")
        batch_analysis = result["responses"][0].__dict__
        # logger.debug(f"Batch analysis: {type(batch_analysis)}")
        current_topics = batch_analysis["current_topics"]
        logger.info(f"Current topics: {current_topics}")
        accumulated_summary = batch_analysis["accumulated_summary"]

        # Update accumulated state
        all_topics.update(current_topics)

        logger.info(
            f"Batch {i//batch_size + 1}: found {len(batch_analysis['current_topics'])} topics"
        )

    history = state.get("conversation_history", [])

    # After all batches, consolidate with full history
    if history:  # If we have conversation history
        consolidation_llm = get_llm().with_structured_output(TopicConsolidation)

        history_context = "\n".join(
            [
                f"Iteration {i+1}: Generated {len(h['suggested_topics'])} topics, User said: '{h['user_feedback']}'"
                for i, h in enumerate(history)
            ]
        )

        prompt = f"""
        CONVERSATION HISTORY:
        {history_context}
        
        Current extracted topics: {list(all_topics)}
        Latest user feedback: "{history[-1]['user_feedback']}"
        
        Generate topics considering the full conversation evolution.
        """

        logger.info(f"Consolidation prompt: {prompt}")

        consolidation_result = consolidation_llm.invoke(prompt)

        final_topics = consolidation_result.consolidated_topics
    else:
        final_topics = list(all_topics)

    return {
        **state,
        "suggested_topics": final_topics,
        "documents": chunks,
        "user_input": None,  # reset user input after processing
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
