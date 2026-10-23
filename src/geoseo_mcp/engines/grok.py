"""xAI Grok engine (Grok with live web search).

Uses the xAI Responses API with the server-side ``web_search`` tool. Grok's
answer carries inline ``[[N]](url)`` links plus ``url_citation`` annotations;
those are the URLs we treat as cited. The response's top-level ``citations``
list contains every source the agent looked at (including ones it discarded),
so it is returned separately as ``sources_considered``.

The older Chat Completions ``search_parameters`` (Live Search) API is retired.

Docs:
    https://docs.x.ai/developers/tools/web-search
    https://docs.x.ai/developers/tools/citations
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

import httpx

from ..config import get_config
from .base import EngineError, EngineNotConfiguredError

XAI_RESPONSES_ENDPOINT = "https://api.x.ai/v1/responses"
_INLINE_RE = re.compile(r"\[\[\d+\]\]\((https?://[^)\s]+)\)")


def _require_key() -> str:
    cfg = get_config()
    if not cfg.grok_api_key:
        raise EngineNotConfiguredError(
            "grok",
            "Set GEOSEO_XAI_API_KEY to a key from https://console.x.ai.",
        )
    return cfg.grok_api_key


def build_payload(
    question: str,
    model: str,
    system_prompt: str | None = None,
    x_search: bool = False,
) -> dict[str, Any]:
    tools: list[dict[str, Any]] = [{"type": "web_search"}]
    if x_search:
        tools.append({"type": "x_search"})
    payload: dict[str, Any] = {
        "model": model,
        "input": [{"role": "user", "content": question}],
        "tools": tools,
    }
    if system_prompt:
        payload["instructions"] = system_prompt
    return payload


def query(
    question: str,
    model: str | None = None,
    system_prompt: str | None = None,
    x_search: bool = False,
) -> dict[str, Any]:
    cfg = get_config()
    api_key = _require_key()
    model = model or cfg.grok_model
    payload = build_payload(question, model, system_prompt, x_search=x_search)

    with httpx.Client(timeout=max(cfg.request_timeout_s, 120.0)) as c:
        r = c.post(
            XAI_RESPONSES_ENDPOINT,
            json=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": cfg.user_agent,
            },
        )
    if r.status_code >= 400:
        raise EngineError(f"xAI {r.status_code}: {r.text[:300]}")

    data = r.json()
    answer, citations = _extract(data)
    considered = [u for u in data.get("citations", []) or [] if isinstance(u, str)]
    return {
        "engine": "grok",
        "question": question,
        "model": data.get("model", model),
        "answer": answer,
        "citations": citations,
        "cited_domains": sorted({_domain(u) for u in citations if u}),
        "sources_considered": considered,
        "usage": data.get("usage", {}),
    }


def _extract(data: dict[str, Any]) -> tuple[str, list[str]]:
    text_parts: list[str] = []
    urls: list[str] = []
    for item in data.get("output", []) or []:
        if item.get("type") not in (None, "message"):
            continue
        for c in item.get("content", []) or []:
            if c.get("type") not in (None, "output_text"):
                continue
            t = c.get("text") or ""
            if t:
                text_parts.append(t)
            for ann in c.get("annotations", []) or []:
                if ann.get("type") == "url_citation" and ann.get("url"):
                    urls.append(ann["url"])
    answer = "".join(text_parts)
    if not urls:
        urls = _INLINE_RE.findall(answer)
    return answer, list(dict.fromkeys(urls))


def _domain(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        return url
    return host[4:] if host.startswith("www.") else host
