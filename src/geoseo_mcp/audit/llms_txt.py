"""``llms.txt`` generator + validator.

``llms.txt`` is the emerging standard (https://llmstxt.org) for telling LLM
crawlers where the canonical content of a site lives, in a curated form. It
sits at ``/llms.txt`` and uses a Markdown-flavored format.

This module:

1. **Generates** a draft ``llms.txt`` from a folder of HTML pages, grouping
   by URL path prefix, using each page's ``<title>`` and meta description.
2. **Validates** an existing ``llms.txt`` (or a URL) against the spec
   skeleton: H1 title, optional summary blockquote, sections of links.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from ..config import get_config

_LINK_RE = re.compile(r"^\s*-\s*\[([^\]]+)\]\(([^)]+)\)\s*(?::\s*(.+))?$")


@dataclass
class GeneratedLlmsTxt:
    site_title: str
    site_summary: str | None
    sections: dict[str, list[dict[str, str]]] = field(default_factory=dict)

    def render(self) -> str:
        lines = [f"# {self.site_title}", ""]
        if self.site_summary:
            lines.append(f"> {self.site_summary}")
            lines.append("")
        for section, items in self.sections.items():
            lines.append(f"## {section}")
            lines.append("")
            for it in items:
                desc = f": {it['description']}" if it.get("description") else ""
                lines.append(f"- [{it['title']}]({it['url']}){desc}")
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"


def generate(
    folder: str,
    site_url: str,
    site_title: str | None = None,
    site_summary: str | None = None,
    pattern: str = "*.html",
    section_strategy: str = "first_path_segment",
    limit: int = 1000,
) -> dict[str, Any]:
    """Generate an ``llms.txt`` draft from a folder of HTML files.

    Args:
        folder: Path to the directory containing your published HTML.
        site_url: Canonical site root, e.g. ``https://example.com``.
        site_title: Override the H1 title; defaults to the folder name.
        site_summary: Optional one-paragraph blockquote summary.
        pattern: Glob pattern for HTML files. Defaults to ``*.html``.
        section_strategy: How to group entries. ``first_path_segment``
            groups by URL path prefix; ``flat`` puts everything under
            "Pages".
        limit: Max files to process.

    Returns:
        Dict with ``content`` (the rendered llms.txt), ``entry_count``,
        ``sections``, and ``warnings``.
    """
    root = Path(folder).expanduser().resolve()
    if not root.exists():
        return {"error": f"No such folder: {root}"}
    files = sorted(root.rglob(pattern))[:limit]
    if not files:
        return {"error": f"No files matching {pattern} under {root}"}

    site_url = site_url.rstrip("/")
    sections: dict[str, list[dict[str, str]]] = {}
    warnings: list[str] = []

    for f in files:
        rel = f.relative_to(root).with_suffix("").as_posix()
        if rel.endswith("/index"):
            rel = rel[: -len("/index")]
        url = f"{site_url}/{rel}" if rel else site_url

        try:
            soup = BeautifulSoup(f.read_text(encoding="utf-8", errors="replace"), "lxml")
        except Exception as e:
            warnings.append(f"{f.name}: parse failed ({e})")
            continue

        title = (soup.title.string or "").strip() if soup.title else ""
        if not title:
            warnings.append(f"{f.name}: no <title>")
            title = f.stem.replace("-", " ").title()

        meta = soup.find("meta", attrs={"name": "description"})
        desc = (meta["content"].strip() if meta and meta.get("content") else "")

        section = _section_for(rel, section_strategy)
        sections.setdefault(section, []).append(
            {"title": title, "url": url, "description": desc}
        )

    out = GeneratedLlmsTxt(
        site_title=site_title or root.name,
        site_summary=site_summary,
        sections=dict(sorted(sections.items())),
    )
    rendered = out.render()
    return {
        "content": rendered,
        "entry_count": sum(len(v) for v in out.sections.values()),
        "sections": {k: len(v) for k, v in out.sections.items()},
        "warnings": warnings,
        "suggested_path": str(root.parent / "llms.txt"),
    }


def _section_for(rel_path: str, strategy: str) -> str:
    if strategy == "flat":
        return "Pages"
    head = rel_path.split("/", 1)[0]
    if not head or head == rel_path:
        return "Pages"
    return head.replace("-", " ").title()


def validate(source: str) -> dict[str, Any]:
    """Validate an ``llms.txt`` (URL or local path) against the spec.

    Checks:
        - First non-empty line is an H1.
        - Optional ``> summary`` blockquote follows.
        - Subsequent ``## Section`` blocks contain valid Markdown link items.
        - All link URLs parse and use http(s).
    """
    text = _load(source)
    lines = text.splitlines()
    issues: list[dict[str, str]] = []

    title: str | None = None
    summary: str | None = None
    sections: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    seen_summary = False

    for i, raw in enumerate(lines, 1):
        line = raw.rstrip()
        if not line.strip():
            continue
        if title is None:
            if line.startswith("# "):
                title = line[2:].strip()
            else:
                issues.append({"line": str(i), "message": "First line must be H1 (`# Title`)"})
            continue
        if line.startswith("# "):
            issues.append({"line": str(i), "message": "Multiple H1 headings"})
            continue
        if line.startswith("> ") and not seen_summary and current is None:
            summary = (summary + " " + line[2:].strip()).strip() if summary else line[2:].strip()
            continue
        if summary and not line.startswith("> "):
            seen_summary = True
        if line.startswith("## "):
            current = {"name": line[3:].strip(), "items": []}
            sections.append(current)
            continue
        m = _LINK_RE.match(line)
        if m:
            label, url, desc = m.group(1), m.group(2), m.group(3)
            scheme = urlparse(url).scheme
            if scheme not in {"http", "https"}:
                issues.append({"line": str(i), "message": f"Non-http(s) URL: {url}"})
            if current is None:
                issues.append({"line": str(i), "message": "Link before any `## Section`"})
            else:
                current["items"].append({"label": label, "url": url, "description": desc or ""})
            continue
        issues.append({"line": str(i), "message": f"Unrecognized syntax: {line!r}"})

    return {
        "source": source,
        "ok": title is not None and not issues,
        "title": title,
        "summary": summary,
        "section_count": len(sections),
        "link_count": sum(len(s["items"]) for s in sections),
        "sections": sections,
        "issues": issues,
    }


def _load(source: str) -> str:
    if source.startswith(("http://", "https://")):
        cfg = get_config()
        with httpx.Client(timeout=cfg.request_timeout_s, follow_redirects=True) as c:
            r = c.get(source, headers={"User-Agent": cfg.user_agent})
            r.raise_for_status()
            return r.text
    p = Path(source).expanduser().resolve()
    if not p.exists():
        raise FileNotFoundError(f"No such file: {p}")
    return p.read_text(encoding="utf-8", errors="replace")


__all__ = ["generate", "validate", "GeneratedLlmsTxt"]
# Use urljoin to silence unused-import lint while keeping it available for
# future relative-link resolution.
_ = urljoin
