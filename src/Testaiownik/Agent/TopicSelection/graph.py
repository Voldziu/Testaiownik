# src/testaiownik/agent/graph.py

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from functools import partial
from RAG.Retrieval import DocumentRetriever
from .state import AgentState
from .nodes import analyze_documents, request_feedback, process_feedback, route_next
from utils import logger


def create_agent_graph(retriever: DocumentRetriever = None) -> StateGraph:
    workflow = StateGraph(AgentState)
    logger.info("Creating agent graph")

    # workflow.add_node(START, "analyze_documents")
    workflow.add_node(
        "analyze_documents", partial(analyze_documents, retriever=retriever)
    )
    workflow.add_node("request_feedback", request_feedback)
    workflow.add_node("process_feedback", process_feedback)

    workflow.add_conditional_edges(
        "analyze_documents",
        route_next,
        {"request_feedback": "request_feedback", "__end__": END},
    )

    workflow.add_conditional_edges(
        "request_feedback",
        route_next,
        {"process_feedback": "process_feedback", "__end__": END},
    )

    workflow.add_conditional_edges(
        "process_feedback",
        route_next,
        {
            "request_feedback": "request_feedback",
            "analyze_documents": "analyze_documents",
            "__end__": END,
        },
    )

    workflow.set_entry_point("analyze_documents")

    return workflow.compile(
        checkpointer=MemorySaver(), interrupt_before=["process_feedback"]
    )
