"""Engine wrappers against canned API responses (httpx.MockTransport)."""

from __future__ import annotations

import httpx
import pytest

from geoseo_mcp.engines import anthropic, gemini, multi_llm, openai, perplexity
from geoseo_mcp.engines.base import EngineError, EngineNotConfiguredError

from .conftest import body

OPENAI_RESPONSE = {
    "output": [
        {"type": "web_search_call", "status": "completed"},
        {
            "type": "message",
            "content": [
                {
                    "type": "output_text",
                    "text": "Acme and Rival both work.",
                    "annotations": [
                        {"type": "url_citation", "url": "https://www.acme.com/pricing"},
                        {"type": "url_citation", "url": "https://rival.io/"},
                        {"type": "url_citation", "url": "https://www.acme.com/pricing"},
                    ],
                }
            ],
        },
    ],
    "usage": {"input_tokens": 10, "output_tokens": 20},
}


def test_openai_query(set_env, mock_http) -> None:
    set_env(GEOSEO_OPENAI_API_KEY="sk-test")
    seen = mock_http(lambda req: httpx.Response(200, json=OPENAI_RESPONSE))
    res = openai.query("best crm?")
    req = seen[0]
    assert req.url == "https://api.openai.com/v1/responses"
    assert req.headers["authorization"] == "Bearer sk-test"
    sent = body(req)
    assert sent["tools"] == [{"type": "web_search"}]
    assert sent["model"] == "gpt-5-mini"
    assert res["answer"] == "Acme and Rival both work."
    assert res["citations"] == ["https://www.acme.com/pricing", "https://rival.io/"]
    assert res["cited_domains"] == ["acme.com", "rival.io"]


def test_openai_model_override_via_env(set_env, mock_http) -> None:
    set_env(GEOSEO_OPENAI_API_KEY="sk-test", GEOSEO_OPENAI_MODEL="gpt-5")
    seen = mock_http(lambda req: httpx.Response(200, json=OPENAI_RESPONSE))
    assert openai.query("q")["model"] == "gpt-5"
    assert body(seen[0])["model"] == "gpt-5"


def test_openai_missing_key() -> None:
    with pytest.raises(EngineNotConfiguredError):
        openai.query("q")


def test_openai_http_error(set_env, mock_http) -> None:
    set_env(GEOSEO_OPENAI_API_KEY="sk-test")
    mock_http(lambda req: httpx.Response(429, text="slow down"))
    with pytest.raises(EngineError, match="429"):
        openai.query("q")


def test_anthropic_query(set_env, mock_http) -> None:
    set_env(GEOSEO_ANTHROPIC_API_KEY="ak-test")
    payload = {
        "content": [
            {"type": "server_tool_use", "name": "web_search"},
            {
                "type": "web_search_tool_result",
                "content": [{"type": "web_search_result", "url": "https://blog.acme.com/x"}],
            },
            {
                "type": "text",
                "text": "Acme is popular.",
                "citations": [{"type": "web_search_result_location", "url": "https://acme.com/"}],
            },
        ],
        "usage": {"input_tokens": 1},
    }
    seen = mock_http(lambda req: httpx.Response(200, json=payload))
    res = anthropic.query("q")
    assert seen[0].headers["x-api-key"] == "ak-test"
    assert res["answer"] == "Acme is popular."
    assert set(res["cited_domains"]) == {"acme.com", "blog.acme.com"}


def test_gemini_query_uses_header_key_and_real_domains(set_env, mock_http) -> None:
    set_env(GEOSEO_GEMINI_API_KEY="g-test")
    payload = {
        "candidates": [
            {
                "content": {"parts": [{"text": "Acme leads."}]},
                "groundingMetadata": {
                    "groundingChunks": [
                        {
                            "web": {
                                "uri": "https://vertexaisearch.cloud.google.com/grounding-api-redirect/AbC",
                                "title": "acme.com",
                            }
                        },
                        {
                            "web": {
                                "uri": "https://vertexaisearch.cloud.google.com/grounding-api-redirect/XyZ",
                                "title": "Rival Blog",
                                "domain": "rival.io",
                            }
                        },
                        {"web": {"uri": "https://direct.example.org/page"}},
                    ]
                },
            }
        ]
    }
    seen = mock_http(lambda req: httpx.Response(200, json=payload))
    res = gemini.query("q")
    req = seen[0]
    assert "key=" not in str(req.url)
    assert req.headers["x-goog-api-key"] == "g-test"
    assert body(req)["tools"] == [{"google_search": {}}]
    assert res["cited_domains"] == ["acme.com", "direct.example.org", "rival.io"]


