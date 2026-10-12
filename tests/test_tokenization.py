from verdictpilot.tokenization import tokenize


def test_tokenize_keeps_english_and_chinese_bigrams() -> None:
    tokens = tokenize("BFS 网格最短路 C++")
    assert "bfs" in tokens
    assert "网格" in tokens
    assert "最短" in tokens
    assert "c++" in tokens
