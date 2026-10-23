"""Embedding-based internal-link suggestions (mocked providers)."""

from __future__ import annotations

import json

import httpx
import pytest

from geoseo_mcp import config
from geoseo_mcp.graph import embeddings, internal_links

PAGES = {
    "quit-drinking.html": ("How to quit drinking", "Stopping alcohol for good."),
    "sober-curious.html": ("Being sober curious", "Trying a life without booze."),
    "sourdough.html": ("Sourdough starter guide", "Feeding flour and water daily."),
}
# Hand-made vectors: the two sobriety pages point the same way.
VECTORS = {
    "How to quit drinking": [1.0, 0.1, 0.0],
    "Being sober curious": [0.9, 0.2, 0.0],
    "Sourdough starter guide": [0.0, 0.1, 1.0],
}


@pytest.fixture
def site(tmp_path, monkeypatch):
    for name, (title, desc) in PAGES.items():
        (tmp_path / name).write_text(
            f"<html><head><title>{title}</title>"
            f'<meta name="description" content="{desc}"></head>'
            f"<body><h1>{title}</h1><p>{desc}</p></body></html>"
        )
    monkeypatch.setenv("GEOSEO_DB", str(tmp_path / "cache.sqlite"))
    monkeypatch.setenv("GEOSEO_OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("GEOSEO_GEMINI_API_KEY", "g-test")
    monkeypatch.setattr(config, "_cached", None)
    yield tmp_path
    config._cached = None


def _vec_for(text: str) -> list[float]:
    for title, v in VECTORS.items():
        if text.startswith(title):
            return v
    raise AssertionError(text)


def _mock(monkeypatch, handler):
    real = httpx.Client

    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real(*args, **kwargs)

    monkeypatch.setattr(embeddings.httpx, "Client", factory)


def test_openai_mode_uses_vectors_and_caches(site, monkeypatch):
    calls = []

    def handler(request):
        body = json.loads(request.content)
        calls.append(body)
        assert body["model"] == "text-embedding-3-small"
        data = [{"index": i, "embedding": _vec_for(t)} for i, t in enumerate(body["input"])]
        return httpx.Response(200, json={"data": data})

    _mock(monkeypatch, handler)
    out = internal_links.suggest(str(site), page="quit-drinking.html", mode="openai", top_k=1)
    assert out["mode"] == "openai"
    assert out["suggestions"]["quit-drinking.html"][0]["target"] == "sober-curious.html"
    assert out["embedding"]["embedded_now"] == 3
    assert len(calls) == 1

    again = internal_links.suggest(str(site), page="quit-drinking.html", mode="openai", top_k=1)
    assert again["embedding"]["cache_hits"] == 3
    assert again["embedding"]["embedded_now"] == 0
    assert len(calls) == 1  # served from SQLite


def test_gemini_mode_request_shape(site, monkeypatch):
    def handler(request):
        assert "gemini-embedding-001:batchEmbedContents" in str(request.url)
        assert request.headers["x-goog-api-key"] == "g-test"
        reqs = json.loads(request.content)["requests"]
        assert reqs[0]["model"] == "models/gemini-embedding-001"
        return httpx.Response(200, json={"embeddings": [
            {"values": _vec_for(r["content"]["parts"][0]["text"])} for r in reqs
        ]})

    _mock(monkeypatch, handler)
    out = internal_links.suggest(str(site), page="sourdough.html", mode="gemini", top_k=2)
    targets = [s["target"] for s in out["suggestions"]["sourdough.html"]]
    assert len(targets) == 2


def test_missing_key_and_bad_mode(site, monkeypatch):
    monkeypatch.delenv("GEOSEO_OPENAI_API_KEY")
    config._cached = None
    assert "GEOSEO_OPENAI_API_KEY" in internal_links.suggest(str(site), mode="openai")["error"]
    assert "Unknown mode" in internal_links.suggest(str(site), mode="bert")["error"]


def test_tfidf_is_still_default(site):
    out = internal_links.suggest(str(site))
    assert out["mode"] == "tfidf"
    assert "embedding" not in out
