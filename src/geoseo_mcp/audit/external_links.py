"""Broken external-link prospector.

Collects every outbound ``<a href>`` in a folder of HTML files, checks each
unique URL once (HEAD, falling back to GET when HEAD is refused), and groups
the results so you can see which links are dead, redirected, or flaky and
which pages they appear on.

Results are cached in the local SQLite store (default TTL 7 days), so a
second run over the same content only re-checks new or expired URLs.
"""

from __future__ import annotations

import asyncio
import socket
from collections import defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import urldefrag, urlparse

import httpx
from bs4 import BeautifulSoup

from ..config import get_config
from ..storage import sqlite as store

SKIP_SCHEMES = ("mailto:", "tel:", "javascript:", "data:", "sms:", "ftp:")
# Status codes where a HEAD answer isn't trustworthy and a GET is worth trying.
HEAD_RETRY_STATUSES = {400, 403, 404, 405, 406, 429, 501, 503}
DEFAULT_TTL_S = 7 * 24 * 3600

GROUPS = ("ok", "redirect", "client_error", "server_error", "timeout", "dns_fail", "error")


def _strip_www(host: str) -> str:
    host = host.lower()
    return host[4:] if host.startswith("www.") else host


def _normalize(href: str) -> str | None:
    href = href.strip()
    if not href or href.startswith("#"):
        return None
    if href.lower().startswith(SKIP_SCHEMES):
        return None
    if href.startswith("//"):
        href = "https:" + href
    url, _ = urldefrag(href)
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return None  # relative / internal link
    return url


def collect_links(
    folder: str | Path,
    pattern: str = "*.html",
    site_host: str | None = None,
    limit_files: int = 2000,
) -> tuple[dict[str, list[str]], int]:
    """Map each external URL to the files that link to it.

    Links to ``site_host`` (and its www. variant) are treated as internal and
    skipped. Returns ``(url -> [source files], files_scanned)``.
    """
    root = Path(folder).expanduser().resolve()
    if not root.exists():
        raise FileNotFoundError(f"No such folder: {root}")
    own = _strip_www(site_host) if site_host else None
    sources: dict[str, set[str]] = defaultdict(set)
    files = sorted(root.rglob(pattern))[:limit_files]
    for f in files:
        try:
            soup = BeautifulSoup(f.read_text(encoding="utf-8", errors="replace"), "lxml")
        except OSError:
            continue
        rel = str(f.relative_to(root))
        for a in soup.find_all("a", href=True):
            url = _normalize(a["href"])
            if not url:
                continue
            if own and _strip_www(urlparse(url).hostname or "") == own:
                continue
            sources[url].add(rel)
    return {u: sorted(s) for u, s in sources.items()}, len(files)


def _classify(status: int | None, final_url: str | None, url: str, error: str | None) -> str:
    if error:
        return error
    assert status is not None
    if 200 <= status < 300:
        if final_url and final_url.rstrip("/") != url.rstrip("/"):
            return "redirect"
        return "ok"
    if 300 <= status < 400:
        return "redirect"
    if 400 <= status < 500:
        return "client_error"
    return "server_error"


def _suggest(group: str, status: int | None, final_url: str | None) -> str:
    if group == "ok":
        return "none"
    if group == "redirect":
        return f"update link to final URL: {final_url}" if final_url else "update link"
    if group == "client_error":
        if status in (401, 403, 429):
            return "probably bot-blocked; verify in a browser before changing"
        if status in (404, 410):
            return "replace with a live source or remove the link"
        return "verify manually; replace or remove if it stays broken"
    if group == "dns_fail":
        return "domain no longer resolves; replace or remove the link"
    if group in ("server_error", "timeout"):
        return "may be temporary; re-check later before removing"
    return "verify manually"


def _error_kind(exc: Exception) -> str:
    if isinstance(exc, httpx.TimeoutException):
        return "timeout"
    if isinstance(exc, httpx.ConnectError):
        dns_hints = ("name or service", "nodename", "getaddrinfo", "name resolution",
                     "no address", "not known")
        seen: Exception | BaseException | None = exc
        while seen is not None:
            if isinstance(seen, socket.gaierror):
                return "dns_fail"
            if any(h in str(seen).lower() for h in dns_hints):
                return "dns_fail"
            seen = seen.__cause__ or seen.__context__
    return "error"


