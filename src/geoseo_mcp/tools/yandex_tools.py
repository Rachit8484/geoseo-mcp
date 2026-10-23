"""Yandex Webmaster wrappers."""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from ..engines import yandex
from ..engines.base import EngineError, EngineNotConfiguredError


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def yandex_list_sites() -> dict[str, Any]:
        """List sites in the token owner's Yandex Webmaster account."""
        try:
            return {"sites": yandex.list_sites()}
        except (EngineNotConfiguredError, EngineError) as e:
            return {"error": str(e)}

    @mcp.tool()
    def yandex_site_summary(site: str) -> dict[str, Any]:
        """Site quality index (SQI), pages in search, excluded pages, problem counts.

        ``site`` can be a URL (``https://example.com/``) or a Yandex host id
        (``https:example.com:443``).
        """
        try:
            return yandex.site_summary(site)
        except (EngineNotConfiguredError, EngineError) as e:
            return {"error": str(e)}

    @mcp.tool()
    def yandex_query_stats(
        site: str,
        order_by: str = "TOTAL_SHOWS",
        device: str = "ALL",
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int = 500,
    ) -> dict[str, Any]:
        """Top Yandex search queries: shows, clicks, average show/click position.

        ``order_by``: ``TOTAL_SHOWS`` or ``TOTAL_CLICKS``. ``device``: ``ALL``,
        ``DESKTOP``, ``MOBILE_AND_TABLET``, ``MOBILE``, ``TABLET``. Dates are
        ``YYYY-MM-DD``; defaults to the last week.
        """
        try:
            return yandex.query_stats(
                site, order_by=order_by, device=device,
                date_from=date_from, date_to=date_to, limit=limit,
            )
        except (EngineNotConfiguredError, EngineError) as e:
            return {"error": str(e)}

    @mcp.tool()
    def yandex_url_info(site: str, url: str) -> dict[str, Any]:
        """Indexing + search status for a URL in Yandex "Monitoring important pages"."""
        try:
            return yandex.url_info(site, url)
        except (EngineNotConfiguredError, EngineError) as e:
            return {"error": str(e)}

    @mcp.tool()
    def yandex_submit_url(site: str, url: str) -> dict[str, Any]:
        """Queue a URL for Yandex recrawl. Daily quota applies."""
        try:
            return yandex.submit_url(site, url)
        except (EngineNotConfiguredError, EngineError) as e:
            return {"error": str(e)}

    @mcp.tool()
    def yandex_crawl_issues(site: str) -> dict[str, Any]:
        """Active Yandex site diagnostics (by severity) plus sample broken internal links."""
        try:
            return yandex.crawl_issues(site)
        except (EngineNotConfiguredError, EngineError) as e:
            return {"error": str(e)}
