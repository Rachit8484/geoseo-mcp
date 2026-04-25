"""Internal link graph + suggestions.

Reads a folder of HTML files, builds a graph of (file -> file) edges from
``<a href>`` links, and computes:

- structure stats: orphans, dead-ends, hubs, dangling links
- related-page suggestions per file: top-K topically similar files that the
  source does NOT already link to, ranked by simple TF over title + headings
  + meta description (cheap, deterministic, zero deps beyond bs4)

The TF model is intentionally tiny — it stays under ~50ms for hundreds of
pages and gives "good enough" related-link recs. Swap for embeddings later.
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import urldefrag, urlparse

from bs4 import BeautifulSoup

_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9'\-]{2,}")


def _strip_www(host: str) -> str:
    return host[4:] if host.startswith("www.") else host
_STOPWORDS = {
    "the", "and", "for", "you", "your", "with", "that", "this", "from", "are",
    "can", "how", "why", "what", "when", "where", "who", "will", "have", "has",
    "but", "not", "all", "any", "our", "out", "use", "uses", "using", "into",
    "about", "more", "most", "than", "their", "they", "them", "these", "those",
    "been", "was", "were", "would", "could", "should", "also", "just", "like",
    "get", "got", "make", "made", "much", "many", "very", "some", "such",
    "one", "two", "three", "new", "best", "top", "good", "bad", "page", "site",
    "html", "www", "com", "https", "http",
}


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text or "") if t.lower() not in _STOPWORDS]


def _features(html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")
    title = (soup.title.string if soup.title and soup.title.string else "") or ""
    md = soup.find("meta", attrs={"name": "description"})
    desc = md.get("content", "") if md else ""
    headings = " ".join(h.get_text(" ", strip=True) for h in soup.find_all(["h1", "h2", "h3"]))
    body_el = soup.body or soup
    for tag in body_el.find_all(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    body = body_el.get_text(" ", strip=True)[:8000]
    links = []
    for a in soup.find_all("a", href=True):
        href, _ = urldefrag(a["href"])
        links.append(href.strip())
    return {
        "title": title.strip(), "desc": desc.strip(),
        "headings": headings, "body": body, "links": links,
    }


def _resolve_internal(
    href: str,
    src_path: Path,
    root: Path,
    file_set: set[str],
    site_host: str | None,
    basename_index: dict[str, str],
) -> str | None:
    """Return the relative-to-root path string if ``href`` points inside ``root``.

    Tries (in order): literal path, ``path.html``, ``path/index.html``, and
    finally a basename match against ``basename_index`` — which is how we
    resolve ``/blog/foo`` to ``foo.html`` when the on-disk file is flat.
    """
    if not href:
        return None
    parsed = urlparse(href)
    if parsed.scheme in {"mailto", "tel", "javascript"}:
        return None
    if parsed.scheme in {"http", "https"} and (
        not site_host or _strip_www(parsed.netloc.lower()) != site_host
    ):
        return None
    target = parsed.path or ""
    if not target or target == "/":
        return None

    candidates: list[Path] = []
    base = (
        root / target.lstrip("/")
        if target.startswith("/")
        else src_path.parent / target
    )
    candidates.append(base)
    if not base.suffix:
        candidates.append(Path(str(base) + ".html"))
        candidates.append(base / "index.html")

    for c in candidates:
        try:
            rel = str(c.resolve().relative_to(root))
        except (ValueError, OSError):
            continue
        if rel in file_set:
            return rel

    slug = target.rstrip("/").rsplit("/", 1)[-1].lower()
    if slug and slug in basename_index:
        return basename_index[slug]
    return None


def build(
    folder: str,
    pattern: str = "*.html",
    limit: int = 1000,
    site_host: str | None = None,
) -> dict[str, Any]:
    """Audit the internal link graph of ``folder``.

    Args:
        folder: directory to scan recursively.
        pattern: glob, default ``*.html``.
        limit: max files.
        site_host: if pages link to themselves with absolute URLs (e.g.
            ``https://example.com/blog/foo``), pass the bare host
            (``example.com``) to count those as internal.

    Returns:
        - ``files``: total parsed
        - ``edges``: directed (src, dst) pairs
        - ``orphans``: files with zero inbound internal links
        - ``dead_ends``: files with zero outbound internal links
        - ``hubs``: top-10 by inbound count
        - ``dangling``: per-file lists of internal hrefs that don't resolve
    """
    root = Path(folder).expanduser().resolve()
    if not root.exists():
        return {"error": f"No such folder: {root}"}
    files = sorted(root.rglob(pattern))[:limit]
    rels = [str(p.relative_to(root)) for p in files]
    file_set = set(rels)
    if site_host:
        site_host = _strip_www(site_host.lower())
    basename_index: dict[str, str] = {}
    for r in rels:
        stem = Path(r).stem.lower()
        basename_index.setdefault(stem, r)

    inbound: dict[str, int] = defaultdict(int)
    outbound: dict[str, int] = defaultdict(int)
    edges: list[tuple[str, str]] = []
    dangling: dict[str, list[str]] = {}

    feats: dict[str, dict[str, Any]] = {}
    for path in files:
        rel = str(path.relative_to(root))
        try:
            html = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        f = _features(html)
        feats[rel] = f
        broken: list[str] = []
        seen: set[str] = set()
        for href in f["links"]:
            target = _resolve_internal(
                href, path, root, file_set, site_host, basename_index,
            )
            if target is None:
                parsed = urlparse(href)
                if (
                    parsed.scheme not in {"http", "https", "mailto", "tel", "javascript"}
                    and href
                    and not parsed.netloc
                ):
                    broken.append(href)
                continue
            if target == rel or target in seen:
                continue
            seen.add(target)
            edges.append((rel, target))
            outbound[rel] += 1
            inbound[target] += 1
        if broken:
            dangling[rel] = broken[:20]

    orphans = [r for r in rels if inbound.get(r, 0) == 0]
    dead_ends = [r for r in rels if outbound.get(r, 0) == 0]
    hubs = sorted(rels, key=lambda r: inbound.get(r, 0), reverse=True)[:10]

    return {
        "folder": str(root),
        "files": len(rels),
        "edges": len(edges),
        "orphans": orphans[:50],
        "dead_ends": dead_ends[:50],
        "hubs": [{"path": h, "inbound": inbound.get(h, 0)} for h in hubs],
        "dangling": dangling,
        "_feats": feats,
        "_edges": edges,
    }


def suggest(
    folder: str,
    page: str | None = None,
    pattern: str = "*.html",
    top_k: int = 5,
    limit: int = 1000,
    site_host: str | None = None,
) -> dict[str, Any]:
    """Suggest top-K internal links to add per page.

    If ``page`` is given (relative-to-folder path or absolute), suggestions
    are returned only for that page; otherwise for every page. Suggestions
    exclude pages already linked from the source.
    """
    g = build(folder, pattern=pattern, limit=limit, site_host=site_host)
    if "error" in g:
        return g
    feats: dict[str, dict[str, Any]] = g.pop("_feats")
    edges: list[tuple[str, str]] = g.pop("_edges")
    out_edges: dict[str, set[str]] = defaultdict(set)
    for s, t in edges:
        out_edges[s].add(t)

    docs = list(feats.keys())
    tf: dict[str, Counter] = {}
    df: Counter = Counter()
    for d in docs:
        f = feats[d]
        text = " ".join([
            f["title"], f["title"], f["title"],
            f["desc"], f["headings"], f["headings"],
            f.get("body", ""),
        ])
        toks = _tokenize(text)
        c = Counter(toks)
        tf[d] = c
        for term in c:
            df[term] += 1

    n_docs = max(len(docs), 1)
    idf: dict[str, float] = {term: math.log(1 + n_docs / (1 + d)) for term, d in df.items()}

    def vec(d: str) -> dict[str, float]:
        c = tf[d]
        total = sum(c.values()) or 1
        return {t: (n / total) * idf.get(t, 1.0) for t, n in c.items()}

    def cosine(a: dict[str, float], b: dict[str, float]) -> float:
        if not a or not b:
            return 0.0
        common = set(a) & set(b)
        dot = sum(a[t] * b[t] for t in common)
        na = math.sqrt(sum(v * v for v in a.values()))
        nb = math.sqrt(sum(v * v for v in b.values()))
        return dot / (na * nb) if na and nb else 0.0

    vecs = {d: vec(d) for d in docs}

    target_docs: list[str]
    if page:
        rp = page
        root = Path(folder).expanduser().resolve()
        ap = Path(page)
        if ap.is_absolute():
            try:
                rp = str(ap.resolve().relative_to(root))
            except ValueError:
                return {"error": f"{page} not under {root}"}
        if rp not in feats:
            return {"error": f"{rp} not found among audited files"}
        target_docs = [rp]
    else:
        target_docs = docs

    suggestions: dict[str, list[dict[str, Any]]] = {}
    for src in target_docs:
        existing = out_edges.get(src, set()) | {src}
        scored: list[tuple[str, float]] = []
        sv = vecs[src]
        for cand in docs:
            if cand in existing:
                continue
            scored.append((cand, cosine(sv, vecs[cand])))
        scored.sort(key=lambda x: x[1], reverse=True)
        top = [
            {
                "target": t,
                "score": round(s, 4),
                "title": feats[t]["title"],
                "anchor_hint": _anchor_hint(feats[src], feats[t]),
            }
            for t, s in scored[:top_k]
            if s > 0
        ]
        suggestions[src] = top

    return {
        "folder": g["folder"],
        "files": g["files"],
        "suggestions": suggestions,
    }


def _anchor_hint(src: dict[str, Any], dst: dict[str, Any]) -> str:
    """Cheap anchor-text suggestion: shared content words from dst's title."""
    src_terms = set(_tokenize(" ".join([src["title"], src["headings"]])))
    dst_title_toks = _tokenize(dst["title"]) or [dst["title"]]
    overlap = [t for t in dst_title_toks if t in src_terms]
    if overlap:
        return " ".join(overlap[:6])
    return dst["title"][:80] if dst.get("title") else ""
