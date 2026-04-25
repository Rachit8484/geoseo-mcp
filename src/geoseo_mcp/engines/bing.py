"""Bing Webmaster Tools engine.

Auth: a single API key (no OAuth). Get one at
https://www.bing.com/webmasters → Settings → API access.

API: https://learn.microsoft.com/en-us/bingwebmaster/getting-access
"""

from __future__ import annotations

from typing import Any

import httpx

from ..config import get_config
from .base import EngineError, EngineNotConfiguredError

BING_BASE = "https://ssl.bing.com/webmaster/api.svc/json"


def _require_key() -> str:
    cfg = get_config()
    if not cfg.bing_webmaster_api_key:
        raise EngineNotConfiguredError(
            "bing_webmaster",
            "Set GEOSEO_BING_WEBMASTER_API_KEY. Get one at "
            "https://www.bing.com/webmasters/ → Settings → API access.",
        )
    return cfg.bing_webmaster_api_key


def _call(method: str, params: dict[str, Any] | None = None, body: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = get_config()
    api_key = _require_key()
    url = f"{BING_BASE}/{method}"
    qparams = {"apikey": api_key}
    if params:
        qparams.update(params)
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "User-Agent": cfg.user_agent,
    }
    with httpx.Client(timeout=cfg.request_timeout_s) as c:
        if body is not None:
            r = c.post(url, params=qparams, json=body, headers=headers)
        else:
            r = c.get(url, params=qparams, headers=headers)
    if r.status_code >= 400:
        raise EngineError(f"Bing Webmaster {method} {r.status_code}: {r.text[:300]}")
    try:
        return r.json()
    except ValueError as e:
        raise EngineError(f"Bing Webmaster {method}: invalid JSON ({r.text[:200]})") from e


def list_sites() -> list[dict[str, Any]]:
    data = _call("GetUserSites")
    return data.get("d", []) or []


def query_stats(site_url: str) -> dict[str, Any]:
    """6-month query-level rank/impressions/clicks for a Bing-verified site."""
    data = _call("GetQueryStats", params={"siteUrl": site_url})
    rows = data.get("d", []) or []
    return {"site_url": site_url, "rows": rows}


def page_stats(site_url: str) -> dict[str, Any]:
    """Per-page rank/impressions/clicks."""
    data = _call("GetPageStats", params={"siteUrl": site_url})
    rows = data.get("d", []) or []
    return {"site_url": site_url, "rows": rows}


def url_info(site_url: str, url: str) -> dict[str, Any]:
    """Index status + crawl info for a specific URL."""
    data = _call("GetUrlInfo", params={"siteUrl": site_url, "url": url})
    return data.get("d") or {}


def submit_url(site_url: str, url: str) -> dict[str, Any]:
    """Submit a URL for fast crawling. Daily quota applies (default 10/day)."""
    body = {"siteUrl": site_url, "url": url}
    _call("SubmitUrl", body=body)
    return {"site_url": site_url, "url": url, "submitted": True}


def crawl_issues(site_url: str) -> dict[str, Any]:
    """Crawl errors / blocked URLs / DNS issues reported by Bingbot."""
    data = _call("GetCrawlIssues", params={"siteUrl": site_url})
    rows = data.get("d", []) or []
    return {"site_url": site_url, "rows": rows}
