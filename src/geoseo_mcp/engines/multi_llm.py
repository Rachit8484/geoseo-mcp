"""Cross-engine helpers.

Every LLM engine returns the same shape
(``{question, answer, citations, cited_domains, ...}``), so the citation logic
lives here once and runs against any subset of configured engines.

LLM answers are not deterministic: the same question can cite you on one run
and not the next. ``multi_citation_check`` therefore asks each question
``samples`` times per engine and reports rates (plus a confidence interval)
instead of a single yes/no.
"""

from __future__ import annotations

import concurrent.futures as cf
import math
from collections.abc import Callable
from typing import Any

from ..config import get_config
from . import anthropic, gemini, grok, openai, perplexity
from ._domains import (
    any_match,
    default_aliases,
    find_mentions,
    matches_domain,
    normalize_domain,
)
from .base import EngineError, EngineNotConfiguredError

EngineFn = Callable[[str], dict[str, Any]]

MAX_SAMPLES = 10
DEFAULT_CONCURRENCY = 8


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
    if cfg.grok_api_key:
        out["grok"] = lambda q: grok.query(q)
    return out


def list_configured_engines() -> list[str]:
    return sorted(_engines_available().keys())


def _select(engines: list[str] | None) -> dict[str, EngineFn]:
    available = _engines_available()
    if not available:
        raise EngineNotConfiguredError(
            "any LLM",
            "No LLM engines configured. Set at least one of "
            "GEOSEO_PERPLEXITY_API_KEY, GEOSEO_OPENAI_API_KEY, "
            "GEOSEO_ANTHROPIC_API_KEY, GEOSEO_GEMINI_API_KEY, or GEOSEO_XAI_API_KEY.",
        )
    selected = {name: fn for name, fn in available.items() if not engines or name in engines}
    if not selected:
        raise EngineError(f"No requested engines are configured. Available: {sorted(available)}")
    return selected


def _safe_call(name: str, fn: EngineFn, question: str) -> dict[str, Any]:
    try:
        return fn(question)
    except (EngineNotConfiguredError, EngineError) as e:
        return {"engine": name, "error": str(e)}
    except Exception as e:  # never let one engine take down the batch
        return {"engine": name, "error": f"unexpected: {e}"}


def multi_query(question: str, engines: list[str] | None = None) -> dict[str, Any]:
    """Ask the same question to every configured (or selected) engine in parallel."""
    selected = _select(engines)
    results: dict[str, Any] = {}
    with cf.ThreadPoolExecutor(max_workers=len(selected)) as pool:
        futures = {pool.submit(_safe_call, n, fn, question): n for n, fn in selected.items()}
        for fut in cf.as_completed(futures):
            results[futures[fut]] = fut.result()
    return {"question": question, "engines_queried": sorted(selected.keys()), "results": results}


