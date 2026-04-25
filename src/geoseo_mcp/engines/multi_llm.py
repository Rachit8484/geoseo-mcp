"""Cross-engine helpers.

Why this module exists: every individual LLM engine returns the same shape
(``{question, answer, citations, cited_domains, ...}``), so ``citation_check``
logic is identical across them. We factor it here once and run any subset of
configured engines in parallel for the ``multi_llm_*`` tools.
"""

from __future__ import annotations

import concurrent.futures as cf
from collections.abc import Callable
from typing import Any

from ..config import get_config
from . import anthropic, gemini, openai, perplexity
from .base import EngineError, EngineNotConfiguredError

EngineFn = Callable[[str], dict[str, Any]]


def _engines_available() -> dict[str, EngineFn]:
    cfg = get_config()
    out: dict[str, EngineFn] = {}
    if cfg.perplexity_api_key:
        out["perplexity"] = lambda q: perplexity.query(q)
    if cfg.openai_api_key:
        out["openai"] = lambda q: openai.query(q)
    if cfg.anthropic_api_key:
        out["anthropic"] = lambda q: anthropic.query(q)
    if cfg.gemini_api_key:
        out["gemini"] = lambda q: gemini.query(q)
    return out


def list_configured_engines() -> list[str]:
    return sorted(_engines_available().keys())


def multi_query(question: str, engines: list[str] | None = None) -> dict[str, Any]:
    """Ask the same question to every configured (or selected) engine in parallel.

    Returns a dict keyed by engine name. Engines that error are reported but
    don't block the others.
    """
    available = _engines_available()
    if not available:
        raise EngineNotConfiguredError(
            "any LLM",
            "No LLM engines configured. Set at least one of "
            "GEOSEO_PERPLEXITY_API_KEY, GEOSEO_OPENAI_API_KEY, "
            "GEOSEO_ANTHROPIC_API_KEY, or GEOSEO_GEMINI_API_KEY.",
        )

    selected = {name: fn for name, fn in available.items() if not engines or name in engines}
    if not selected:
        raise EngineError(f"No requested engines are configured. Available: {sorted(available)}")

    results: dict[str, Any] = {}
    with cf.ThreadPoolExecutor(max_workers=len(selected)) as pool:
        futures = {pool.submit(fn, question): name for name, fn in selected.items()}
        for fut in cf.as_completed(futures):
            name = futures[fut]
            try:
                results[name] = fut.result()
            except (EngineNotConfiguredError, EngineError) as e:
                results[name] = {"engine": name, "error": str(e)}
            except Exception as e:
                results[name] = {"engine": name, "error": f"unexpected: {e}"}
    return {"question": question, "engines_queried": sorted(selected.keys()), "results": results}


def multi_citation_check(
    questions: list[str],
    target_domain: str,
    engines: list[str] | None = None,
) -> dict[str, Any]:
    """Citation-share metrics across every configured LLM in one pass.

    Output mirrors ``perplexity_citation_check`` but adds a per-engine
    breakdown so you can see *which* LLM cites you and which doesn't.
    """
    target = _normalize_domain(target_domain)

    per_engine: dict[str, dict[str, Any]] = {}
    available = _engines_available()
    selected = [e for e in available if not engines or e in engines]
    if not selected:
        raise EngineNotConfiguredError(
            "any LLM",
            "No LLM engines configured. See geoseo_status for setup hints.",
        )

    for engine in selected:
        per_engine[engine] = {
            "questions_with_target_cited": 0,
            "competing_domains": {},
            "errors": 0,
            "results": [],
        }

    for q in questions:
        mq = multi_query(q, engines=selected)
        for engine, res in mq["results"].items():
            bucket = per_engine[engine]
            if "error" in res:
                bucket["errors"] += 1
                bucket["results"].append({"question": q, "error": res["error"]})
                continue
            cited = target in res["cited_domains"]
            if cited:
                bucket["questions_with_target_cited"] += 1
            for d in res["cited_domains"]:
                if d != target:
                    bucket["competing_domains"][d] = bucket["competing_domains"].get(d, 0) + 1
            bucket["results"].append(
                {
                    "question": q,
                    "cited": cited,
                    "cited_domains": res["cited_domains"],
                    "answer_excerpt": (res.get("answer") or "")[:280],
                }
            )

    summary = {}
    for engine, bucket in per_engine.items():
        n = len(questions) - bucket["errors"]
        share = (bucket["questions_with_target_cited"] / n) if n else 0.0
        top = sorted(bucket["competing_domains"].items(), key=lambda kv: kv[1], reverse=True)[:10]
        summary[engine] = {
            "questions_asked": len(questions),
            "questions_with_errors": bucket["errors"],
            "questions_with_target_cited": bucket["questions_with_target_cited"],
            "citation_share": share,
            "top_competing_domains": [{"domain": d, "citations": n} for d, n in top],
            "results": bucket["results"],
        }

    overall_n = sum(len(questions) - per_engine[e]["errors"] for e in selected)
    overall_cited = sum(per_engine[e]["questions_with_target_cited"] for e in selected)
    return {
        "target_domain": target,
        "engines_queried": selected,
        "questions_asked": len(questions),
        "overall_citation_share": (overall_cited / overall_n) if overall_n else 0.0,
        "by_engine": summary,
    }


def _normalize_domain(host: str) -> str:
    host = host.strip().lower()
    if host.startswith(("http://", "https://")):
        from urllib.parse import urlparse

        host = urlparse(host).netloc
    return host[4:] if host.startswith("www.") else host
