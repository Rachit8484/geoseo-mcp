"""LLM-citation tools (v0.1: Perplexity)."""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from ..engines import perplexity
from ..engines.base import EngineError, EngineNotConfiguredError


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def perplexity_query(
        question: str,
        model: str | None = None,
        system_prompt: str | None = None,
        max_tokens: int = 1024,
    ) -> dict[str, Any]:
        """Ask Perplexity a question and return the answer plus cited URLs/domains.

        Use this to see what Perplexity's answer engine currently surfaces for a
        target query. ``model`` defaults to ``GEOSEO_PERPLEXITY_MODEL`` (``sonar``).
        """
        try:
            return perplexity.query(
                question=question, model=model, system_prompt=system_prompt,
                max_tokens=max_tokens,
            )
        except (EngineNotConfiguredError, EngineError) as e:
            return {"error": str(e)}

    @mcp.tool()
    def perplexity_citation_check(
        questions: list[str],
        target_domain: str,
        model: str | None = None,
    ) -> dict[str, Any]:
        """Run a list of questions against Perplexity and report citation share for ``target_domain``.

        Returns:
            - ``citation_share``: fraction of questions where ``target_domain`` was cited.
            - ``top_competing_domains``: most-cited other domains across the run.
            - ``results``: per-question detail (cited yes/no + cited domains + answer excerpt).

        This is your "rank tracker for AI search". Run it weekly to see drift.
        """
        try:
            return perplexity.citation_check(
                questions=questions, target_domain=target_domain, model=model,
            )
        except (EngineNotConfiguredError, EngineError) as e:
            return {"error": str(e)}