PPLX_AGENT_RESPONSE = {
    "model": "sonar",
    "output": [
        {
            "type": "search_results",
            "queries": ["best crm"],
            "results": [
                {"id": 1, "url": "https://docs.acme.com/start", "title": "Acme"},
                {"id": 2, "url": "https://rival.io/", "title": "Rival"},
                {"id": 3, "url": "https://unused.net/", "title": "Unused"},
            ],
        },
        {
            "type": "message",
            "role": "assistant",
            "content": [{"type": "output_text", "text": "Use Acme [1] or Rival [web:2]."}],
        },
    ],
    "usage": {"input_tokens": 5},
}


def test_perplexity_agent_api(set_env, mock_http) -> None:
    set_env(GEOSEO_PERPLEXITY_API_KEY="p-test")
    seen = mock_http(lambda req: httpx.Response(200, json=PPLX_AGENT_RESPONSE))
    res = perplexity.query("q")
    assert str(seen[0].url) == "https://api.perplexity.ai/v1/agent"
    assert body(seen[0]) == {"input": "q", "effort": "fast"}
    assert res["answer"] == "Use Acme [1] or Rival [web:2]."
    # Only sources the answer actually cites, not every search result.
    assert res["citations"] == ["https://docs.acme.com/start", "https://rival.io/"]
    assert res["cited_domains"] == ["docs.acme.com", "rival.io"]
    assert res["sources_considered"] == 3


def test_perplexity_payload_variants(set_env) -> None:
    set_env(GEOSEO_PERPLEXITY_API_KEY="p-test")
    assert perplexity.build_payload("q", model="sonar-deep-research")[0]["effort"] == "high"
    payload, label = perplexity.build_payload("q", model="openai/gpt-5-mini", max_tokens=200)
    assert payload["model"] == "openai/gpt-5-mini" and label == "openai/gpt-5-mini"
    assert payload["tools"] == [{"type": "web_search"}]
    assert payload["max_output_tokens"] == 200
    set_env(GEOSEO_PERPLEXITY_EFFORT="medium")
    assert perplexity.build_payload("q")[0]["effort"] == "medium"


def test_perplexity_no_markers_falls_back_to_all_sources(set_env, mock_http) -> None:
    set_env(GEOSEO_PERPLEXITY_API_KEY="p-test")
    data = {
        "output": [
            PPLX_AGENT_RESPONSE["output"][0],
            {"type": "message", "content": [{"type": "output_text", "text": "Acme."}]},
        ]
    }
    mock_http(lambda req: httpx.Response(200, json=data))
    assert len(perplexity.query("q")["citations"]) == 3


def test_perplexity_legacy_shape_and_citation_check(set_env, mock_http) -> None:
    set_env(GEOSEO_PERPLEXITY_API_KEY="p-test")
    payload = {
        "choices": [{"message": {"content": "Use Acme."}}],
        "citations": ["https://docs.acme.com/start", "https://rival.io/"],
    }
    mock_http(lambda req: httpx.Response(200, json=payload))
    res = perplexity.query("q")
    assert res["cited_domains"] == ["docs.acme.com", "rival.io"]
    check = perplexity.citation_check(["q1", "q2"], "https://www.acme.com")
    assert check["target_domain"] == "acme.com"
    assert check["questions_with_target_cited"] == 2
    assert check["top_competing_domains"] == [{"domain": "rival.io", "citations": 2}]


def test_multi_llm_uses_configured_engines(set_env, mock_http) -> None:
    set_env(GEOSEO_OPENAI_API_KEY="sk", GEOSEO_PERPLEXITY_API_KEY="pk")

    def handler(req: httpx.Request) -> httpx.Response:
        if "openai" in req.url.host:
            return httpx.Response(200, json=OPENAI_RESPONSE)
        return httpx.Response(500, text="down")

    mock_http(handler)
    assert multi_llm.list_configured_engines() == ["openai", "perplexity"]
    res = multi_llm.multi_citation_check(["q"], "acme.com", samples=2)
    assert res["by_engine"]["openai"]["citation_rate"] == 1.0
    assert res["by_engine"]["perplexity"]["answers_errored"] == 2
