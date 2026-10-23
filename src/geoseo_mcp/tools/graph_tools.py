"""Internal-link-graph tools."""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from ..graph import internal_links


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def internal_link_graph(
        folder: str,
        pattern: str = "*.html",
        limit: int = 1000,
        site_host: str | None = None,
    ) -> dict[str, Any]:
        """Audit a folder of HTML pages as a directed internal-link graph.

        Returns counts of files/edges, the orphans (no inbound links),
        dead-ends (no outbound links), top hub pages, and a list of
        dangling internal hrefs that don't resolve to any file.

        Pass ``site_host`` (e.g. ``"example.com"``) if pages link to
        themselves with absolute URLs — those will then count as internal
        edges. Files are also matched by URL slug, so ``/blog/foo``
        resolves to ``foo.html`` even when paths don't match exactly.
        """
        result = internal_links.build(
            folder=folder, pattern=pattern, limit=limit, site_host=site_host,
        )
        result.pop("_feats", None)
        result.pop("_edges", None)
        return result

    @mcp.tool()
    def suggest_internal_links(
        folder: str,
        page: str | None = None,
        pattern: str = "*.html",
        top_k: int = 5,
        limit: int = 1000,
        site_host: str | None = None,
        mode: str = "tfidf",
        model: str | None = None,
    ) -> dict[str, Any]:
        """Suggest top-K internal links to add to each page in a folder.

        By default uses TF-IDF cosine similarity over ``<title>``, headings,
        meta description and body text (offline, free). Set ``mode`` to
        ``"openai"`` (text-embedding-3-small), ``"gemini"``
        (gemini-embedding-001) or ``"local"`` (sentence-transformers) for
        embedding similarity; ``model`` overrides the default model. Vectors
        are cached in SQLite by content hash, so re-runs are cheap. Excludes links the source already has, plus
        the page itself. Returns suggestions for ``page`` only if
        provided, otherwise for every page.

        Each suggestion includes a cheap ``anchor_hint`` derived from
        terms shared between source headings and target title.
        """
        return internal_links.suggest(
            folder=folder, page=page, pattern=pattern, top_k=top_k, limit=limit,
            site_host=site_host, mode=mode, model=model,
        )
