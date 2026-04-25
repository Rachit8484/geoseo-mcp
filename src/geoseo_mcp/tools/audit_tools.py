"""On-page + on-folder audit tools, plus llms.txt generator/validator."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastmcp import FastMCP

from ..audit import llms_txt, on_page


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def audit_page(source: str) -> dict[str, Any]:
        """Audit a single page (local file path or http(s) URL).

        Returns a structured report with: title/meta/headings, word count,
        link counts, image alt coverage, JSON-LD schema types, Open Graph,
        Twitter Card, freshness signals, GEO-quotability score, and a list
        of human-readable findings. Plus a 0-100 overall ``score``.

        Examples:
            ``audit_page("seo/aa-meetings-what-to-expect.html")``
            ``audit_page("https://soberpath.com/blog/quit-drinking")``
        """
        try:
            return on_page.audit(source)
        except FileNotFoundError as e:
            return {"error": str(e)}
        except Exception as e:
            return {"error": f"audit failed: {e}"}

    @mcp.tool()
    def audit_site(folder: str, pattern: str = "*.html", limit: int = 200) -> dict[str, Any]:
        """Recursively audit every HTML file under a folder.

        Returns per-file scores, an aggregate summary (mean score, worst pages,
        most common findings), and the top opportunities for improvement.

        Useful as the first call against a content directory to spot the worst
        offenders quickly.
        """
        root = Path(folder).expanduser().resolve()
        if not root.exists():
            return {"error": f"No such folder: {root}"}

        files = sorted(root.rglob(pattern))[:limit]
        if not files:
            return {"error": f"No files matching {pattern} under {root}"}

        per_file: list[dict[str, Any]] = []
        finding_tally: dict[str, int] = {}
        for f in files:
            try:
                report = on_page.audit(str(f))
            except Exception as e:
                per_file.append({"path": str(f), "error": str(e)})
                continue
            per_file.append(
                {
                    "path": str(f),
                    "score": report["score"],
                    "title": report["title"],
                    "word_count": report["word_count"],
                    "warnings": [x["key"] for x in report["findings"] if not x["ok"]],
                }
            )
            for finding in report["findings"]:
                if not finding["ok"]:
                    finding_tally[finding["key"]] = finding_tally.get(finding["key"], 0) + 1

        scored = [p for p in per_file if "score" in p]
        mean_score = sum(p["score"] for p in scored) / len(scored) if scored else 0.0
        worst = sorted(scored, key=lambda p: p["score"])[:10]
        top_findings = sorted(finding_tally.items(), key=lambda kv: kv[1], reverse=True)

        return {
            "folder": str(root),
            "files_audited": len(per_file),
            "mean_score": round(mean_score, 1),
            "worst_pages": worst,
            "most_common_findings": [{"key": k, "count": n} for k, n in top_findings],
            "per_file": per_file,
        }

    @mcp.tool()
    def generate_llms_txt(
        folder: str,
        site_url: str,
        site_title: str | None = None,
        site_summary: str | None = None,
        pattern: str = "*.html",
        section_strategy: str = "first_path_segment",
        limit: int = 1000,
    ) -> dict[str, Any]:
        """Generate a draft ``llms.txt`` from a folder of HTML pages.

        ``llms.txt`` (https://llmstxt.org) is the emerging standard for telling
        LLM crawlers where your canonical content lives. This tool reads each
        page's ``<title>`` and meta description, groups by URL prefix, and
        produces spec-compliant Markdown ready to drop at ``/llms.txt``.

        ``section_strategy`` controls grouping:
            - ``first_path_segment`` (default): groups by first URL path
              segment, e.g. all ``/blog/...`` pages under "Blog".
            - ``flat``: a single "Pages" section.
        """
        return llms_txt.generate(
            folder=folder, site_url=site_url, site_title=site_title,
            site_summary=site_summary, pattern=pattern,
            section_strategy=section_strategy, limit=limit,
        )

    @mcp.tool()
    def validate_llms_txt(source: str) -> dict[str, Any]:
        """Validate an ``llms.txt`` file (local path or URL) against the spec.

        Returns parsed structure plus an ``issues`` list with line numbers for
        any violations (missing H1, broken link syntax, non-http(s) URLs, etc).
        """
        try:
            return llms_txt.validate(source)
        except FileNotFoundError as e:
            return {"error": str(e)}
        except Exception as e:
            return {"error": f"validate failed: {e}"}
