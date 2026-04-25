"""Static on-page SEO + GEO audit.

Inputs: a local file path or a live URL. Output: a structured findings dict
that is stable and JSON-serializable so MCP clients can render it cleanly.

Heuristics intentionally kept conservative; we report facts and let the LLM
synthesize advice. The single opinionated bit is the ``score`` (0-100), a
weighted sum of widely-accepted on-page signals plus GEO citation-readiness.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from ..config import get_config

_WORD_RE = re.compile(r"\b\w+\b", flags=re.UNICODE)


@dataclass
class PageAudit:
    source: str
    url: str | None
    title: str | None
    title_length: int
    meta_description: str | None
    meta_description_length: int
    canonical: str | None
    robots: str | None
    lang: str | None
    h1: list[str]
    h2: list[str]
    h3: list[str]
    word_count: int
    internal_links: int
    external_links: int
    images: int
    images_missing_alt: int
    schema_types: list[str]
    schema_blocks: int
    open_graph: dict[str, str]
    twitter_card: dict[str, str]
    has_faq_schema: bool
    has_article_schema: bool
    has_author: bool
    has_published_date: bool
    quotable_sentences: int
    score: int
    findings: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def audit(source: str) -> dict[str, Any]:
    """Audit a local file path or HTTP(S) URL."""
    html, url = _load(source)
    return _audit_html(html, source=source, url=url).to_dict()


def _load(source: str) -> tuple[str, str | None]:
    if source.startswith(("http://", "https://")):
        cfg = get_config()
        with httpx.Client(timeout=cfg.request_timeout_s, follow_redirects=True) as c:
            r = c.get(source, headers={"User-Agent": cfg.user_agent})
            r.raise_for_status()
            return r.text, str(r.url)
    p = Path(source).expanduser().resolve()
    if not p.exists():
        raise FileNotFoundError(f"No such file: {p}")
    return p.read_text(encoding="utf-8", errors="replace"), None


def _audit_html(html: str, source: str, url: str | None) -> PageAudit:
    soup = BeautifulSoup(html, "lxml")

    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else None

    meta_desc = _meta_content(soup, "description")
    canonical = _attr(soup.find("link", rel=lambda v: v and "canonical" in v), "href")
    robots = _meta_content(soup, "robots")
    lang = soup.html.get("lang") if soup.html else None

    h1 = [t.get_text(" ", strip=True) for t in soup.find_all("h1")]
    h2 = [t.get_text(" ", strip=True) for t in soup.find_all("h2")]
    h3 = [t.get_text(" ", strip=True) for t in soup.find_all("h3")]

    body_text = soup.get_text(" ", strip=True)
    word_count = len(_WORD_RE.findall(body_text))

    internal_links, external_links = _count_links(soup, base=url)
    images = soup.find_all("img")
    images_missing_alt = sum(1 for i in images if not (i.get("alt") or "").strip())

    schema_blocks, schema_types = _extract_jsonld(soup)
    og = {
        m.get("property", "")[3:]: m.get("content", "")
        for m in soup.find_all("meta", property=lambda v: v and v.startswith("og:"))
        if m.get("content")
    }
    tw = {
        m.get("name", "")[8:]: m.get("content", "")
        for m in soup.find_all("meta", attrs={"name": lambda v: v and v.startswith("twitter:")})
        if m.get("content")
    }

    has_faq = any(t.lower() == "faqpage" for t in schema_types)
    has_article = any(t.lower() in {"article", "newsarticle", "blogposting"} for t in schema_types)
    has_author = bool(soup.find(attrs={"rel": "author"})) or any(
        "author" in (t.lower() if isinstance(t, str) else "") for t in schema_types
    )
    has_published = bool(soup.find("time")) or any(
        k in html.lower() for k in ("datepublished", "article:published_time")
    )

    quotable = _count_quotable_sentences(body_text)

    findings: list[dict[str, Any]] = []
    _check(findings, title is not None and 10 <= (len(title or "")) <= 70,
           "title", "Title length should be 10-70 chars",
           detail=f"length={len(title or '')}")
    _check(findings, meta_desc is not None and 70 <= len(meta_desc or "") <= 160,
           "meta_description", "Meta description should be 70-160 chars",
           detail=f"length={len(meta_desc or '')}")
    _check(findings, len(h1) == 1, "h1", "Exactly one H1 expected", detail=f"found={len(h1)}")
    _check(findings, word_count >= 300, "word_count", "Pages under 300 words rarely rank or get cited",
           detail=f"words={word_count}")
    _check(findings, images_missing_alt == 0, "alt_text",
           "Some images are missing alt text",
           detail=f"missing={images_missing_alt}/{len(images)}")
    _check(findings, schema_blocks > 0, "schema",
           "No JSON-LD schema found; LLMs and Google use this heavily")
    _check(findings, canonical is not None, "canonical", "Missing canonical URL")
    _check(findings, og.get("title") and og.get("description"),
           "open_graph", "Missing core Open Graph tags (og:title, og:description)")
    _check(findings, has_published, "freshness",
           "No published-date signal found; LLMs deprioritize stale content")
    _check(findings, quotable >= 3, "quotability",
           "Few short, fact-dense sentences; LLMs prefer quotable lines",
           detail=f"quotable_sentences={quotable}")

    score = _score(
        title=title, meta_desc=meta_desc, h1_count=len(h1), word_count=word_count,
        images_missing_alt=images_missing_alt, total_images=len(images),
        schema_blocks=schema_blocks, has_canonical=canonical is not None,
        has_og=bool(og.get("title")), has_published=has_published, quotable=quotable,
    )

    return PageAudit(
        source=source,
        url=url,
        title=title,
        title_length=len(title or ""),
        meta_description=meta_desc,
        meta_description_length=len(meta_desc or ""),
        canonical=canonical,
        robots=robots,
        lang=lang,
        h1=h1,
        h2=h2,
        h3=h3,
        word_count=word_count,
        internal_links=internal_links,
        external_links=external_links,
        images=len(images),
        images_missing_alt=images_missing_alt,
        schema_types=schema_types,
        schema_blocks=schema_blocks,
        open_graph=og,
        twitter_card=tw,
        has_faq_schema=has_faq,
        has_article_schema=has_article,
        has_author=has_author,
        has_published_date=has_published,
        quotable_sentences=quotable,
        score=score,
        findings=findings,
    )


def _meta_content(soup: BeautifulSoup, name: str) -> str | None:
    tag = soup.find("meta", attrs={"name": name})
    if tag and tag.get("content"):
        return tag["content"].strip()
    return None


def _attr(tag: Any, key: str) -> str | None:
    if tag is None:
        return None
    val = tag.get(key)
    return val.strip() if isinstance(val, str) else None


def _count_links(soup: BeautifulSoup, base: str | None) -> tuple[int, int]:
    base_host = urlparse(base).netloc if base else None
    internal = external = 0
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        absolute = urljoin(base or "", href) if base else href
        host = urlparse(absolute).netloc
        if not host or (base_host and host == base_host):
            internal += 1
        else:
            external += 1
    return internal, external


def _extract_jsonld(soup: BeautifulSoup) -> tuple[int, list[str]]:
    types: list[str] = []
    blocks = 0
    for s in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(s.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        blocks += 1
        for node in _iter_jsonld(data):
            t = node.get("@type")
            if isinstance(t, list):
                types.extend(str(x) for x in t)
            elif t:
                types.append(str(t))
    return blocks, sorted(set(types))


def _iter_jsonld(data: Any):
    if isinstance(data, dict):
        yield data
        for v in data.values():
            yield from _iter_jsonld(v)
    elif isinstance(data, list):
        for v in data:
            yield from _iter_jsonld(v)


_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")


def _count_quotable_sentences(text: str) -> int:
    """A 'quotable' sentence is short (<=200 chars), self-contained, fact-dense.

    LLMs preferentially cite these because they fit cleanly into a generated
    answer with attribution. Heuristic, not perfect, but reproducible.
    """
    n = 0
    for s in _SENT_SPLIT.split(text):
        s = s.strip()
        if 40 <= len(s) <= 200 and any(c.isdigit() for c in s):
            n += 1
    return n


def _check(findings: list[dict[str, Any]], ok: bool, key: str, msg: str, detail: str = "") -> None:
    findings.append(
        {"key": key, "ok": bool(ok), "severity": "info" if ok else "warn",
         "message": msg, "detail": detail}
    )


def _score(*, title, meta_desc, h1_count, word_count, images_missing_alt, total_images,
           schema_blocks, has_canonical, has_og, has_published, quotable) -> int:
    score = 0
    score += 10 if title and 10 <= len(title) <= 70 else 0
    score += 10 if meta_desc and 70 <= len(meta_desc) <= 160 else 0
    score += 10 if h1_count == 1 else 0
    if word_count >= 1500:
        score += 15
    elif word_count >= 600:
        score += 10
    elif word_count >= 300:
        score += 5
    score += 10 if has_canonical else 0
    score += 5 if has_og else 0
    if total_images:
        score += int(10 * (1 - images_missing_alt / total_images))
    else:
        score += 5
    score += 10 if schema_blocks > 0 else 0
    score += 10 if has_published else 0
    score += min(10, quotable)
    return min(100, score)
