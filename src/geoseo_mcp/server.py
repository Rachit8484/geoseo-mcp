"""FastMCP server wiring.

Tools are grouped into modules under `tools/`. Each module exposes a
`register(mcp)` function that attaches its tools to the FastMCP instance,
keeping `server.py` declarative.
"""

from __future__ import annotations

from fastmcp import FastMCP

from . import __version__
from .tools import audit_tools, gsc_tools, indexing_tools, llm_tools


def build_server() -> FastMCP:
    mcp = FastMCP(
        name="geoseo-mcp",
        instructions=(
            "Unified SEO + GEO toolkit. Use `gsc_*` for Google Search Console, "
            "`indexnow_*` to notify Bing/Yandex/Naver/Seznam, `perplexity_*` to "
            "track LLM citations, and `audit_*` for on-page checks. Call "
            "`geoseo_status` first to see which engines are configured."
        ),
    )

    @mcp.tool()
    def geoseo_status() -> dict:
        """Report which engines are configured and reachable.

        Always safe to call. Returns a dict keyed by engine name with
        `configured: bool` and a short message. Use this as the first call
        in a session to know what's available.
        """
        from .config import get_config

        cfg = get_config()
        return {
            "version": __version__,
            "engines": {
                "google_search_console": {
                    "configured": cfg.google_client_secret is not None,
                    "message": (
                        "OAuth client secret configured."
                        if cfg.google_client_secret
                        else "Set GEOSEO_GOOGLE_CLIENT_SECRET to a path "
                        "to your OAuth client_secret.json. See docs/setup-gsc.md."
                    ),
                },
                "indexnow": {
                    "configured": cfg.indexnow_key is not None,
                    "message": (
                        "IndexNow key configured."
                        if cfg.indexnow_key
                        else "Set GEOSEO_INDEXNOW_KEY to a 32-char hex string "
                        "and host it at https://yourdomain.com/<key>.txt."
                    ),
                },
                "perplexity": {
                    "configured": cfg.perplexity_api_key is not None,
                    "message": (
                        "Perplexity API key configured."
                        if cfg.perplexity_api_key
                        else "Set GEOSEO_PERPLEXITY_API_KEY to a key from "
                        "https://www.perplexity.ai/settings/api."
                    ),
                },
                "on_page_audit": {
                    "configured": True,
                    "message": "Always available; needs no credentials.",
                },
            },
        }

    gsc_tools.register(mcp)
    indexing_tools.register(mcp)
    llm_tools.register(mcp)
    audit_tools.register(mcp)

    return mcp
