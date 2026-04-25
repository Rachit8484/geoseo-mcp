"""SerpAPI / Google AI Overviews tools."""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from ..engines import serpapi
from ..engines.base import EngineError, EngineNotConfiguredError


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def aio_check(
        query: str,
        location: str | None = None,
        hl: str = "en",
        gl: str = "us",
        google_domain: str = "google.com",
    ) -> dict[str, Any]:
        """Run a Google search via SerpAPI and parse the AI Overview block.

        Returns ``aio_present``, the AIO answer text, the URLs/domains AIO
        cites, and the top-10 organic results for context. Use this to
        track which pages Google's generative answers actually source.
        """
        try:
            return serpapi.aio_check(
                query=query, location=location, hl=hl, gl=gl, google_domain=google_domain,
            )
        except (EngineNotConfiguredError, EngineError) as e:
            return {"error": str(e)}

    @mcp.tool()
    def aio_citation_check(queries: list[str], target_domain: str) -> dict[str, Any]:
        """For a batch of queries, report AIO fire-rate and citation share for ``target_domain``.

        This is the GEO companion to ``multi_llm_citation_check`` — same
        idea, but specifically for Google's on-SERP AI Overviews. Run
        weekly and snapshot to ``snapshot_serp_aio`` to track AIO
        visibility over time.
        """
        try:
            return serpapi.aio_citation_check(queries=queries, target_domain=target_domain)
        except (EngineNotConfiguredError, EngineError) as e:
            return {"error": str(e)}
