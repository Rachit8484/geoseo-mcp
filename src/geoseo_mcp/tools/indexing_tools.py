"""Indexing / submission tools."""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from ..engines import indexnow
from ..engines.base import EngineError, EngineNotConfiguredError


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def indexnow_submit_url(url: str) -> dict[str, Any]:
        """Notify Bing, Yandex, Naver, Seznam, and Yep that a single URL was published or updated.

        Requires ``GEOSEO_INDEXNOW_KEY`` env var (a 32-char hex string you also
        host at ``https://yourdomain.com/<key>.txt``).
        """
        try:
            return indexnow.submit_url(url)
        except (EngineNotConfiguredError, EngineError) as e:
            return {"error": str(e)}

    @mcp.tool()
    def indexnow_submit_urls(urls: list[str]) -> dict[str, Any]:
        """Batch-notify search engines about up to 10,000 URLs (must share one host).

        Best for sitemap-wide rebuilds or large content updates.
        """
        try:
            return indexnow.submit_urls(urls)
        except (EngineNotConfiguredError, EngineError) as e:
            return {"error": str(e)}
