"""Yandex Webmaster engine (API v4).

Auth: an OAuth token sent as ``Authorization: OAuth <token>`` (not Bearer,
whatever the token response says). Register an app at
https://oauth.yandex.com/client/new with both ``webmaster:hostinfo`` and
``webmaster:verify``; hostinfo alone only lists sites, every report needs
verify. For personal use the ``response_type=token`` flow is enough.

Every resource is scoped by ``user_id`` (from ``GET /v4/user``) and a host id
like ``https:example.com:443``. You can pass a normal site URL; we match it
against the account's hosts (including www/http variants) and follow the main
mirror Yandex reports.

Docs: https://yandex.com/dev/webmaster/doc/en/
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote, urlparse

import httpx

from ..config import get_config
from .base import EngineError, EngineNotConfiguredError

YANDEX_BASE = "https://api.webmaster.yandex.net/v4"
QUERY_INDICATORS = ("TOTAL_SHOWS", "TOTAL_CLICKS", "AVG_SHOW_POSITION", "AVG_CLICK_POSITION")
_user_ids: dict[str, int] = {}


def _require_token() -> str:
    cfg = get_config()
    if not cfg.yandex_oauth_token:
        raise EngineNotConfiguredError(
            "yandex_webmaster",
            "Set GEOSEO_YANDEX_OAUTH_TOKEN to an OAuth token with Webmaster access "
            "(https://yandex.com/dev/webmaster/doc/en/tasks/how-to-get-oauth).",
        )
    return cfg.yandex_oauth_token


def _call(
    method: str,
    path: str,
    params: list[tuple[str, Any]] | dict[str, Any] | None = None,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = get_config()
    token = _require_token()
    headers = {
        "Authorization": f"OAuth {token}",
        "Accept": "application/json",
        "User-Agent": cfg.user_agent,
    }
    with httpx.Client(timeout=cfg.request_timeout_s) as c:
        r = c.request(method, f"{YANDEX_BASE}{path}", params=params, json=body, headers=headers)
    if r.status_code >= 400:
        try:
            err = r.json()
            detail = f"{err.get('error_code')}: {err.get('error_message')}"
        except ValueError:
            detail = r.text[:300]
        raise EngineError(f"Yandex Webmaster {r.status_code} {detail}")
    if not r.content:
        return {}
    try:
        return r.json()
    except ValueError as e:
        raise EngineError(f"Yandex Webmaster: invalid JSON ({r.text[:200]})") from e


def user_id() -> int:
    token = _require_token()
    if token not in _user_ids:
        _user_ids[token] = int(_call("GET", "/user")["user_id"])
    return _user_ids[token]


def host_id(site: str) -> str:
    """``https://example.com/`` -> ``https:example.com:443``. Host ids pass through."""
    site = site.strip()
    if "://" not in site:
        parts = site.split(":")
        if len(parts) == 3 and parts[0] in ("http", "https") and parts[2].isdigit():
            return site
        site = "https://" + site
    p = urlparse(site)
    scheme = (p.scheme or "https").lower()
    host = (p.hostname or "").encode("idna").decode("ascii")
    port = p.port or (443 if scheme == "https" else 80)
    return f"{scheme}:{host}:{port}"


def resolve_host(site: str) -> str:
    """Map a URL/host id to the host id Yandex actually has for this account."""
    want = host_id(site)
    try:
        hosts = list_sites()
    except EngineError:
        return want
    by_id = {h.get("host_id"): h for h in hosts if h.get("host_id")}

    def canonical(hid: str) -> str:
        mirror = (by_id[hid].get("main_mirror") or {}).get("host_id")
        return mirror if mirror in by_id else hid

    if want in by_id:
        return canonical(want)
    _, host, _ = want.split(":")
    bare = host.removeprefix("www.")
    for hid in by_id:
        if hid.split(":")[1].removeprefix("www.") == bare:
            return canonical(hid)
    return want


def _host_path(hid: str) -> str:
    return f"/user/{user_id()}/hosts/{quote(hid, safe='')}"


def list_sites() -> list[dict[str, Any]]:
    return _call("GET", f"/user/{user_id()}/hosts").get("hosts", []) or []


def site_summary(site: str) -> dict[str, Any]:
    """SQI, pages in search, excluded pages and problem counts by severity."""
    hid = resolve_host(site)
    data = _call("GET", f"{_host_path(hid)}/summary")
    return {"host_id": hid, **data}


