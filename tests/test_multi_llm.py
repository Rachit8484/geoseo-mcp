"""multi_citation_check logic, with fake engines (no network)."""

from __future__ import annotations

import itertools
import threading
import time

import pytest

from geoseo_mcp.engines import multi_llm
from geoseo_mcp.engines.base import EngineError, EngineNotConfiguredError


def _answer(text: str, *urls: str) -> dict:
    from geoseo_mcp.engines._domains import domain_of

    return {
        "answer": text,
        "citations": list(urls),
        "cited_domains": sorted({domain_of(u) for u in urls}),
    }


def _install(monkeypatch: pytest.MonkeyPatch, engines: dict) -> None:
    monkeypatch.setattr(multi_llm, "_engines_available", lambda: engines)


def test_no_engines_configured() -> None:
    with pytest.raises(EngineNotConfiguredError):
        multi_llm.multi_citation_check(["q"], "example.com")


def test_unknown_engine_selection(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch, {"openai": lambda q: _answer("x")})
    with pytest.raises(EngineError):
        multi_llm.multi_citation_check(["q"], "example.com", engines=["gemini"])


def test_samples_rates_and_subdomains(monkeypatch: pytest.MonkeyPatch) -> None:
    # Cites a subdomain on 2 of 3 runs; the 3rd run only mentions the brand.
    cycle = itertools.cycle(
        [
            _answer("See the docs.", "https://docs.example.com/a", "https://rival.io/x"),
            _answer("Example is good.", "https://www.example.com/"),
            _answer("Example is one option, rival.io is another.", "https://rival.io/y"),
        ]
    )
    lock = threading.Lock()

    def fake(q: str) -> dict:
        with lock:
            return next(cycle)

    _install(monkeypatch, {"openai": fake})
    res = multi_llm.multi_citation_check(
        ["best tool?"], "https://example.com", samples=3, max_concurrency=1
    )
    eng = res["by_engine"]["openai"]
    assert res["target_domain"] == "example.com"
    assert res["samples_per_question"] == 3
    assert eng["answers_ok"] == 3
    assert eng["citation_rate"] == pytest.approx(2 / 3, abs=1e-3)
    assert eng["mention_rate"] == pytest.approx(2 / 3, abs=1e-3)
    assert eng["unlinked_mention_rate"] == pytest.approx(1 / 3, abs=1e-3)
    lo, hi = eng["citation_rate_ci95"]
    assert 0 < lo < 2 / 3 < hi <= 1
    q = eng["results"][0]
    assert q["cited"] is True and q["stable"] is False
    assert eng["unstable_questions"] == 1
    assert eng["top_competing_domains"][0] == {"domain": "rival.io", "citations": 2}
    assert res["overall_visibility_rate"] == 1.0
    # Backwards-compatible keys are still there.
    assert eng["questions_with_target_cited"] == 1
    assert "overall_citation_share" in res


def test_brand_aliases_detect_unlinked_mentions(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch, {"claude": lambda q: _answer("Try SoberPath for that.", "https://x.com")})
    res = multi_llm.multi_citation_check(
        ["q1", "q2"], "getsoberpath.app", samples=1, brand_aliases=["SoberPath"]
    )
    eng = res["by_engine"]["claude"]
    assert eng["citation_rate"] == 0
    assert eng["mention_rate"] == 1.0
    assert eng["unlinked_mention_rate"] == 1.0


def test_errors_are_isolated(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(q: str) -> dict:
        raise EngineError("rate limited")

    _install(monkeypatch, {"good": lambda q: _answer("", "https://example.com"), "bad": boom})
    res = multi_llm.multi_citation_check(["q"], "example.com", samples=2)
    assert res["by_engine"]["good"]["citation_rate"] == 1.0
    bad = res["by_engine"]["bad"]
    assert bad["answers_ok"] == 0 and bad["answers_errored"] == 2
    assert bad["results"][0]["errors"] == ["rate limited", "rate limited"]
    assert bad["results"][0]["cited"] is False
    assert res["overall_citation_rate"] == 1.0


def test_variance_across_questions(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake(q: str) -> dict:
        return _answer("", "https://example.com") if q == "yes" else _answer("")

    _install(monkeypatch, {"e": fake})
    res = multi_llm.multi_citation_check(["yes", "no"], "example.com", samples=2)
    eng = res["by_engine"]["e"]
    assert eng["citation_share"] == 0.5
    assert eng["question_rate_variance"] == 0.25


def test_concurrency_is_capped(monkeypatch: pytest.MonkeyPatch) -> None:
    active = peak = 0
    lock = threading.Lock()

    def slow(q: str) -> dict:
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        time.sleep(0.02)
        with lock:
            active -= 1
        return _answer("")

    _install(monkeypatch, {"a": slow, "b": slow})
    multi_llm.multi_citation_check(["q1", "q2", "q3"], "example.com", samples=3, max_concurrency=3)
    assert 1 < peak <= 3


def test_samples_are_clamped(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []
    _install(monkeypatch, {"a": lambda q: calls.append(q) or _answer("")})
    res = multi_llm.multi_citation_check(["q"], "example.com", samples=999)
    assert res["samples_per_question"] == multi_llm.MAX_SAMPLES
    assert len(calls) == multi_llm.MAX_SAMPLES


def test_wilson_interval_edges() -> None:
    assert multi_llm.wilson_interval(0, 0) == (0.0, 0.0)
    lo, hi = multi_llm.wilson_interval(0, 10)
    assert lo == 0.0 and 0 < hi < 0.35
    lo, hi = multi_llm.wilson_interval(10, 10)
    assert hi == 1.0 and lo > 0.65
