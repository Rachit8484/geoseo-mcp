"""Yandex Webmaster engine tests (mocked HTTP)."""

from __future__ import annotations

import json

import httpx
import pytest

from geoseo_mcp import config
from geoseo_mcp.engines import yandex
from geoseo_mcp.engines.base import EngineError, EngineNotConfiguredError

HOSTS = {
    "hosts": [
        {"host_id": "https:example.com:443", "ascii_host_url": "https://example.com/",
         "verified": True},
        {"host_id": "https:www.example.com:443", "ascii_host_url": "https://www.example.com/",
         "verified": True, "main_mirror": {"host_id": "https:example.com:443"}},
    ]
}


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("GEOSEO_YANDEX_OAUTH_TOKEN", "y0_test")
    monkeypatch.setattr(config, "_cached", None)
    monkeypatch.setattr(yandex, "_user_ids", {})
    yield monkeypatch
    config._cached = None


def _mock(monkeypatch, routes, seen):
    real = httpx.Client

    def handler(request):
        seen.append(request)
        path = request.url.path.removeprefix("/v4")
        if path == "/user":
            return httpx.Response(200, json={"user_id": 42})
        if path == "/user/42/hosts":
            return httpx.Response(200, json=HOSTS)
        for suffix, resp in routes.items():
            if path.endswith(suffix):
                return resp(request) if callable(resp) else resp
        return httpx.Response(404, json={"error_code": "NOT_FOUND", "error_message": path})

    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real(*args, **kwargs)

    monkeypatch.setattr(yandex.httpx, "Client", factory)


def test_not_configured(monkeypatch):
    monkeypatch.delenv("GEOSEO_YANDEX_OAUTH_TOKEN", raising=False)
    monkeypatch.setattr(config, "_cached", None)
    with pytest.raises(EngineNotConfiguredError):
        yandex.list_sites()
    config._cached = None


def test_host_id_and_mirror_resolution(env):
    assert yandex.host_id("https://Example.com/blog") == "https:example.com:443"
    assert yandex.host_id("http://example.com:8080") == "http:example.com:8080"
    assert yandex.host_id("example.com") == "https:example.com:443"
    assert yandex.host_id("https:example.com:443") == "https:example.com:443"
    seen: list[httpx.Request] = []
    summary = {"sqi": 30, "searchable_pages_count": 12, "site_problems": {"FATAL": 0}}
    _mock(env, {"/summary": httpx.Response(200, json=summary)}, seen)
    out = yandex.site_summary("https://www.example.com/")
    assert out["host_id"] == "https:example.com:443"
    assert out["sqi"] == 30
    assert seen[-1].headers["authorization"] == "OAuth y0_test"
    assert seen[-1].url.raw_path == b"/v4/user/42/hosts/https%3Aexample.com%3A443/summary"


def test_query_stats_pages_and_flattens(env):
    seen: list[httpx.Request] = []

    def popular(request):
        offset = int(request.url.params["offset"])
        n = 500 if offset == 0 else 100
        queries = [
            {"query_id": f"q{offset + i}", "query_text": f"query {offset + i}",
             "indicators": {"TOTAL_SHOWS": 1000 - i, "TOTAL_CLICKS": 5}}
            for i in range(n)
        ]
        return httpx.Response(200, json={"queries": queries, "count": 600,
                                         "date_from": "2026-10-10", "date_to": "2026-10-16"})

    _mock(env, {"/search-queries/popular": popular}, seen)
    out = yandex.query_stats("example.com", limit=3000)
    calls = [r for r in seen if r.url.path.endswith("/popular")]
    assert len(calls) == 2
    assert calls[0].url.params.get_list("query_indicator") == list(yandex.QUERY_INDICATORS)
    assert calls[0].url.params["order_by"] == "TOTAL_SHOWS"
    assert len(out["rows"]) == 600 and out["truncated"] is False
    assert out["rows"][0] == {"query": "query 0", "query_id": "q0",
                              "TOTAL_SHOWS": 1000, "TOTAL_CLICKS": 5}
    assert out["date_to"] == "2026-10-16"


def test_submit_crawl_issues_and_errors(env):
    seen: list[httpx.Request] = []
    routes = {
        "/recrawl/queue": lambda r: (
            httpx.Response(409, json={"error_code": "URL_ALREADY_ADDED",
                                      "error_message": "already queued"})
            if json.loads(r.content)["url"].endswith("/dup")
            else httpx.Response(202, json={"task_id": "t1", "quota_remainder": 19})
        ),
        "/diagnostics": httpx.Response(200, json={"problems": {
            "NO_SITEMAPS": {"severity": "CRITICAL", "state": "PRESENT"},
            "DNS_ERROR": {"severity": "FATAL", "state": "PRESENT"},
            "SLOW_PAGES": {"severity": "POSSIBLE_PROBLEM", "state": "ABSENT"},
        }}),
        "/links/internal/broken/samples": httpx.Response(200, json={
            "count": 1, "links": [{"source_url": "https://example.com/a",
                                   "destination_url": "https://example.com/gone"}]}),
        "/important-urls": httpx.Response(200, json={"urls": [
            {"url": "https://example.com/a", "indexing_status": {"http_code": 200}}]}),
    }
    _mock(env, routes, seen)
    ok = yandex.submit_url("https://example.com/", "https://example.com/new")
    assert ok["submitted"] and ok["quota_remainder"] == 19
    with pytest.raises(EngineError, match="409 URL_ALREADY_ADDED"):
        yandex.submit_url("https://example.com/", "https://example.com/dup")
    issues = yandex.crawl_issues("example.com")
    assert [p["problem"] for p in issues["problems"]] == ["DNS_ERROR", "NO_SITEMAPS"]
    assert issues["broken_internal_links_count"] == 1
    assert yandex.url_info("example.com", "https://example.com/a/")["found"] is True
    missing = yandex.url_info("example.com", "https://example.com/zzz")
    assert missing["found"] is False and missing["monitored_urls"] == ["https://example.com/a"]
