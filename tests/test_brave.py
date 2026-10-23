"""Brave Answers engine tests (mocked SSE stream)."""

from __future__ import annotations

import json

import httpx
import pytest

from geoseo_mcp import config
from geoseo_mcp.engines import brave, multi_llm
from geoseo_mcp.engines.base import EngineError, EngineNotConfiguredError


def _chunk(content: str) -> str:
    return "data: " + json.dumps(
        {"object": "chat.completion.chunk", "choices": [{"index": 0, "delta": {"content": content}}]}
    )


CIT1 = {"start_index": 0, "end_index": 10, "number": 1,
        "url": "https://www.example.com/a", "favicon": "", "snippet": "s1"}
CIT2 = {"start_index": 11, "end_index": 20, "number": 2,
        "url": "https://other.org/b", "favicon": "", "snippet": "s2"}
USAGE = {"X-Request-Queries": 1, "X-Request-Total-Cost": 0.01}

SSE = "\n\n".join([
    _chunk("Sober apps help"),
    _chunk(f"<citation>{json.dumps(CIT1)}</citation>"),
    _chunk(" a lot."),
    _chunk(f"<citation>{json.dumps(CIT2)}</citation>"),
    _chunk(f"<citation>{json.dumps(CIT1)}</citation>"),
    _chunk(f"<usage>{json.dumps(USAGE)}</usage>"),
    "data: [DONE]",
]) + "\n\n"


@pytest.fixture
def env(monkeypatch):
    for k in ("GEOSEO_PERPLEXITY_API_KEY", "GEOSEO_OPENAI_API_KEY", "GEOSEO_ANTHROPIC_API_KEY",
              "GEOSEO_GEMINI_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("GEOSEO_BRAVE_API_KEY", "brave-test")
    monkeypatch.setattr(config, "_cached", None)
    yield monkeypatch
    config._cached = None


def _mock(monkeypatch, handler):
    real = httpx.Client

    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real(*args, **kwargs)

    monkeypatch.setattr(brave.httpx, "Client", factory)


def test_parse_content_strips_tags():
    raw = "".join(brave.iter_sse_content(SSE.splitlines()))
    answer, cits, usage = brave.parse_content(raw)
    assert answer == "Sober apps help[1] a lot.[2][1]"
    assert [c["url"] for c in cits] == [CIT1["url"], CIT2["url"], CIT1["url"]]
    assert usage == USAGE


def test_query_streams_and_dedupes(env):
    seen = {}

    def handler(request):
        seen["token"] = request.headers["x-subscription-token"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, text=SSE, headers={"content-type": "text/event-stream"})

    _mock(env, handler)
    out = brave.query("best sober apps?")
    assert seen["token"] == "brave-test"
    assert seen["body"]["stream"] is True and seen["body"]["enable_citations"] is True
    assert seen["body"]["model"] == "brave"
    assert out["citations"] == ["https://www.example.com/a", "https://other.org/b"]
    assert out["cited_domains"] == ["example.com", "other.org"]
    assert out["usage"]["X-Request-Total-Cost"] == 0.01


def test_errors(env):
    _mock(env, lambda r: httpx.Response(402, text="plan required"))
    with pytest.raises(EngineError, match="Brave 402"):
        brave.query("q")
    env.delenv("GEOSEO_BRAVE_API_KEY")
    config._cached = None
    with pytest.raises(EngineNotConfiguredError):
        brave.query("q")


def test_brave_joins_multi_llm(env):
    _mock(env, lambda r: httpx.Response(200, text=SSE))
    assert multi_llm.list_configured_engines() == ["brave"]
    out = multi_llm.multi_citation_check(["q1"], "example.com")
    assert "brave" in json.dumps(out)