def wilson_interval(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score interval. Behaves sensibly for small n and p near 0/1."""
    if n == 0:
        return (0.0, 0.0)
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return (round(max(0.0, centre - half), 4), round(min(1.0, centre + half), 4))


def _rate(k: int, n: int) -> float:
    return round(k / n, 4) if n else 0.0


def multi_citation_check(
    questions: list[str],
    target_domain: str,
    engines: list[str] | None = None,
    samples: int = 3,
    brand_aliases: list[str] | None = None,
    max_concurrency: int = DEFAULT_CONCURRENCY,
) -> dict[str, Any]:
    """Citation + mention metrics for ``target_domain`` across configured LLMs.

    - Each question is asked ``samples`` times per engine (1-10).
    - A citation counts if any cited URL is on ``target_domain`` or a subdomain.
    - A *mention* counts if the answer text names the brand/domain (or any of
      ``brand_aliases``) even without a link. ``unlinked_mention_rate`` is the
      share of answers that mention you but don't cite you: an easy PR win.
    - Calls run concurrently, capped at ``max_concurrency`` in flight.
    """
    target = normalize_domain(target_domain)
    if not target:
        raise EngineError("target_domain is empty")
    samples = max(1, min(int(samples), MAX_SAMPLES))
    max_concurrency = max(1, int(max_concurrency))
    aliases = default_aliases(target, brand_aliases)
    selected = _select(engines)

    jobs = [(e, qi, s) for e in selected for qi in range(len(questions)) for s in range(samples)]
    raw: dict[tuple[str, int], list[dict[str, Any]]] = {}
    with cf.ThreadPoolExecutor(max_workers=min(max_concurrency, max(1, len(jobs)))) as pool:
        futures = {
            pool.submit(_safe_call, e, selected[e], questions[qi]): (e, qi) for e, qi, _ in jobs
        }
        for fut in cf.as_completed(futures):
            raw.setdefault(futures[fut], []).append(fut.result())

    by_engine: dict[str, Any] = {}
    tot_ok = tot_cited = tot_mentioned = tot_visible = 0
    for engine in selected:
        ok = cited_n = mentioned_n = unlinked_n = errors = 0
        competitors: dict[str, int] = {}
        per_question: list[dict[str, Any]] = []
        question_rates: list[float] = []
        for qi, q in enumerate(questions):
            runs = raw.get((engine, qi), [])
            q_ok = q_cited = q_mentioned = 0
            domains: set[str] = set()
            excerpt = ""
            q_errors: list[str] = []
            for res in runs:
                if "error" in res:
                    q_errors.append(res["error"])
                    continue
                q_ok += 1
                cds = res.get("cited_domains") or []
                is_cited = any_match(cds, target)
                mentions = find_mentions(res.get("answer") or "", aliases)
                q_cited += is_cited
                q_mentioned += bool(mentions)
                unlinked_n += bool(mentions) and not is_cited
                domains.update(cds)
                for d in set(cds):
                    if not matches_domain(d, target):
                        competitors[d] = competitors.get(d, 0) + 1
                if not excerpt:
                    excerpt = (res.get("answer") or "")[:280]
            ok += q_ok
            cited_n += q_cited
            mentioned_n += q_mentioned
            errors += len(q_errors)
            rate = _rate(q_cited, q_ok)
            if q_ok:
                question_rates.append(rate)
            entry: dict[str, Any] = {
                "question": q,
                "samples_ok": q_ok,
                "cited_rate": rate,
                "mention_rate": _rate(q_mentioned, q_ok),
                # Majority vote, kept for trend snapshots and older clients.
                "cited": q_ok > 0 and rate >= 0.5,
                "stable": q_ok > 0 and q_cited in (0, q_ok),
                "cited_domains": sorted(domains),
                "answer_excerpt": excerpt,
            }
            if q_errors:
                entry["errors"] = q_errors[:3]
            per_question.append(entry)

        mean_q = sum(question_rates) / len(question_rates) if question_rates else 0.0
        var_q = (
            sum((r - mean_q) ** 2 for r in question_rates) / len(question_rates)
            if question_rates
            else 0.0
        )
        top = sorted(competitors.items(), key=lambda kv: kv[1], reverse=True)[:10]
        by_engine[engine] = {
            "questions_asked": len(questions),
            "samples_per_question": samples,
            "answers_ok": ok,
            "answers_errored": errors,
            "citation_rate": _rate(cited_n, ok),
            "citation_rate_ci95": wilson_interval(cited_n, ok),
            "mention_rate": _rate(mentioned_n, ok),
            "unlinked_mention_rate": _rate(unlinked_n, ok),
            "question_rate_variance": round(var_q, 4),
            "unstable_questions": sum(1 for p in per_question if p["samples_ok"] and not p["stable"]),
            # Backwards-compatible fields from v0.3.
            "questions_with_target_cited": sum(1 for p in per_question if p["cited"]),
            "citation_share": round(mean_q, 4),
            "top_competing_domains": [{"domain": d, "citations": n} for d, n in top],
            "results": per_question,
        }
        tot_ok += ok
        tot_cited += cited_n
        tot_mentioned += mentioned_n
        tot_visible += sum(
            1
            for qi in range(len(questions))
            for r in raw.get((engine, qi), [])
            if "error" not in r
            and (
                any_match(r.get("cited_domains") or [], target)
                or find_mentions(r.get("answer") or "", aliases)
            )
        )

    return {
        "target_domain": target,
        "brand_aliases": aliases,
        "engines_queried": sorted(selected),
        "questions_asked": len(questions),
        "samples_per_question": samples,
        "overall_citation_rate": _rate(tot_cited, tot_ok),
        "overall_citation_rate_ci95": wilson_interval(tot_cited, tot_ok),
        "overall_mention_rate": _rate(tot_mentioned, tot_ok),
        "overall_visibility_rate": _rate(tot_visible, tot_ok),
        "overall_citation_share": _rate(tot_cited, tot_ok),
        "by_engine": by_engine,
    }
