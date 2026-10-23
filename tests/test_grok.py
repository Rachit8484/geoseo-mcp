"""xAI Grok engine tests (mocked HTTP)."""

from __future__ import annotations

import json

import httpx
import pytest

from geoseo_mcp import config
from geoseo_mcp.engines import grok, multi_llm
from geoseo_mcp.engines.base import EngineError, EngineNotConfiguredError

RESPONSE = {
    "model": "grok-4.3",
    "output": [
        {"type": "web_search_call", "status": "completed"},
        {
            "type": "message",
            "role": "assistant",
            "content": [
                {
                    "type": "output_text",
                    "text": "Use a tracker.[[1]](https://www.example.com/guide) "
                    "Also see [[2]](https://docs.other.org/x).",
                    "annotations": [
                        {"type": "url_citation", "url": "https://www.example.com/guide",
                         "start_index": 14, "end_index": 47, "title": "1"},
                        {"type": "url_citation", "url": "https://docs.other.org/x",
                         "start_index": 58, "end_index": 85, "title": "2"},
                    ],
                }
            ],
        },
    ],
    "citations": [
        "https://www.example.com/guide",
        "https://docs.other.org/x",
        "https://ignored.net/",
    ],
    "usage": {"input_tokens": 10, "output_tokens": 20},
}


@pytest.fixture
def env(monkeypatch):
    for k in ("GEOSEO_PERPLEXITY_API_KEY", "GEOSEO_OPENAI_API_KEY", "GEOSEO_ANTHROPIC_API_KEY",
              "GEOSEO_GEMINI_API_KEY", "GEOSEO_GROK_API_KEY", "GEOSEO_GROK_MODEL"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("GEOSEO_XAI_API_KEY", "xai-test")
    monkeypatch.setattr(config, "_cached", None)
    yield monkeypatch
    config._cached = None


def _mock(monkeypatch, handler):
    real = httpx.Client

    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real(*args, **kwargs)

    monkeypatch.setattr(grok.httpx, "Client", factory)


def test_query_parses_annotations_and_sends_web_search(env):
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=RESPONSE)

    _mock(env, handler)
    out = grok.query("best sober apps?", system_prompt="be brief", x_search=True)
    assert seen["url"] == grok.XAI_RESPONSES_ENDPOINT
    assert seen["auth"] == "Bearer xai-test"
    assert seen["body"]["model"] == "grok-4.3"
    assert seen["body"]["tools"] == [{"type": "web_search"}, {"type": "x_search"}]
    assert seen["body"]["instructions"] == "be brief"
    assert out["engine"] == "grok"
    assert out["citations"] == ["https://www.example.com/guide", "https://docs.other.org/x"]
    assert out["cited_domains"] == ["docs.other.org", "example.com"]
    assert "https://ignored.net/" in out["sources_considered"]
    assert "ignored.net" not in out["cited_domains"]


def test_inline_links_used_when_annotations_missing(env):
    data = json.loads(json.dumps(RESPONSE))
    data["output"][1]["content"][0]["annotations"] = []
    _mock(env, lambda r: httpx.Response(200, json=data))
    out = grok.query("q")
    assert out["citations"] == ["https://www.example.com/guide", "https://docs.other.org/x"]


def test_errors(env):
    _mock(env, lambda r: httpx.Response(429, text="rate limited"))
    with pytest.raises(EngineError, match="xAI 429"):
        grok.query("q")
    env.delenv("GEOSEO_XAI_API_KEY")
    config._cached = None
    with pytest.raises(EngineNotConfiguredError):
        grok.query("q")


def test_grok_joins_multi_llm(env):
    _mock(env, lambda r: httpx.Response(200, json=RESPONSE))
    assert multi_llm.list_configured_engines() == ["grok"]
    out = multi_llm.multi_citation_check(["q1"], "example.com")
    assert "grok" in json.dumps(out)
