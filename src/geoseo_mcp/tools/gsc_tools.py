"""Google Search Console tools."""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from ..engines import gsc
from ..engines.base import EngineError, EngineNotConfiguredError


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def gsc_list_sites() -> dict[str, Any]:
        """List all Search Console properties the authenticated user can access.

        Returns a list of site entries with ``siteUrl`` and ``permissionLevel``.
        Use ``siteUrl`` from this list as input to other ``gsc_*`` tools.
        """
        try:
            return {"sites": gsc.list_sites()}
        except (EngineNotConfiguredError, EngineError) as e:
            return {"error": str(e)}

    @mcp.tool()
    def gsc_performance(
        site_url: str,
        start_date: str | None = None,
        end_date: str | None = None,
        dimensions: list[str] | None = None,
        row_limit: int = 1000,
        search_type: str = "web",
        country: str | None = None,
        device: str | None = None,
    ) -> dict[str, Any]:
        """Query GSC search analytics.

        Args:
            site_url: The property as it appears in GSC (e.g. ``sc-domain:example.com``
                or ``https://example.com/``).
            start_date: ISO date (YYYY-MM-DD). Defaults to 28 days ago.
            end_date: ISO date. Defaults to 2 days ago (GSC has ~2-day latency).
            dimensions: One or more of ``query``, ``page``, ``country``, ``device``,
                ``date``, ``searchAppearance``. Defaults to ``["query"]``.
            row_limit: Max rows (capped at 25,000).
            search_type: ``web``, ``image``, ``video``, ``news``, or ``discover``.
            country: ISO 3166-1 alpha-3 country filter (e.g. ``usa``).
            device: ``desktop``, ``mobile``, or ``tablet``.
        """
        try:
            return gsc.query_performance(
                site_url=site_url, start_date=start_date, end_date=end_date,
                dimensions=dimensions, row_limit=row_limit, search_type=search_type,
                country=country, device=device,
            )
        except (EngineNotConfiguredError, EngineError) as e:
            return {"error": str(e)}

    @mcp.tool()
    def gsc_inspect_url(site_url: str, url: str, language_code: str = "en-US") -> dict[str, Any]:
        """Get index status for a specific URL via the URL Inspection API.

        Returns coverage state, last crawl time, mobile usability, indexed verdict,
        and indexing rich-result data. Slow (~1s/call); rate-limited by Google.
        """
        try:
            return gsc.inspect_url(site_url=site_url, url=url, language_code=language_code)
        except (EngineNotConfiguredError, EngineError) as e:
            return {"error": str(e)}

    @mcp.tool()
    def gsc_submit_sitemap(site_url: str, feedpath: str) -> dict[str, Any]:
        """Submit (or resubmit) a sitemap URL to GSC.

        ``feedpath`` is the absolute URL of the sitemap, e.g.
        ``https://example.com/sitemap.xml``.
        """
        try:
            return gsc.submit_sitemap(site_url=site_url, feedpath=feedpath)
        except (EngineNotConfiguredError, EngineError) as e:
            return {"error": str(e)}
