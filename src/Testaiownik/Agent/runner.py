from Agent.graph import create_agent_graph
from RAG.Retrieval import MockRetriever
from utils import logger


def run_agent():
    graph = create_agent_graph(MockRetriever())
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
    result = graph.invoke(state, config)

    while result.get("next_node") != "END":
        logger.info(result)
        # Show feedback request
        if "feedback_request" in result:
            print(result["feedback_request"])

        # Get user input
        user_input = input("\nTwój feedback: ")

        # Continue with user input
        result = graph.invoke({**result, "user_input": user_input}, config)

    print(f"\nFinal topics: {result.get('confirmed_topics', [])}")


if __name__ == "__main__":
    run_agent()
