"""Brave Answers engine (AI answers grounded in Brave Search).

Brave's Answers API is OpenAI-compatible (``/res/v1/chat/completions``, model
``brave``). Citations are only available in streaming mode: with
``enable_citations=true`` the stream interleaves plain text with
``<citation>{json}</citation>`` and a final ``<usage>{json}</usage>`` tag. We
read the whole stream, pull those tags out, and return the clean answer with
``[n]`` markers where the citations were.

Pricing (Answers plan): $4 per 1,000 searches + $5 per million tokens in/out.

Docs: https://api-dashboard.search.brave.com/documentation/services/answers
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from typing import Any
from urllib.parse import urlparse

import httpx

from ..config import get_config
from .base import EngineError, EngineNotConfiguredError

BRAVE_ANSWERS_ENDPOINT = "https://api.search.brave.com/res/v1/chat/completions"
_TAG_RE = re.compile(r"<(citation|usage)>(.*?)</\1>", re.DOTALL)


def _require_key() -> str:
    cfg = get_config()
    if not cfg.brave_api_key:
        raise EngineNotConfiguredError(
            "brave",
            "Set GEOSEO_BRAVE_API_KEY to a key with the Answers plan "
            "(https://api-dashboard.search.brave.com).",
        )
    return cfg.brave_api_key


def build_payload(question: str, country: str = "us", language: str = "en") -> dict[str, Any]:
    return {
        "model": "brave",
        "messages": [{"role": "user", "content": question}],
        "stream": True,
        "enable_citations": True,
        "country": country,
        "language": language,
    }


def query(
    question: str,
    country: str = "us",
    language: str = "en",
) -> dict[str, Any]:
    cfg = get_config()
    api_key = _require_key()
    payload = build_payload(question, country=country, language=language)

    with httpx.Client(timeout=max(cfg.request_timeout_s, 60.0)) as c, c.stream(
        "POST",
        BRAVE_ANSWERS_ENDPOINT,
        json=payload,
        headers={
            "X-Subscription-Token": api_key,
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "User-Agent": cfg.user_agent,
        },
    ) as r:
        if r.status_code >= 400:
            r.read()
            raise EngineError(f"Brave {r.status_code}: {r.text[:300]}")
        raw = "".join(iter_sse_content(r.iter_lines()))

    answer, citations, usage = parse_content(raw)
    urls = list(dict.fromkeys(c["url"] for c in citations if c.get("url")))
    return {
        "engine": "brave",
        "question": question,
        "model": "brave",
        "answer": answer,
        "citations": urls,
        "cited_domains": sorted({_domain(u) for u in urls}),
        "citation_details": citations,
        "usage": usage,
    }


def iter_sse_content(lines: Iterable[str]) -> Iterable[str]:
    """Yield ``choices[0].delta.content`` from OpenAI-style SSE ``data:`` lines."""
    for line in lines:
        line = line.strip()
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if not data or data == "[DONE]":
            continue
        try:
            chunk = json.loads(data)
        except json.JSONDecodeError:
            continue
        for choice in chunk.get("choices", []) or []:
            content = (choice.get("delta") or {}).get("content")
            if content:
                yield content


def parse_content(raw: str) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
    """Split streamed content into (answer text, citations, usage)."""
    citations: list[dict[str, Any]] = []
    usage: dict[str, Any] = {}

    def repl(m: re.Match[str]) -> str:
        nonlocal usage
        try:
            obj = json.loads(m.group(2))
        except json.JSONDecodeError:
            return ""
        if m.group(1) == "usage":
            usage = obj if isinstance(obj, dict) else {}
            return ""
        if isinstance(obj, dict):
            citations.append(
                {k: obj.get(k) for k in ("number", "url", "snippet", "start_index", "end_index")}
            )
            return f"[{obj.get('number')}]" if obj.get("number") is not None else ""
        return ""

    answer = _TAG_RE.sub(repl, raw).strip()
    return answer, citations, usage


def _domain(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        return url
    return host[4:] if host.startswith("www.") else host
