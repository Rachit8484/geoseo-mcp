"""Bing Webmaster Tools wrappers."""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from ..engines import bing
from ..engines.base import EngineError, EngineNotConfiguredError


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def bing_list_sites() -> dict[str, Any]:
        """List all Bing-verified sites for the API key owner."""
        try:
            return {"sites": bing.list_sites()}
        except (EngineNotConfiguredError, EngineError) as e:
            return {"error": str(e)}

    @mcp.tool()
    def bing_query_stats(site_url: str) -> dict[str, Any]:
        """Last-6-months query stats from Bing Webmaster (clicks, impressions, position).

        ``site_url`` must match what Bing has verified, e.g. ``https://example.com/``.
        """
        try:
            return bing.query_stats(site_url)
        except (EngineNotConfiguredError, EngineError) as e:
            return {"error": str(e)}

    @mcp.tool()
    def bing_page_stats(site_url: str) -> dict[str, Any]:
        """Per-page stats from Bing Webmaster."""
        try:
            return bing.page_stats(site_url)
        except (EngineNotConfiguredError, EngineError) as e:
            return {"error": str(e)}

    @mcp.tool()
    def bing_url_info(site_url: str, url: str) -> dict[str, Any]:
        """Index status + crawl info for a single URL on Bing."""
        try:
            return bing.url_info(site_url, url)
        except (EngineNotConfiguredError, EngineError) as e:
            return {"error": str(e)}

    @mcp.tool()
    def bing_submit_url(site_url: str, url: str) -> dict[str, Any]:
        """Submit a URL for fast crawling. Daily quota applies (default ~10/day)."""
        try:
            return bing.submit_url(site_url, url)
        except (EngineNotConfiguredError, EngineError) as e:
            return {"error": str(e)}

    @mcp.tool()
    def bing_crawl_issues(site_url: str) -> dict[str, Any]:
        """Crawl errors / blocked URLs / DNS issues reported by Bingbot."""
        try:
            return bing.crawl_issues(site_url)
        except (EngineNotConfiguredError, EngineError) as e:
            return {"error": str(e)}
