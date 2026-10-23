"""FastMCP server wiring.

Tools are grouped into modules under `tools/`. Each module exposes a
`register(mcp)` function that attaches its tools to the FastMCP instance,
keeping `server.py` declarative.
"""

from __future__ import annotations

import os
from collections.abc import Iterable

from fastmcp import FastMCP

from . import __version__
from .tools import (
    audit_tools,
    bing_tools,
    graph_tools,
    gsc_tools,
    indexing_tools,
    llm_tools,
    serpapi_tools,
    trend_tools,
)

TOOLSETS = {
    "gsc": gsc_tools,
    "bing": bing_tools,
    "indexing": indexing_tools,
    "llm": llm_tools,
    "aio": serpapi_tools,
    "audit": audit_tools,
    "graph": graph_tools,
    "trend": trend_tools,
}


def resolve_toolsets(value: str | Iterable[str] | None = None) -> list[str]:
    """Parse ``GEOSEO_TOOLSETS`` (comma-separated). Empty or ``all`` = everything."""
    if value is None:
        value = os.getenv("GEOSEO_TOOLSETS", "")
    names = (
        [v.strip().lower() for v in value.split(",")]
        if isinstance(value, str)
        else [v.strip().lower() for v in value]
    )
    names = [n for n in names if n]
    if not names or "all" in names:
        return list(TOOLSETS)
    unknown = sorted(set(names) - set(TOOLSETS))
    if unknown:
        raise ValueError(
            f"Unknown GEOSEO_TOOLSETS value(s): {', '.join(unknown)}. "
            f"Valid: {', '.join(TOOLSETS)} (or 'all')."
        )
    return [n for n in TOOLSETS if n in names]


def build_server(toolsets: str | Iterable[str] | None = None) -> FastMCP:
    """Build the server. ``toolsets`` overrides ``GEOSEO_TOOLSETS``.

    ``geoseo_status`` is always registered; everything else can be trimmed so
    clients with tight tool limits only see what you use.
    """
    enabled = resolve_toolsets(toolsets)
    mcp = FastMCP(
        name="geoseo-mcp",
        instructions=(
            "Unified SEO + GEO toolkit. Use `gsc_*` for Google Search Console, "
            "`bing_*` for Bing Webmaster, `indexnow_*` to notify search engines, "
            "`*_query`/`multi_llm_*` to track LLM citations across "
            "ChatGPT/Claude/Gemini/Perplexity/Grok, `aio_*` for Google AI Overviews "
            "(via SerpAPI), `audit_*` for on-page checks, "
            "`internal_link_graph`/`suggest_internal_links` for site structure, "
            "and `snapshot_*`/`trend_*` for local SQLite-backed time-series. "
            "Call `geoseo_status` first to see which engines are configured."
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
            "toolsets": enabled,
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
                        "Perplexity configured (Agent API, "
                        f"{cfg.perplexity_model or 'effort ' + cfg.perplexity_effort})."
                        if cfg.perplexity_api_key
                        else "Set GEOSEO_PERPLEXITY_API_KEY (https://www.perplexity.ai/settings/api)."
                    ),
                },
                "openai": {
                    "configured": cfg.openai_api_key is not None,
                    "message": (
                        f"OpenAI configured (model: {cfg.openai_model})."
                        if cfg.openai_api_key
                        else "Set GEOSEO_OPENAI_API_KEY (https://platform.openai.com/api-keys)."
                    ),
                },
                "anthropic": {
                    "configured": cfg.anthropic_api_key is not None,
                    "message": (
                        f"Anthropic configured (model: {cfg.anthropic_model})."
                        if cfg.anthropic_api_key
                        else "Set GEOSEO_ANTHROPIC_API_KEY (https://console.anthropic.com/settings/keys)."
                    ),
                },
                "gemini": {
                    "configured": cfg.gemini_api_key is not None,
                    "message": (
                        f"Gemini configured (model: {cfg.gemini_model})."
                        if cfg.gemini_api_key
                        else "Set GEOSEO_GEMINI_API_KEY (https://aistudio.google.com/app/apikey)."
                    ),
                },
                "grok": {
                    "configured": cfg.grok_api_key is not None,
                    "message": (
                        f"xAI Grok configured (model: {cfg.grok_model})."
                        if cfg.grok_api_key
                        else "Set GEOSEO_XAI_API_KEY (https://console.x.ai)."
                    ),
                },
                "bing_webmaster": {
                    "configured": cfg.bing_webmaster_api_key is not None,
                    "message": (
                        "Bing Webmaster API key configured."
                        if cfg.bing_webmaster_api_key
                        else "Set GEOSEO_BING_WEBMASTER_API_KEY "
                        "(https://www.bing.com/webmasters → Settings → API access)."
                    ),
                },
                "serpapi_aio": {
                    "configured": cfg.serpapi_api_key is not None,
                    "message": (
                        "SerpAPI key configured (Google AI Overviews tracking enabled)."
                        if cfg.serpapi_api_key
                        else "Set GEOSEO_SERPAPI_API_KEY (https://serpapi.com/manage-api-key) "
                        "to enable Google AI Overviews tracking."
                    ),
                },
                "on_page_audit": {
                    "configured": True,
                    "message": "Always available; needs no credentials.",
                },
                "llms_txt": {
                    "configured": True,
                    "message": "Always available; needs no credentials.",
                },
                "internal_link_graph": {
                    "configured": True,
                    "message": "Always available; needs no credentials.",
                },
                "trend_storage": {
                    "configured": True,
                    "message": (
                        "Local SQLite snapshot store. Override location via GEOSEO_DB."
                    ),
                },
            },
        }

    for name in enabled:
        TOOLSETS[name].register(mcp)

    return mcp
