"""OpenAI engine (ChatGPT with web search).

Uses the Responses API + ``web_search_preview`` tool, which returns inline
``url_citation`` annotations alongside the generated text. This is the cleanest
way to attribute ChatGPT's answer to specific URLs.

Docs: https://platform.openai.com/docs/guides/tools-web-search
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import httpx

from ..config import get_config
from .base import EngineError, EngineNotConfiguredError

OPENAI_RESPONSES_ENDPOINT = "https://api.openai.com/v1/responses"


def _require_key() -> str:
    cfg = get_config()
    if not cfg.openai_api_key:
        raise EngineNotConfiguredError(
            "openai",
            "Set GEOSEO_OPENAI_API_KEY to a key from "
            "https://platform.openai.com/api-keys.",
        )
    return cfg.openai_api_key


def query(
    question: str,
    model: str | None = None,
    system_prompt: str | None = None,
) -> dict[str, Any]:
    cfg = get_config()
    api_key = _require_key()
    model = model or cfg.openai_model

    payload: dict[str, Any] = {
        "model": model,
        "input": question,
        "tools": [{"type": "web_search_preview"}],
    }
    if system_prompt:
        payload["instructions"] = system_prompt

    with httpx.Client(timeout=cfg.request_timeout_s) as c:
        r = c.post(
            OPENAI_RESPONSES_ENDPOINT,
            json=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": cfg.user_agent,
            },
        )
    if r.status_code >= 400:
        raise EngineError(f"OpenAI {r.status_code}: {r.text[:300]}")

    data = r.json()
    answer, citations = _extract_answer_and_citations(data)
    cited_domains = sorted({_domain(u) for u in citations if u})

    return {
        "engine": "openai",
        "question": question,
        "model": model,
        "answer": answer,
        "citations": citations,
        "cited_domains": cited_domains,
        "usage": data.get("usage", {}),
    }


def _extract_answer_and_citations(data: dict[str, Any]) -> tuple[str, list[str]]:
    """Walk the Responses-API output tree. Defensive: schema evolves."""
    text_parts: list[str] = []
    urls: list[str] = []
    for item in data.get("output", []) or []:
        for c in item.get("content", []) or []:
            t = c.get("text") or ""
            if isinstance(t, str) and t:
                text_parts.append(t)
            for ann in c.get("annotations", []) or []:
                if ann.get("type") in {"url_citation", "url"}:
                    u = ann.get("url") or ann.get("href")
                    if u:
                        urls.append(u)
    if not text_parts and "output_text" in data:
        text_parts.append(str(data["output_text"]))
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
