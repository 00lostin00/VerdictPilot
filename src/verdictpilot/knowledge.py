from __future__ import annotations

import hashlib
import math
import sqlite3
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from .models import RetrievedDocument
from .tokenization import tokenize


@dataclass(frozen=True, slots=True)
class _Document:
    doc_id: str
    title: str
    body: str
    source: str
    tags: str


class KnowledgeStore:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=15000")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS knowledge_documents (
                    doc_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    body TEXT NOT NULL,
                    source TEXT NOT NULL,
                    tags TEXT NOT NULL,
                    content_hash TEXT NOT NULL
                )
                """
            )

    def bootstrap(self, knowledge_dir: Path) -> int:
        self.initialize()
        files = sorted(knowledge_dir.glob("*.md"))
        seen: set[str] = set()
        with self._connect() as connection:
            for path in files:
                raw = path.read_text(encoding="utf-8").strip()
                if not raw:
                    continue
                lines = raw.splitlines()
                title = lines[0].removeprefix("#").strip() or path.stem
                tags = path.stem.replace("-", " ")
                doc_id = path.stem
                digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
                connection.execute(
                    """
                    INSERT INTO knowledge_documents
                        (doc_id, title, body, source, tags, content_hash)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(doc_id) DO UPDATE SET
                        title=excluded.title,
                        body=excluded.body,
                        source=excluded.source,
                        tags=excluded.tags,
                        content_hash=excluded.content_hash
                    """,
                    (doc_id, title, raw, str(path.relative_to(knowledge_dir.parent)), tags, digest),
                )
                seen.add(doc_id)
            if seen:
                placeholders = ",".join("?" for _ in seen)
                connection.execute(
                    f"DELETE FROM knowledge_documents WHERE doc_id NOT IN ({placeholders})",
                    tuple(sorted(seen)),
                )
            else:
                connection.execute("DELETE FROM knowledge_documents")
        return len(seen)

    def _all_documents(self) -> list[_Document]:
        self.initialize()
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT doc_id, title, body, source, tags FROM knowledge_documents"
            ).fetchall()
        return [_Document(**dict(row)) for row in rows]

    def documents(self) -> list[dict[str, str]]:
        return [
            {"id": doc.doc_id, "title": doc.title, "source": doc.source, "body": doc.body}
            for doc in self._all_documents()
        ]

    def search(self, query: str, limit: int = 4) -> list[RetrievedDocument]:
        documents = self._all_documents()
        query_tokens = tokenize(query)
        if not documents or not query_tokens:
            return []

        tokenized = [tokenize(f"{doc.title} {doc.tags} {doc.body}") for doc in documents]
        frequencies = [Counter(tokens) for tokens in tokenized]
        document_frequency = Counter(token for tokens in tokenized for token in set(tokens))
        average_length = sum(map(len, tokenized)) / len(tokenized)
        k1, b = 1.5, 0.75
        scores: list[tuple[float, _Document]] = []

        for doc, tokens, frequency in zip(documents, tokenized, frequencies, strict=True):
            score = 0.0
            title_tokens = set(tokenize(f"{doc.title} {doc.tags}"))
            for token in query_tokens:
                tf = frequency[token]
                if not tf:
                    continue
                df = document_frequency[token]
                inverse_document_frequency = math.log(1 + (len(documents) - df + 0.5) / (df + 0.5))
                denominator = tf + k1 * (1 - b + b * len(tokens) / max(average_length, 1.0))
                score += inverse_document_frequency * (tf * (k1 + 1)) / denominator
                if token in title_tokens:
                    score += inverse_document_frequency * 0.8
            if score > 0:
                scores.append((score, doc))

        scores.sort(key=lambda item: (-item[0], item[1].doc_id))
        return [
            RetrievedDocument(
                doc_id=doc.doc_id,
                title=doc.title,
                source=doc.source,
                score=round(score, 4),
                snippet=self._snippet(doc.body, query_tokens),
            )
            for score, doc in scores[: max(1, min(limit, 10))]
        ]

    @staticmethod
    def _snippet(body: str, query_tokens: list[str], max_chars: int = 220) -> str:
        compact = " ".join(line.strip() for line in body.splitlines() if line.strip())
        lowered = compact.lower()
        positions = [lowered.find(token) for token in query_tokens if len(token) > 1]
        positions = [position for position in positions if position >= 0]
        start = max(0, (min(positions) if positions else 0) - 45)
        snippet = compact[start : start + max_chars]
        if start:
            snippet = "..." + snippet
        if start + max_chars < len(compact):
            snippet += "..."
        return snippet
