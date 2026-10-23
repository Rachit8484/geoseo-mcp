"""Google Gemini engine (with Google Search grounding).

Uses ``generateContent`` with the ``google_search`` tool. Citations are
returned in ``candidates[0].groundingMetadata.groundingChunks[].web.uri``.
This is the same grounding signal Google's AI Overviews use.

Docs: https://ai.google.dev/gemini-api/docs/grounding
"""

from __future__ import annotations

import re
from typing import Any

import httpx

from ..config import get_config
from ._domains import domain_of, normalize_domain
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

    # Key goes in a header so it never ends up in URLs, logs or tracebacks.
    url = f"{GEMINI_BASE}/{model}:generateContent"
    with httpx.Client(timeout=cfg.request_timeout_s) as c:
        r = c.post(
            url,
            json=payload,
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": api_key,
                "User-Agent": cfg.user_agent,
            },
        )
    if r.status_code >= 400:
        raise EngineError(f"Gemini {r.status_code}: {r.text[:300]}")

    data = r.json()
    answer, citations = _extract_answer_and_citations(data)
    cited_domains = _cited_domains(data)

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


_REDIRECT_HOSTS = {"vertexaisearch.cloud.google.com"}
_DOMAIN_RE = re.compile(r"^[a-z0-9-]+(\.[a-z0-9-]+)+$")


def _cited_domains(data: dict[str, Any]) -> list[str]:
    """Domains behind the grounding chunks.

    Gemini returns ``vertexaisearch.cloud.google.com/grounding-api-redirect/...``
    URLs, not the source URL. The source domain lives in ``web.domain`` (newer
    responses) or ``web.title`` (which is the bare domain in practice).
    """
    out: set[str] = set()
    for cand in data.get("candidates", []) or []:
        gm = cand.get("groundingMetadata", {}) or {}
        for chunk in gm.get("groundingChunks", []) or []:
            web = chunk.get("web") or {}
            uri = web.get("uri") or web.get("url") or ""
            host = _domain(uri) if uri else ""
            if host and host not in _REDIRECT_HOSTS:
                out.add(host)
                continue
            for candidate in (web.get("domain"), web.get("title")):
                d = normalize_domain(candidate or "")
                if d and _DOMAIN_RE.match(d):
                    out.add(d)
                    break
    return sorted(out)


def _domain(url: str) -> str:
    return domain_of(url)
