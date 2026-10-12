from __future__ import annotations

import re

_PART_RE = re.compile(r"[A-Za-z0-9_+#.-]+|[\u3400-\u4dbf\u4e00-\u9fff]+")


def tokenize(text: str) -> list[str]:
    """Tokenize English identifiers and Chinese text for lightweight BM25 retrieval.

    Chinese spans contribute unigrams and bigrams so queries work without an external
    segmentation model. Duplicate tokens are intentionally retained for term frequency.
    """

    tokens: list[str] = []
    for match in _PART_RE.finditer(text.lower()):
        part = match.group(0)
        if "\u3400" <= part[0] <= "\u9fff":
            chars = list(part)
            tokens.extend(chars)
            tokens.extend("".join(chars[i : i + 2]) for i in range(len(chars) - 1))
        else:
            tokens.append(part.strip(".-"))
    return [token for token in tokens if token]
