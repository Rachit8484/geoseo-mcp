"""Anthropic engine (Claude with web search).

Uses Messages API with the ``web_search_20250305`` server-side tool. Citations
arrive as ``citations`` arrays inside text content blocks.

Docs: https://docs.anthropic.com/en/docs/build-with-claude/tool-use/web-search-tool
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import httpx

from ..config import get_config
from .base import EngineError, EngineNotConfiguredError

ANTHROPIC_MESSAGES_ENDPOINT = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"


def _require_key() -> str:
    cfg = get_config()
    if not cfg.anthropic_api_key:
        raise EngineNotConfiguredError(
            "anthropic",
            "Set GEOSEO_ANTHROPIC_API_KEY to a key from "
            "https://console.anthropic.com/settings/keys.",
        )
    return cfg.anthropic_api_key


def query(
    question: str,
    model: str | None = None,
    system_prompt: str | None = None,
    max_tokens: int = 1024,
) -> dict[str, Any]:
    cfg = get_config()
    api_key = _require_key()
    model = model or cfg.anthropic_model

    payload: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": question}],
        "tools": [{"type": "web_search_20250305", "name": "web_search"}],
    }
    if system_prompt:
        payload["system"] = system_prompt

    with httpx.Client(timeout=cfg.request_timeout_s) as c:
        r = c.post(
            ANTHROPIC_MESSAGES_ENDPOINT,
            json=payload,
            headers={
                "x-api-key": api_key,
                "anthropic-version": ANTHROPIC_VERSION,
                "content-type": "application/json",
                "User-Agent": cfg.user_agent,
            },
        )
    if r.status_code >= 400:
        raise EngineError(f"Anthropic {r.status_code}: {r.text[:300]}")

    data = r.json()
    answer, citations = _extract_answer_and_citations(data)
    cited_domains = sorted({_domain(u) for u in citations if u})

    return {
        "engine": "anthropic",
        "question": question,
        "model": model,
        "answer": answer,
        "citations": citations,
        "cited_domains": cited_domains,
        "usage": data.get("usage", {}),
    }


def _extract_answer_and_citations(data: dict[str, Any]) -> tuple[str, list[str]]:
    text_parts: list[str] = []
    urls: list[str] = []
    for block in data.get("content", []) or []:
        if block.get("type") == "text":
            t = block.get("text") or ""
            if t:
                text_parts.append(t)
            for cit in block.get("citations", []) or []:
                u = cit.get("url") or cit.get("source", {}).get("url")
                if u:
                    urls.append(u)
        elif block.get("type") == "web_search_tool_result":
            for r in block.get("content", []) or []:
                u = r.get("url") if isinstance(r, dict) else None
                if u:
                    urls.append(u)
    seen: set[str] = set()
    deduped: list[str] = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            deduped.append(u)
    return "".join(text_parts), deduped


def _domain(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        return url
    return host[4:] if host.startswith("www.") else host
