"""LLM-citation tools.

v0.1: Perplexity. v0.2: + ChatGPT (OpenAI), Claude (Anthropic), Gemini, plus
``multi_llm_*`` tools that fan out across every configured engine in parallel.
"""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from ..engines import anthropic, gemini, multi_llm, openai, perplexity
from ..engines.base import EngineError, EngineNotConfiguredError


def register(mcp: FastMCP) -> None:
    # --- Perplexity ----------------------------------------------------------
    @mcp.tool()
    def perplexity_query(
        question: str,
        model: str | None = None,
        system_prompt: str | None = None,
        max_tokens: int = 1024,
    ) -> dict[str, Any]:
        """Ask Perplexity a question; return answer + cited URLs/domains."""
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

        Uses the OpenAI Responses API with the ``web_search_preview`` tool.
        Default model: ``GEOSEO_OPENAI_MODEL`` (``gpt-4o-mini``).
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

    # --- Multi-engine --------------------------------------------------------
    @mcp.tool()
    def multi_llm_query(
        question: str, engines: list[str] | None = None,
    ) -> dict[str, Any]:
        """Ask the same question to all (or selected) configured LLM engines in parallel.

        ``engines``: optional subset of ``["perplexity","openai","anthropic","gemini"]``.
        Default: every engine with credentials configured (see ``geoseo_status``).
        Engines that error are reported per-engine and don't block the others.
        """
        try:
            return multi_llm.multi_query(question=question, engines=engines)
        except (EngineNotConfiguredError, EngineError) as e:
            return {"error": str(e)}

    @mcp.tool()
    def multi_llm_citation_check(
        questions: list[str], target_domain: str, engines: list[str] | None = None,
    ) -> dict[str, Any]:
        """Citation-share metrics for ``target_domain`` across every configured LLM.

        This is the headline GEO/AEO tool: feed it your top 20-50 user questions,
        get a per-engine breakdown of how often ChatGPT/Claude/Gemini/Perplexity
        cite your domain, plus the top competing domains per engine. Run weekly
        and diff to track AI-search visibility over time.
        """
        try:
            return multi_llm.multi_citation_check(
                questions=questions, target_domain=target_domain, engines=engines,
            )
        except (EngineNotConfiguredError, EngineError) as e:
            return {"error": str(e)}

    @mcp.tool()
    def list_llm_engines() -> dict[str, Any]:
        """Return the LLM engines currently configured (have an API key)."""
        return {"configured": multi_llm.list_configured_engines()}
