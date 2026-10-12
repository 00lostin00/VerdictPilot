from verdictpilot.memory import MistakeMemory
from verdictpilot.models import NewMistake


def test_mistake_memory_round_trip(settings) -> None:
    memory = MistakeMemory(settings.database_path)
    created = memory.add(
        NewMistake(
            session_id="learner-1",
            problem_title="Shortest Path",
            category="graph",
            symptom="BFS marked visited after dequeue",
            lesson="Mark nodes when enqueueing them.",
        )
    )
    results = memory.search("learner-1", "graph")
    assert results[0].id == created.id
    assert results[0].lesson == "Mark nodes when enqueueing them."
    assert memory.search("another-learner", "graph") == []
