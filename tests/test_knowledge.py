from verdictpilot.knowledge import KnowledgeStore


def test_bm25_retrieves_graph_note(settings) -> None:
    store = KnowledgeStore(settings.database_path)
    assert store.bootstrap(settings.knowledge_dir) >= 5
    results = store.search("网格最短路 BFS visited", limit=3)
    assert results
    assert results[0].doc_id == "graphs"
    assert results[0].source.endswith("graphs.md")


def test_bm25_retrieves_segment_tree_note(settings) -> None:
    store = KnowledgeStore(settings.database_path)
    store.bootstrap(settings.knowledge_dir)
    results = store.search("区间修改 懒标记 线段树", limit=3)
    assert "segment-tree" in [result.doc_id for result in results]
