"""Google Gemini engine (with Google Search grounding).

Uses ``generateContent`` with the ``google_search`` tool. Citations are
returned in ``candidates[0].groundingMetadata.groundingChunks[].web.uri``.
This is the same grounding signal Google's AI Overviews use.

Docs: https://ai.google.dev/gemini-api/docs/grounding
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import httpx

from ..config import get_config
from .base import EngineError, EngineNotConfiguredError

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


def _require_key() -> str:
    cfg = get_config()
    if not cfg.gemini_api_key:
        raise EngineNotConfiguredError(
            "gemini",
            "Set GEOSEO_GEMINI_API_KEY to a key from "
            "https://aistudio.google.com/app/apikey.",
        )
    return cfg.gemini_api_key


def query(
    question: str,
    model: str | None = None,
    system_prompt: str | None = None,
) -> dict[str, Any]:
    cfg = get_config()
    api_key = _require_key()
    model = model or cfg.gemini_model

    payload: dict[str, Any] = {
        "contents": [{"role": "user", "parts": [{"text": question}]}],
        "tools": [{"google_search": {}}],
    }
    if system_prompt:
        payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}

    url = f"{GEMINI_BASE}/{model}:generateContent?key={api_key}"
    with httpx.Client(timeout=cfg.request_timeout_s) as c:
        r = c.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json", "User-Agent": cfg.user_agent},
        )
    if r.status_code >= 400:
        raise EngineError(f"Gemini {r.status_code}: {r.text[:300]}")

    data = r.json()
    answer, citations = _extract_answer_and_citations(data)
    cited_domains = sorted({_domain(u) for u in citations if u})

    return {
        "engine": "gemini",
        "question": question,
        "model": model,
        "answer": answer,
        "citations": citations,
        "cited_domains": cited_domains,
        "usage": data.get("usageMetadata", {}),
    }


def _extract_answer_and_citations(data: dict[str, Any]) -> tuple[str, list[str]]:
    text_parts: list[str] = []
    urls: list[str] = []
    for cand in data.get("candidates", []) or []:
        for part in cand.get("content", {}).get("parts", []) or []:
            t = part.get("text")
            if t:
                text_parts.append(t)
        gm = cand.get("groundingMetadata", {}) or {}
        for chunk in gm.get("groundingChunks", []) or []:
            web = chunk.get("web") or {}
            u = web.get("uri") or web.get("url")
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
