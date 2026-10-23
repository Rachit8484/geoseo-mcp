"""LLM-citation tools.

v0.1: Perplexity. v0.2: + ChatGPT (OpenAI), Claude (Anthropic), Gemini, plus
``multi_llm_*`` tools that fan out across every configured engine in parallel.
"""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from ..engines import anthropic, gemini, grok, multi_llm, openai, perplexity
from ..engines.base import EngineError, EngineNotConfiguredError


def register(mcp: FastMCP) -> None:
    # --- Perplexity ----------------------------------------------------------
    @mcp.tool()
    def perplexity_query(
        question: str,
        model: str | None = None,
        system_prompt: str | None = None,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        """Ask Perplexity (Agent API + web search); return answer + cited URLs/domains.

        Defaults to the ``fast`` effort preset. Pass ``model`` to pin one
        (e.g. ``openai/gpt-5-mini``); legacy names like ``sonar`` still work.
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
        questions: list[str], target_domain: str, model: str | None = None,
    ) -> dict[str, Any]:
        """Citation share for ``target_domain`` across a Perplexity question batch."""
        try:
            return perplexity.citation_check(
                questions=questions, target_domain=target_domain, model=model,
            )
        except (EngineNotConfiguredError, EngineError) as e:
            return {"error": str(e)}

    # --- OpenAI / ChatGPT ----------------------------------------------------
    @mcp.tool()
    def openai_query(
        question: str, model: str | None = None, system_prompt: str | None = None,
    ) -> dict[str, Any]:
        """Ask ChatGPT (with web search) a question; return answer + cited URLs.

        Uses the OpenAI Responses API with the ``web_search`` tool.
        Default model: ``GEOSEO_OPENAI_MODEL`` (``gpt-5-mini``).
        """
        try:
            return openai.query(question=question, model=model, system_prompt=system_prompt)
        except (EngineNotConfiguredError, EngineError) as e:
            return {"error": str(e)}

    # --- Anthropic / Claude --------------------------------------------------
    @mcp.tool()
    def claude_query(
        question: str, model: str | None = None, system_prompt: str | None = None,
        max_tokens: int = 1024,
    ) -> dict[str, Any]:
        """Ask Claude (with server-side web search) a question; return answer + cited URLs."""
        try:
            return anthropic.query(
                question=question, model=model, system_prompt=system_prompt,
                max_tokens=max_tokens,
            )
        except (EngineNotConfiguredError, EngineError) as e:
            return {"error": str(e)}

    # --- Google Gemini -------------------------------------------------------
    @mcp.tool()
    def gemini_query(
        question: str, model: str | None = None, system_prompt: str | None = None,
    ) -> dict[str, Any]:
        """Ask Gemini (with Google Search grounding) a question; return answer + cited URLs.

        Grounding sources here are the same signal Google uses for AI Overviews,
        so this is the closest open-API proxy for "what AIO might cite for this query".
        """
        try:
            return gemini.query(question=question, model=model, system_prompt=system_prompt)
        except (EngineNotConfiguredError, EngineError) as e:
            return {"error": str(e)}

    # --- xAI Grok -----------------------------------------------------------
    @mcp.tool()
    def grok_query(
        question: str, model: str | None = None, system_prompt: str | None = None,
        x_search: bool = False,
    ) -> dict[str, Any]:
        """Ask Grok (with live web search) a question; return answer + cited URLs.

        Uses the xAI Responses API with the ``web_search`` tool. ``citations``
        are the URLs Grok actually cites inline; ``sources_considered`` lists
        everything it looked at. Set ``x_search=True`` to also search X posts.
        Default model: ``GEOSEO_GROK_MODEL`` (``grok-4.3``).
        """
        try:
            return grok.query(
                question=question, model=model, system_prompt=system_prompt,
                x_search=x_search,
            )
        except (EngineNotConfiguredError, EngineError) as e:
            return {"error": str(e)}

    # --- Multi-engine --------------------------------------------------------
    @mcp.tool()
    def multi_llm_query(
        question: str, engines: list[str] | None = None,
    ) -> dict[str, Any]:
        """Ask the same question to all (or selected) configured LLM engines in parallel.

        ``engines``: optional subset of ``["perplexity","openai","anthropic","gemini","grok"]``.
        Default: every engine with credentials configured (see ``geoseo_status``).
        Engines that error are reported per-engine and don't block the others.
        """
        try:
            return multi_llm.multi_query(question=question, engines=engines)
        except (EngineNotConfiguredError, EngineError) as e:
            return {"error": str(e)}

    @mcp.tool()
    def multi_llm_citation_check(
        questions: list[str],
        target_domain: str,
        engines: list[str] | None = None,
        samples: int | None = None,
        brand_aliases: list[str] | None = None,
        max_concurrency: int | None = None,
    ) -> dict[str, Any]:
        """How often each configured LLM cites (or mentions) ``target_domain``.

        The headline GEO/AEO tool. Feed it your top 20-50 buyer questions and get
        a per-engine breakdown for ChatGPT/Claude/Gemini/Perplexity/Grok:

        - ``citation_rate`` (+ 95% interval): share of answers linking to your
          domain or any subdomain of it.
        - ``mention_rate`` / ``unlinked_mention_rate``: answers that name your
          brand, with or without a link. Pass ``brand_aliases`` (e.g.
          ``["Acme", "Acme CRM"]``) if your brand isn't obvious from the domain.
        - ``top_competing_domains`` and per-question results.

        LLM answers vary run to run, so every question is asked ``samples``
        times per engine (default ``GEOSEO_CITATION_SAMPLES``, 3; max 10).
        Cost scales with questions x samples x engines.
        """
        from ..config import get_config

        cfg = get_config()
        try:
            return multi_llm.multi_citation_check(
                questions=questions,
                target_domain=target_domain,
                engines=engines,
                samples=samples or cfg.citation_samples,
                brand_aliases=brand_aliases,
                max_concurrency=max_concurrency or cfg.max_concurrency,
            )
        except (EngineNotConfiguredError, EngineError) as e:
            return {"error": str(e)}

    @mcp.tool()
    def list_llm_engines() -> dict[str, Any]:
        """Return the LLM engines currently configured (have an API key)."""
        return {"configured": multi_llm.list_configured_engines()}
