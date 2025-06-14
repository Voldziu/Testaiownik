if __name__ == "__main__":
    from Agent.Shared import WeightedTopic

    # Test topics
    test_topics = [
        WeightedTopic(topic="Algorithms", weight=0.6),
        WeightedTopic(topic="Data Structures", weight=0.4),
    ]

    # Create and run quiz
    run_quiz = create_quiz_runner()
    run_quiz(
        confirmed_topics=test_topics,
        total_questions=10,
        difficulty="medium",
        batch_size=3,
    )
