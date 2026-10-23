"""Optional embedding backends for internal-link suggestions.

TF-IDF stays the default (zero deps, zero cost). These backends trade a bit of
setup for better topical matching — they catch pages that mean the same thing
without sharing many words:

- ``openai``: ``text-embedding-3-small`` (needs ``GEOSEO_OPENAI_API_KEY``)
- ``gemini``: ``gemini-embedding-001`` (needs ``GEOSEO_GEMINI_API_KEY``)
- ``local``:  ``sentence-transformers`` model ``all-MiniLM-L6-v2`` (needs
  ``pip install sentence-transformers``; runs on your machine, no API calls)

Vectors are cached in the geoseo SQLite DB keyed by (mode, model, sha256 of
the text), so re-running on an unchanged site costs nothing.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Callable, Sequence
from typing import Any

import httpx

from ..config import get_config
from ..storage import sqlite as store

MODES = ("tfidf", "openai", "gemini", "local")
DEFAULT_MODELS = {
    "openai": "text-embedding-3-small",
    "gemini": "gemini-embedding-001",
    "local": "all-MiniLM-L6-v2",
}
OPENAI_EMBEDDINGS_URL = "https://api.openai.com/v1/embeddings"
GEMINI_BATCH_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:batchEmbedContents"
)
_BATCH = 100

_DDL = """
CREATE TABLE IF NOT EXISTS embedding_cache (
    mode TEXT NOT NULL,
    model TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    vector_json TEXT NOT NULL,
    PRIMARY KEY (mode, model, content_hash)
)
"""


class EmbeddingError(RuntimeError):
    pass


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def embed(
    texts: list[str],
    mode: str,
    model: str | None = None,
    use_cache: bool = True,
) -> tuple[list[list[float]], dict[str, Any]]:
    """Embed ``texts``; return (vectors, stats). Raises EmbeddingError."""
    if mode not in DEFAULT_MODELS:
        raise EmbeddingError(f"Unknown embedding mode {mode!r}; use one of {MODES}.")
    model = model or DEFAULT_MODELS[mode]
    hashes = [content_hash(t) for t in texts]

    cached: dict[str, list[float]] = _cache_get(mode, model, set(hashes)) if use_cache else {}
    missing_idx = [i for i, h in enumerate(hashes) if h not in cached]
    # De-dupe identical texts before calling the provider.
    todo: dict[str, str] = {}
    for i in missing_idx:
        todo.setdefault(hashes[i], texts[i])

    fresh: dict[str, list[float]] = {}
    if todo:
        backend = _backend(mode)
        keys = list(todo)
        for start in range(0, len(keys), _BATCH):
            chunk = keys[start:start + _BATCH]
            vecs = backend([todo[k] for k in chunk], model)
            if len(vecs) != len(chunk):
                raise EmbeddingError(f"{mode} returned {len(vecs)} vectors for {len(chunk)} texts")
            fresh.update(zip(chunk, vecs, strict=True))
        if use_cache:
            _cache_put(mode, model, fresh)

    allv = {**cached, **fresh}
    stats = {
        "mode": mode,
        "model": model,
        "texts": len(texts),
        "cache_hits": len(texts) - len(missing_idx),
        "embedded_now": len(fresh),
    }
    return [allv[h] for h in hashes], stats


# --- backends --------------------------------------------------------------

def _backend(mode: str) -> Callable[[list[str], str], list[list[float]]]:
    return {"openai": _openai, "gemini": _gemini, "local": _local}[mode]


def _openai(texts: list[str], model: str) -> list[list[float]]:
    cfg = get_config()
    if not cfg.openai_api_key:
        raise EmbeddingError("mode='openai' needs GEOSEO_OPENAI_API_KEY.")
    with httpx.Client(timeout=max(cfg.request_timeout_s, 60.0)) as c:
        r = c.post(
            OPENAI_EMBEDDINGS_URL,
            json={"model": model, "input": texts},
            headers={"Authorization": f"Bearer {cfg.openai_api_key}"},
        )
    if r.status_code >= 400:
        raise EmbeddingError(f"OpenAI embeddings {r.status_code}: {r.text[:300]}")
    data = sorted(r.json().get("data", []), key=lambda d: d.get("index", 0))
    return [d["embedding"] for d in data]


def _gemini(texts: list[str], model: str) -> list[list[float]]:
    cfg = get_config()
    if not cfg.gemini_api_key:
        raise EmbeddingError("mode='gemini' needs GEOSEO_GEMINI_API_KEY.")
    body = {
        "requests": [
            {
                "model": f"models/{model}",
                "content": {"parts": [{"text": t}]},
                "taskType": "SEMANTIC_SIMILARITY",
            }
            for t in texts
        ]
    }
    with httpx.Client(timeout=max(cfg.request_timeout_s, 60.0)) as c:
        r = c.post(
            GEMINI_BATCH_URL.format(model=model),
            json=body,
            headers={"x-goog-api-key": cfg.gemini_api_key},
        )
    if r.status_code >= 400:
        raise EmbeddingError(f"Gemini embeddings {r.status_code}: {r.text[:300]}")
    return [e["values"] for e in r.json().get("embeddings", [])]


_local_models: dict[str, Any] = {}


def _local(texts: list[str], model: str) -> list[list[float]]:
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore[import-not-found]
    except ImportError as e:
        raise EmbeddingError(
            "mode='local' needs sentence-transformers: pip install sentence-transformers"
        ) from e
    if model not in _local_models:
        _local_models[model] = SentenceTransformer(model)
    vecs = _local_models[model].encode(texts, normalize_embeddings=True)
    return [[float(x) for x in v] for v in vecs]


# --- cache -----------------------------------------------------------------

def _cache_get(mode: str, model: str, hashes: set[str]) -> dict[str, list[float]]:
    if not hashes:
        return {}
    out: dict[str, list[float]] = {}
    with store._connect() as conn:
        conn.execute(_DDL)
        hl = list(hashes)
        for start in range(0, len(hl), 500):
            chunk = hl[start:start + 500]
            q = ",".join("?" * len(chunk))
            rows = conn.execute(
                "SELECT content_hash, vector_json FROM embedding_cache "
                f"WHERE mode=? AND model=? AND content_hash IN ({q})",
                (mode, model, *chunk),
            ).fetchall()
            for row in rows:
                out[row["content_hash"]] = json.loads(row["vector_json"])
    return out


def _cache_put(mode: str, model: str, vecs: dict[str, list[float]]) -> None:
    if not vecs:
        return
    with store._connect() as conn:
        conn.execute(_DDL)
        conn.executemany(
            "INSERT OR REPLACE INTO embedding_cache(mode, model, content_hash, vector_json) "
            "VALUES (?, ?, ?, ?)",
            [(mode, model, h, json.dumps(v)) for h, v in vecs.items()],
        )
        conn.commit()
