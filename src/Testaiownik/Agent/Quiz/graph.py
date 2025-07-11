from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from .state import QuizState
from .nodes import (
    initialize_quiz,
    load_or_generate_questions,
    generate_all_questions,
    present_question,
    process_answer,
    check_completion,
    finalize_results,
    route_next,
)
from RAG.Retrieval import DocumentRetriever
from utils import logger


def create_quiz_graph(retriever: DocumentRetriever) -> StateGraph:
    """Create the quiz execution graph"""
    workflow = StateGraph(QuizState)
    logger.info("Creating quiz graph")

    from functools import partial

    generate_questions_with_retriever = partial(
        generate_all_questions, retriever=retriever
    )

    workflow.add_node("initialize_quiz", initialize_quiz)
    workflow.add_node("load_or_generate_questions", load_or_generate_questions)
    workflow.add_node("generate_all_questions", generate_questions_with_retriever)
    workflow.add_node("present_question", present_question)
    workflow.add_node("process_answer", process_answer)
    workflow.add_node("check_completion", check_completion)
    workflow.add_node("finalize_results", finalize_results)

    workflow.add_conditional_edges(
        "initialize_quiz",
        route_next,
        {
            "load_or_generate_questions": "load_or_generate_questions",
            "__end__": END,
        },
    )

    workflow.add_conditional_edges(
        "load_or_generate_questions",
        route_next,
        {
            "generate_all_questions": "generate_all_questions",
            "present_question": "present_question",
            "__end__": END,
        },
    )

    workflow.add_conditional_edges(
        "generate_all_questions",
        route_next,
        {
            "present_question": "present_question",
            "__end__": END,
        },
    )

    workflow.add_conditional_edges(
        "present_question",
        route_next,
        {
            "process_answer": "process_answer",
            "finalize_results": "finalize_results",
            "__end__": END,
        },
    )

    workflow.add_conditional_edges(
        "process_answer",
        route_next,
        {
            "check_completion": "check_completion",
            "__end__": END,
        },
    )

    workflow.add_conditional_edges(
        "check_completion",
        route_next,
        {
            "present_question": "present_question",
            "finalize_results": "finalize_results",
            "__end__": END,
        },
    )

    workflow.add_conditional_edges(
        "finalize_results",
        route_next,
        {
            "__end__": END,
        },
    )

    workflow.set_entry_point("initialize_quiz")

    return workflow.compile(
        checkpointer=MemorySaver(),
        interrupt_before=["process_answer"],  
    )
