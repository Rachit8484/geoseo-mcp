"""Perplexity engine.

Perplexity returns answers WITH citations as a structured field, which is why
it's our v0.1 LLM target: cleanest signal for citation-share metrics.

API: https://docs.perplexity.ai/reference/post_chat_completions
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import httpx

from ..config import get_config
from .base import EngineError, EngineNotConfiguredError

PPLX_ENDPOINT = "https://api.perplexity.ai/chat/completions"


def _require_key() -> str:
    cfg = get_config()
    if not cfg.perplexity_api_key:
        raise EngineNotConfiguredError(
            "perplexity",
            "Set GEOSEO_PERPLEXITY_API_KEY to a key from "
            "https://www.perplexity.ai/settings/api.",
        )
    return cfg.perplexity_api_key


def query(
    question: str,
    model: str | None = None,
    system_prompt: str | None = None,
    max_tokens: int = 1024,
) -> dict[str, Any]:
    cfg = get_config()
    api_key = _require_key()
    model = model or cfg.perplexity_model

    messages: list[dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": question})

    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "return_citations": True,
        "return_related_questions": False,
    }

    with httpx.Client(timeout=cfg.request_timeout_s) as c:
        r = c.post(
            PPLX_ENDPOINT,
            json=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": cfg.user_agent,
            },
        )

    if r.status_code >= 400:
        raise EngineError(f"Perplexity {r.status_code}: {r.text[:300]}")

    data = r.json()
    answer = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    citations: list[str] = data.get("citations", []) or []
    cited_domains = sorted({_domain(u) for u in citations if u})

    return {
        "question": question,
        "model": model,
        "answer": answer,
        "citations": citations,
        "cited_domains": cited_domains,
        "usage": data.get("usage", {}),
    }


def citation_check(
    questions: list[str],
    target_domain: str,
    model: str | None = None,
) -> dict[str, Any]:
    target = _domain_only(target_domain)
    results: list[dict[str, Any]] = []
    cited_count = 0
    competing_domains: dict[str, int] = {}

    for q in questions:
        try:
            res = query(q, model=model)
        except EngineError as e:
            results.append({"question": q, "error": str(e)})
            continue

        cited = target in res["cited_domains"]
        if cited:
            cited_count += 1
        for d in res["cited_domains"]:
            if d != target:
                competing_domains[d] = competing_domains.get(d, 0) + 1

        results.append(
            {
                "question": q,
                "cited": cited,
                "cited_domains": res["cited_domains"],
                "answer_excerpt": (res["answer"] or "")[:280],
            }
        )

    top_competitors = sorted(competing_domains.items(), key=lambda kv: kv[1], reverse=True)[:10]
    return {
        "target_domain": target,
        "questions_asked": len(questions),
        "questions_with_target_cited": cited_count,
        "citation_share": (cited_count / len(questions)) if questions else 0.0,
        "top_competing_domains": [{"domain": d, "citations": n} for d, n in top_competitors],
        "results": results,
    }


def _domain(url: str) -> str:
    try:
        return _domain_only(urlparse(url).netloc or url)
    except Exception:
        return url


def _domain_only(host: str) -> str:
    host = host.strip().lower()
    if host.startswith("http://") or host.startswith("https://"):
        host = urlparse(host).netloc
    if host.startswith("www."):
        host = host[4:]
    return host