def query_stats(
    site: str,
    order_by: str = "TOTAL_SHOWS",
    device: str = "ALL",
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 500,
) -> dict[str, Any]:
    """Popular search queries (shows, clicks, avg positions). Defaults to last week.

    Yandex serves 500 rows per call out of a pool of up to 3,000; ``limit`` up
    to 3000 pages through it.
    """
    hid = resolve_host(site)
    limit = max(1, min(limit, 3000))
    base: list[tuple[str, Any]] = [("order_by", order_by), ("device_type_indicator", device)]
    base += [("query_indicator", q) for q in QUERY_INDICATORS]
    if date_from:
        base.append(("date_from", date_from))
    if date_to:
        base.append(("date_to", date_to))
    rows: list[dict[str, Any]] = []
    data: dict[str, Any] = {}
    while len(rows) < limit:
        page_size = min(500, limit - len(rows))
        params = base + [("offset", len(rows)), ("limit", page_size)]
        try:
            data = _call("GET", f"{_host_path(hid)}/search-queries/popular", params=params)
        except EngineError:
            if not rows:
                raise
            break
        page = data.get("queries", []) or []
        rows += [
            {"query": q.get("query_text"), "query_id": q.get("query_id"), **(q.get("indicators") or {})}
            for q in page
        ]
        if len(page) < page_size or (data.get("count") or 0) <= len(rows):
            break
    total = data.get("count")
    return {
        "host_id": hid,
        "date_from": data.get("date_from"),
        "date_to": data.get("date_to"),
        "total_queries": total,
        "truncated": bool(total and total > len(rows)),
        "order_by": order_by,
        "notes": [
            "Yandex only reports its top queries (max 3,000) for the period; totals are floors.",
            "Rows are selected by order_by; re-sorting by another metric may miss queries.",
            "Use the date range echoed back; Yandex finalises days a few days late.",
        ],
        "rows": rows,
    }


def url_info(site: str, url: str) -> dict[str, Any]:
    """Indexing + search status for a URL tracked under "Monitoring important pages".

    Yandex has no arbitrary-URL inspection endpoint; status is only exposed for
    pages you've added to important-page monitoring in the Webmaster UI.
    """
    hid = resolve_host(site)
    data = _call("GET", f"{_host_path(hid)}/important-urls")
    urls = data.get("urls", []) or []
    want = url.rstrip("/")
    for u in urls:
        if (u.get("url") or "").rstrip("/") == want:
            return {"host_id": hid, "found": True, **u}
    return {
        "host_id": hid,
        "url": url,
        "found": False,
        "message": (
            "URL isn't in 'Monitoring important pages'. Add it in Yandex Webmaster "
            "(Indexing → Monitoring important pages) to get its status via the API."
        ),
        "monitored_urls": [u.get("url") for u in urls][:50],
    }


def submit_url(site: str, url: str) -> dict[str, Any]:
    """Queue a URL for recrawl. Daily quota applies (see ``quota_remainder``)."""
    hid = resolve_host(site)
    data = _call("POST", f"{_host_path(hid)}/recrawl/queue", body={"url": url})
    return {"host_id": hid, "url": url, "submitted": True, **data}


def recrawl_quota(site: str) -> dict[str, Any]:
    hid = resolve_host(site)
    data = _call("GET", f"{_host_path(hid)}/recrawl/quota")
    return {"host_id": hid, **data}


def crawl_issues(site: str, broken_links_limit: int = 100) -> dict[str, Any]:
    """Active site diagnostics plus sample broken internal links."""
    hid = resolve_host(site)
    hp = _host_path(hid)
    diag = _call("GET", f"{hp}/diagnostics").get("problems", {}) or {}
    problems = [
        {"problem": name, **info}
        for name, info in diag.items()
        if (info or {}).get("state") == "PRESENT"
    ]
    order = {"FATAL": 0, "CRITICAL": 1, "POSSIBLE_PROBLEM": 2, "RECOMMENDATION": 3}
    problems.sort(key=lambda p: order.get(p.get("severity", ""), 9))
    links = _call(
        "GET",
        f"{hp}/links/internal/broken/samples",
        params={"limit": max(1, min(broken_links_limit, 100)), "offset": 0},
    )
    return {
        "host_id": hid,
        "problems": problems,
        "broken_internal_links_count": links.get("count", 0),
        "broken_internal_links": links.get("links", []) or [],
    }
