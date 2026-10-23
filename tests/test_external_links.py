"""Broken-link prospector tests (mocked HTTP, no network)."""

from __future__ import annotations

import httpx
import pytest

from geoseo_mcp.audit import external_links as el


@pytest.fixture
def site(tmp_path, monkeypatch):
    monkeypatch.setenv("GEOSEO_DB", str(tmp_path / "geoseo.sqlite"))
    content = tmp_path / "content"
    content.mkdir()
    (content / "a.html").write_text(
        """<html><body>
        <a href="https://ok.example/page">ok</a>
        <a href="https://gone.example/old#section">404</a>
        <a href="http://moved.example/">moved</a>
        <a href="//slow.example/x">slow</a>
        <a href="https://nohead.example/">no head</a>
        <a href="https://mysite.com/internal">own site</a>
        <a href="/relative">relative</a>
        <a href="#top">anchor</a>
        <a href="mailto:a@b.c">mail</a>
        <a href="tel:123">tel</a>
        <a href="javascript:void(0)">js</a>
        </body></html>"""
    )
    (content / "b.html").write_text(
        '<a href="https://gone.example/old">again</a><a href="https://nxdomain.example/">dns</a>'
    )
    return content


def _transport(calls):
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, str(request.url)))
        host = request.url.host
        if host == "ok.example":
            return httpx.Response(200)
        if host == "gone.example":
            return httpx.Response(404)
        if host == "moved.example":
            if request.url.scheme == "http":
                return httpx.Response(301, headers={"Location": "https://moved.example/new"})
            return httpx.Response(200)
        if host == "slow.example":
            raise httpx.ReadTimeout("timed out", request=request)
        if host == "nohead.example":
            return httpx.Response(405 if request.method == "HEAD" else 200)
        if host == "nxdomain.example":
            raise httpx.ConnectError("[Errno -2] Name or service not known", request=request)
        return httpx.Response(500)

    return httpx.MockTransport(handler)


def test_collect_links_skips_non_http_and_own_host(site):
    sources, n = el.collect_links(site, site_host="www.mysite.com")
    assert n == 2
    assert sorted(sources) == [
        "http://moved.example/",
        "https://gone.example/old",
        "https://nohead.example/",
        "https://nxdomain.example/",
        "https://ok.example/page",
        "https://slow.example/x",
    ]
    assert sources["https://gone.example/old"] == ["a.html", "b.html"]


def test_find_broken_groups_and_suggestions(site):
    calls: list = []
    out = el.find_broken(str(site), site_host="mysite.com", transport=_transport(calls))
    assert out["counts"] == {
        "ok": 2, "redirect": 1, "client_error": 1, "server_error": 0,
        "timeout": 1, "dns_fail": 1, "error": 0,
    }
    by_url = {r["url"]: r for r in out["links"]}
    assert "https://ok.example/page" not in by_url  # ok hidden by default
    assert "https://nohead.example/" not in by_url  # GET fallback succeeded
    gone = by_url["https://gone.example/old"]
    assert gone["status"] == 404 and gone["source_pages"] == ["a.html", "b.html"]
    assert "replace" in gone["suggested_action"]
    moved = by_url["http://moved.example/"]
    assert moved["group"] == "redirect" and moved["final_url"] == "https://moved.example/new"
    assert by_url["https://nxdomain.example/"]["group"] == "dns_fail"
    assert by_url["https://slow.example/x"]["group"] == "timeout"
    # broken links come first
    assert out["links"][0]["group"] == "client_error"
    assert ("GET", "https://nohead.example/") in calls


def test_cache_skips_rechecks_except_transient(site):
    calls: list = []
    el.find_broken(str(site), transport=_transport(calls))
    calls.clear()
    out = el.find_broken(str(site), include_ok=True, transport=_transport(calls))
    rechecked = {u for _, u in calls}
    # only the timeout is re-checked; everything else comes from the cache
    assert rechecked == {"https://slow.example/x"}
    assert out["checked_now"] == 1
    assert len(out["links"]) == out["external_urls"]

    fresh = el.find_broken(str(site), cache_ttl_s=0, transport=_transport(calls))
    assert fresh["checked_now"] == 7 and fresh["from_cache"] == 0  # mysite.com included


def test_missing_folder(tmp_path):
    with pytest.raises(FileNotFoundError):
        el.collect_links(tmp_path / "nope")
