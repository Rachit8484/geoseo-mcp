"""Perplexity engine (Agent API).

Perplexity retired Sonar Chat Completions in favour of the Agent API
(``POST /v1/agent``, Open Responses format). Sources come back as a typed
``search_results`` output item, and the answer cites them with ``[n]`` /
``[web:n]`` markers that map to each result's ``id``.

By default we use the ``fast`` effort preset (Perplexity's suggested
replacement for ``sonar``). Set ``GEOSEO_PERPLEXITY_EFFORT`` to change the
preset, or ``GEOSEO_PERPLEXITY_MODEL`` to pin a specific model
(e.g. ``openai/gpt-5-mini``) with the ``web_search`` tool. Legacy Sonar model
names are mapped to their recommended effort level.

Docs: https://docs.perplexity.ai/docs/agent-api/quickstart
"""

from __future__ import annotations

import re
from typing import Any

import httpx

from ..config import get_config
from ._domains import any_match, domain_of, matches_domain, normalize_domain
from .base import EngineError, EngineNotConfiguredError

PPLX_ENDPOINT = "https://api.perplexity.ai/v1/agent"

# https://docs.perplexity.ai/docs/agent-api/migrate-from-sonar/how-to
SONAR_TO_EFFORT = {
    "sonar": "fast",
    "sonar-pro": "fast",
    "sonar-reasoning-pro": "low",
    "sonar-deep-research": "high",
}
_MARKER_RE = re.compile(r"\[(?:web:)?(\d+)\]")


def _require_key() -> str:
    cfg = get_config()
    if not cfg.perplexity_api_key:
        raise EngineNotConfiguredError(
            "perplexity",
            "Set GEOSEO_PERPLEXITY_API_KEY to a key from "
            "https://www.perplexity.ai/settings/api.",
        )
    return cfg.perplexity_api_key


def build_payload(
    question: str,
    model: str | None = None,
    system_prompt: str | None = None,
    max_tokens: int | None = None,
) -> tuple[dict[str, Any], str]:
    """Return ``(payload, label)`` where label is what we report as ``model``."""
    cfg = get_config()
    model = model or cfg.perplexity_model
    payload: dict[str, Any] = {"input": question}
    if model and model not in SONAR_TO_EFFORT:
        payload["model"] = model
        payload["tools"] = [{"type": "web_search"}]
        label = model
    else:
        effort = SONAR_TO_EFFORT.get(model or "", cfg.perplexity_effort)
        payload["effort"] = effort
        label = f"effort:{effort}"
    if system_prompt:
        payload["instructions"] = system_prompt
    if max_tokens:
        payload["max_output_tokens"] = max_tokens
    return payload, label


def query(
    question: str,
    model: str | None = None,
    system_prompt: str | None = None,
    max_tokens: int | None = None,
) -> dict[str, Any]:
    cfg = get_config()
    api_key = _require_key()
    payload, label = build_payload(question, model, system_prompt, max_tokens)

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
    answer, citations, sources = _extract(data)
    cited_domains = sorted({_domain(u) for u in citations if u})

    return {
        "engine": "perplexity",
        "question": question,
        "model": data.get("model") or label,
        "answer": answer,
        "citations": citations,
        "cited_domains": cited_domains,
        "sources_considered": len(sources),
        "usage": data.get("usage", {}),
    }


def _extract(data: dict[str, Any]) -> tuple[str, list[str], list[str]]:
    """Return ``(answer, cited_urls, all_source_urls)``.

    Cited URLs are the results referenced by ``[n]`` markers. If the answer has
    no markers we fall back to every returned source. Legacy Sonar-shaped
    payloads (``choices`` + ``citations``) are still understood.
    """
    if "choices" in data:  # legacy Sonar shape
        answer = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
        urls = list(data.get("citations") or [])
        return answer, urls, urls

    text_parts: list[str] = []
    by_id: dict[int, str] = {}
    order: list[str] = []
    for item in data.get("output", []) or []:
        kind = item.get("type")
        if kind == "search_results":
            for res in item.get("results", []) or []:
                url = res.get("url")
                if not url:
                    continue
                if isinstance(res.get("id"), int):
                    by_id[res["id"]] = url
                if url not in order:
                    order.append(url)
        elif kind == "message":
            for c in item.get("content", []) or []:
                if c.get("type") in ("output_text", "text") and c.get("text"):
                    text_parts.append(c["text"])
                for ann in c.get("annotations", []) or []:
                    u = ann.get("url")
                    if u and u not in order:
                        order.append(u)
    answer = "".join(text_parts) or str(data.get("output_text") or "")

    cited: list[str] = []
    for m in _MARKER_RE.finditer(answer):
        u = by_id.get(int(m.group(1)))
        if u and u not in cited:
            cited.append(u)
    return answer, (cited or order), order


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

        cited = any_match(res["cited_domains"], target)
        if cited:
            cited_count += 1
        for d in res["cited_domains"]:
            if not matches_domain(d, target):
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
    return domain_of(url)


def _domain_only(host: str) -> str:
    return normalize_domain(host)
