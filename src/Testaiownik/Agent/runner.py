from Agent.graph import create_agent_graph
from RAG.Retrieval import MockRetriever, RAGRetriever, DocumentRetriever


def run_agent(retriever: DocumentRetriever):
    graph = create_agent_graph(retriever=retriever)
    config = {"configurable": {"thread_id": "test-run"}}

    state = {
        "materials": [],
        "suggested_topics": [],
        "confirmed_topics": [],
        "user_input": None,
        "feedback_request": None,
        "next_node": "",
        "messages": [],
    }

    # Run until interrupt
    graph.invoke(state, config)

    while True:
        # logger.info(f"Graph state result: {result}")
        # Show feedback request
        current_state = graph.get_state(config)

        if current_state.next == ():  # Execution finished
            break

        # Get user input
        print(current_state.values.get("feedback_request", ""))
        user_input = input("\nYour feedback: ")

        # Continue with user input
        graph.update_state(config, {"user_input": user_input})
        graph.invoke(None, config)

    print(
        f"\nFinal topics: {graph.get_state(config).values.get('confirmed_topics', [])}"
    )


if __name__ == "__main__":
    run_agent()
