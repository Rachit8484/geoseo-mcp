"""SerpAPI engine — primary signal for Google AI Overviews (AIO).

SerpAPI scrapes Google's SERP and parses its features into JSON. When AIO
fires for a query, the response includes an ``ai_overview`` block with
``text_blocks`` (the answer body) and ``references`` (the cited URLs).

This is currently the most reliable open-API way to observe AIO content
without running headless Chrome yourself.

API docs: https://serpapi.com/google-ai-overviews
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import httpx

from ..config import get_config
from .base import EngineError, EngineNotConfiguredError

SERPAPI_ENDPOINT = "https://serpapi.com/search.json"


def _require_key() -> str:
    cfg = get_config()
    if not cfg.serpapi_api_key:
        raise EngineNotConfiguredError(
            "serpapi",
            "Set GEOSEO_SERPAPI_API_KEY (https://serpapi.com/manage-api-key). "
            "Free tier: 100 searches/month.",
        )
    return cfg.serpapi_api_key


def _domain(url: str) -> str:
    try:
        host = urlparse(url).netloc or url
    except Exception:
        return url
    host = host.lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def aio_check(
    query: str,
    location: str | None = None,
    hl: str = "en",
    gl: str = "us",
    google_domain: str = "google.com",
) -> dict[str, Any]:
    """Run a Google search via SerpAPI; report whether AIO fired and which URLs it cites.

    Returns a dict with:
        - ``query``, ``aio_present`` (bool)
        - ``aio_text`` (concatenated answer text, may be empty)
        - ``aio_references`` (list of {title, link, source})
        - ``cited_domains`` (deduped lowercased)
        - ``organic_top10`` (light list of {position, link, title, domain})
    """
    cfg = get_config()
    api_key = _require_key()
    params: dict[str, Any] = {
        "engine": "google",
        "q": query,
        "api_key": api_key,
        "hl": hl,
        "gl": gl,
        "google_domain": google_domain,
    }
    if location:
        params["location"] = location

    with httpx.Client(timeout=cfg.request_timeout_s) as c:
        r = c.get(SERPAPI_ENDPOINT, params=params, headers={"User-Agent": cfg.user_agent})
    if r.status_code >= 400:
        raise EngineError(f"SerpAPI {r.status_code}: {r.text[:300]}")
    data = r.json()

    aio = data.get("ai_overview") or {}
    text_blocks = aio.get("text_blocks") or []
    aio_text = "\n".join(b.get("snippet", "") for b in text_blocks if b.get("snippet"))
    refs = aio.get("references") or []
    aio_refs = [
        {
            "title": ref.get("title"),
            "link": ref.get("link"),
            "source": ref.get("source"),
            "domain": _domain(ref.get("link") or ""),
        }
        for ref in refs
        if ref.get("link")
    ]
    cited_domains = sorted({r["domain"] for r in aio_refs if r["domain"]})

    organic = data.get("organic_results") or []
    organic_top10 = [
        {
            "position": o.get("position"),
            "title": o.get("title"),
            "link": o.get("link"),
            "domain": _domain(o.get("link") or ""),
        }
        for o in organic[:10]
    ]

    return {
        "query": query,
        "aio_present": bool(aio),
        "aio_text": aio_text,
        "aio_references": aio_refs,
        "cited_domains": cited_domains,
        "organic_top10": organic_top10,
    }


def aio_citation_check(queries: list[str], target_domain: str) -> dict[str, Any]:
    """For each query, run AIO check and report whether ``target_domain`` is cited.

    Returns:
        - ``aio_fire_rate``: fraction of queries that triggered AIO
        - ``citation_share``: fraction of AIO-firing queries that cite the target
        - ``top_competing_domains``
        - ``per_query`` results
    """
    target = _domain(target_domain)
    fired = 0
    cited = 0
    competitors: dict[str, int] = {}
    per_query: list[dict[str, Any]] = []

    for q in queries:
        try:
            res = aio_check(q)
        except EngineError as e:
            per_query.append({"query": q, "error": str(e)})
            continue
        is_cited = target in res["cited_domains"]
        if res["aio_present"]:
            fired += 1
            if is_cited:
                cited += 1
            for d in res["cited_domains"]:
                if d != target:
                    competitors[d] = competitors.get(d, 0) + 1
        per_query.append({
            "query": q,
            "aio_present": res["aio_present"],
            "cited": is_cited,
            "cited_domains": res["cited_domains"],
        })

    top = sorted(competitors.items(), key=lambda kv: kv[1], reverse=True)[:10]
    return {
        "target_domain": target,
        "queries": len(queries),
        "aio_fire_rate": fired / len(queries) if queries else 0.0,
        "citation_share": (cited / fired) if fired else 0.0,
        "top_competing_domains": [{"domain": d, "appearances": n} for d, n in top],
        "per_query": per_query,
    }