async def _check_one(client: httpx.AsyncClient, url: str) -> dict[str, Any]:
    status: int | None = None
    final_url: str | None = None
    method = "HEAD"
    error: str | None = None
    detail: str | None = None
    try:
        resp = await client.head(url)
        status, final_url = resp.status_code, str(resp.url)
        if status in HEAD_RETRY_STATUSES:
            method = "GET"
            async with client.stream("GET", url) as r:
                status, final_url = r.status_code, str(r.url)
    except Exception as e:  # noqa: BLE001 - classify anything network-ish
        if method == "HEAD":
            # Some servers drop HEAD entirely; give GET one chance.
            try:
                method = "GET"
                async with client.stream("GET", url) as r:
                    status, final_url = r.status_code, str(r.url)
            except Exception as e2:  # noqa: BLE001
                error, detail = _error_kind(e2), f"{type(e2).__name__}: {e2}"[:200]
        elif status is None:
            error, detail = _error_kind(e), f"{type(e).__name__}: {e}"[:200]
        else:
            method = "HEAD"  # GET retry failed; keep the HEAD answer
    group = _classify(status, final_url, url, error)
    out: dict[str, Any] = {
        "url": url,
        "group": group,
        "status": status,
        "final_url": final_url if final_url and final_url != url else None,
        "method": method,
        "suggested_action": _suggest(group, status, final_url),
    }
    if detail:
        out["error"] = detail
    return out


async def check_urls(
    urls: list[str],
    timeout: float = 10.0,
    concurrency: int = 20,
    transport: httpx.AsyncBaseTransport | None = None,
) -> dict[str, dict[str, Any]]:
    """Check URLs concurrently. Returns ``url -> result``."""
    sem = asyncio.Semaphore(max(1, concurrency))
    headers = {"User-Agent": get_config().user_agent, "Accept": "*/*"}
    async with httpx.AsyncClient(
        timeout=timeout, follow_redirects=True, headers=headers, transport=transport,
        limits=httpx.Limits(max_connections=max(1, concurrency)),
    ) as client:

        async def run(u: str) -> dict[str, Any]:
            async with sem:
                return await _check_one(client, u)

        results = await asyncio.gather(*(run(u) for u in urls))
    return {r["url"]: r for r in results}


async def find_broken_async(
    folder: str,
    pattern: str = "*.html",
    timeout: float = 10.0,
    concurrency: int = 20,
    site_host: str | None = None,
    cache_ttl_s: float = DEFAULT_TTL_S,
    include_ok: bool = False,
    max_urls: int = 2000,
    transport: httpx.AsyncBaseTransport | None = None,
) -> dict[str, Any]:
    sources, files_scanned = collect_links(folder, pattern=pattern, site_host=site_host)
    urls = sorted(sources)
    truncated = len(urls) > max_urls
    urls = urls[:max_urls]

    cached = store.link_cache_get(urls, cache_ttl_s) if cache_ttl_s > 0 else {}
    to_check = [u for u in urls if u not in cached]
    fresh = await check_urls(to_check, timeout=timeout, concurrency=concurrency,
                             transport=transport) if to_check else {}
    if cache_ttl_s > 0:
        # Don't cache transient failures; they deserve a re-check next run.
        store.link_cache_put(
            {u: r for u, r in fresh.items() if r["group"] not in ("timeout", "error")}
        )

    results = {**cached, **fresh}
    counts = dict.fromkeys(GROUPS, 0)
    links: list[dict[str, Any]] = []
    for u in urls:
        r = dict(results[u])
        counts[r["group"]] = counts.get(r["group"], 0) + 1
        r["source_pages"] = sources[u]
        r["cached"] = u in cached
        if include_ok or r["group"] != "ok":
            links.append(r)
    order = {g: i for i, g in enumerate(
        ("client_error", "dns_fail", "server_error", "timeout", "error", "redirect", "ok")
    )}
    links.sort(key=lambda r: (order.get(r["group"], 99), -len(r["source_pages"]), r["url"]))

    return {
        "folder": str(Path(folder).expanduser().resolve()),
        "files_scanned": files_scanned,
        "external_urls": len(urls),
        "truncated": truncated,
        "checked_now": len(to_check),
        "from_cache": len(cached),
        "counts": counts,
        "links": links,
    }


def find_broken(folder: str, **kwargs: Any) -> dict[str, Any]:
    """Synchronous wrapper around :func:`find_broken_async`."""
    return asyncio.run(find_broken_async(folder, **kwargs))
