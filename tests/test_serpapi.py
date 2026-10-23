"""SerpAPI AI Overviews wrapper with mocked responses."""

from __future__ import annotations

import httpx
import pytest

from geoseo_mcp.engines import serpapi
from geoseo_mcp.engines.base import EngineError, EngineNotConfiguredError

WITH_AIO = {
    "ai_overview": {
        "text_blocks": [{"snippet": "Acme is a CRM."}, {"snippet": "It has a free tier."}],
        "references": [
            {"title": "Acme", "link": "https://help.acme.com/a", "source": "Acme"},
            {"title": "Rival", "link": "https://www.rival.io/b", "source": "Rival"},
        ],
    },
    "organic_results": [
        {"position": 1, "title": "Acme", "link": "https://acme.com/"},
        {"position": 2, "title": "Rival", "link": "https://rival.io/"},
    ],
}
WITHOUT_AIO = {"organic_results": [{"position": 1, "title": "x", "link": "https://x.com"}]}


def test_requires_key() -> None:
    with pytest.raises(EngineNotConfiguredError):
        serpapi.aio_check("q")


def test_aio_check_parses_overview(set_env, mock_http) -> None:
    set_env(GEOSEO_SERPAPI_API_KEY="s-test")
    seen = mock_http(lambda req: httpx.Response(200, json=WITH_AIO))
    res = serpapi.aio_check("best crm", location="Austin, Texas")
    params = seen[0].url.params
    assert params["engine"] == "google" and params["q"] == "best crm"
    assert params["api_key"] == "s-test" and params["location"] == "Austin, Texas"
    assert res["aio_present"] is True
    assert res["aio_text"] == "Acme is a CRM.\nIt has a free tier."
    assert res["cited_domains"] == ["help.acme.com", "rival.io"]
    assert res["organic_top10"][0]["domain"] == "acme.com"


def test_aio_citation_check_counts_subdomains(set_env, mock_http) -> None:
    set_env(GEOSEO_SERPAPI_API_KEY="s-test")
    mock_http(
        lambda req: httpx.Response(
            200, json=WITH_AIO if req.url.params["q"] != "no aio" else WITHOUT_AIO
        )
    )
    res = serpapi.aio_citation_check(["best crm", "crm pricing", "no aio"], "acme.com")
    assert res["aio_fire_rate"] == pytest.approx(2 / 3)
    assert res["citation_share"] == 1.0
    assert res["top_competing_domains"] == [{"domain": "rival.io", "appearances": 2}]
    assert [q["cited"] for q in res["per_query"]] == [True, True, False]


def test_aio_http_error(set_env, mock_http) -> None:
    set_env(GEOSEO_SERPAPI_API_KEY="s-test")
    mock_http(lambda req: httpx.Response(401, text="bad key"))
    with pytest.raises(EngineError, match="401"):
        serpapi.aio_check("q")
