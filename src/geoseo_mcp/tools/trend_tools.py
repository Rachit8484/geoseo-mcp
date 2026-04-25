"""Trend / snapshot tools backed by local SQLite.

Idea: every "snapshot" is an immutable row dump tagged with ``captured_at``.
Comparing snapshots over time gives you trends — clicks/impressions/position
deltas for GSC, citation-share deltas for LLMs and AIO. No external service,
your data stays on your machine.
"""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from ..engines import gsc, multi_llm, serpapi
from ..engines.base import EngineError, EngineNotConfiguredError
from ..storage import sqlite as store


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def trend_init() -> dict[str, Any]:
        """Create the local SQLite snapshot DB if it doesn't exist; return its path."""
        return store.init()

    @mcp.tool()
    def trend_stats() -> dict[str, Any]:
        """Inventory of what's stored: row counts, sites/domains, oldest/newest snapshots."""
        return store.stats()

    @mcp.tool()
    def snapshot_gsc(
        site_url: str,
        start_date: str | None = None,
        end_date: str | None = None,
        dimensions: list[str] | None = None,
        row_limit: int = 1000,
        search_type: str = "web",
    ) -> dict[str, Any]:
        """Run a GSC performance query and persist the rows as a snapshot.

        Run this on a schedule (cron, n8n, ``launchd`` — anything that can
        invoke an MCP tool) to build a local time-series of search
        performance. Default dimensions: ``["query"]``.
        """
        try:
            res = gsc.query_performance(
                site_url=site_url, start_date=start_date, end_date=end_date,
                dimensions=dimensions, row_limit=row_limit, search_type=search_type,
            )
        except (EngineNotConfiguredError, EngineError) as e:
            return {"error": str(e)}
        info = store.insert_gsc_rows(
            site_url=site_url,
            dimensions=res["request"]["dimensions"],
            rows=res["rows"],
        )
        info["request"] = res["request"]
        return info

    @mcp.tool()
    def snapshot_llm_citations(
        questions: list[str],
        target_domain: str,
        engines: list[str] | None = None,
    ) -> dict[str, Any]:
        """Run multi-LLM citation check and persist the per-question results.

        Builds the dataset behind ``trend_llm_citations``. ``engines``
        defaults to every configured LLM (see ``geoseo_status``).
        """
        try:
            res = multi_llm.multi_citation_check(
                questions=questions, target_domain=target_domain, engines=engines,
            )
        except (EngineNotConfiguredError, EngineError) as e:
            return {"error": str(e)}

        flat: list[dict[str, Any]] = []
        for engine_name, eng in (res.get("by_engine") or {}).items():
            for r in eng.get("results", []):
                if "error" in r:
                    continue
                flat.append({
                    "engine": engine_name,
                    "question": r.get("question", ""),
                    "cited": bool(r.get("cited")),
                    "cited_domains": r.get("cited_domains") or [],
                    "answer_excerpt": r.get("answer_excerpt", ""),
                })
        info = store.insert_citation_rows(target_domain=target_domain, rows=flat)
        info["summary"] = {
            "engines": list((res.get("by_engine") or {}).keys()),
            "questions": res.get("questions_asked"),
            "overall_citation_share": res.get("overall_citation_share"),
        }
        return info

    @mcp.tool()
    def snapshot_serp_aio(
        queries: list[str], target_domain: str,
    ) -> dict[str, Any]:
        """Run AIO citation check via SerpAPI and persist as ``serpapi_aio`` engine rows."""
        try:
            res = serpapi.aio_citation_check(queries=queries, target_domain=target_domain)
        except (EngineNotConfiguredError, EngineError) as e:
            return {"error": str(e)}
        flat = [
            {
                "engine": "serpapi_aio",
                "question": pq["query"],
                "cited": bool(pq.get("cited")),
                "cited_domains": pq.get("cited_domains") or [],
                "answer_excerpt": "",
            }
            for pq in res.get("per_query", [])
            if "error" not in pq and pq.get("aio_present")
        ]
        info = store.insert_citation_rows(target_domain=target_domain, rows=flat)
        info["summary"] = {
            "queries": len(queries),
            "aio_fire_rate": res.get("aio_fire_rate"),
            "citation_share": res.get("citation_share"),
        }
        return info

    @mcp.tool()
    def trend_gsc(
        site_url: str,
        query: str | None = None,
        page: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Time-series of clicks/impressions/position from stored GSC snapshots.

        Aggregates by ``captured_at``. Filter by ``query`` and/or ``page``
        to drill in. Returns up to ``limit`` most recent snapshots in
        chronological order.
        """
        return store.gsc_trend(site_url=site_url, query=query, page=page, limit=limit)

    @mcp.tool()
    def trend_llm_citations(
        target_domain: str, engine: str | None = None, limit: int = 50,
    ) -> dict[str, Any]:
        """Per-snapshot citation share for ``target_domain`` over time.

        ``engine`` filters to one of ``perplexity|openai|anthropic|gemini|serpapi_aio``.
        Returns rows of ``{captured_at, engine, questions, cited, citation_share}``.
        """
        return store.citation_trend(target_domain=target_domain, engine=engine, limit=limit)
