"""IndexNow engine.

IndexNow is a simple POST that notifies multiple search engines (Bing, Yandex,
Naver, Seznam, Yep) at once. We post to the api.indexnow.org aggregator which
fans out to all participating engines.

Spec: https://www.indexnow.org/documentation
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import httpx

from ..config import get_config
from .base import EngineError, EngineNotConfiguredError

INDEXNOW_ENDPOINT = "https://api.indexnow.org/IndexNow"


def _require_key() -> tuple[str, str | None]:
    cfg = get_config()
    if not cfg.indexnow_key:
        raise EngineNotConfiguredError(
            "indexnow",
            "Set GEOSEO_INDEXNOW_KEY to a 32-char hex string and host it at "
            "https://yourdomain.com/<key>.txt (one line, the key itself).",
        )
    return cfg.indexnow_key, cfg.indexnow_key_location


def submit_url(url: str) -> dict[str, Any]:
    key, key_location = _require_key()
    host = urlparse(url).netloc
    if not host:
        raise EngineError(f"Invalid URL: {url!r} (no host)")

    params = {"url": url, "key": key}
    if key_location:
        params["keyLocation"] = key_location

    cfg = get_config()
    with httpx.Client(timeout=cfg.request_timeout_s) as c:
        r = c.get(INDEXNOW_ENDPOINT, params=params, headers={"User-Agent": cfg.user_agent})

    return {
        "url": url,
        "status_code": r.status_code,
        "ok": 200 <= r.status_code < 300,
        "engines_notified": ["bing", "yandex", "naver", "seznam", "yep"],
        "body": r.text[:500] if r.text else "",
    }


def submit_urls(urls: list[str]) -> dict[str, Any]:
    if not urls:
        raise EngineError("urls list is empty")
    if len(urls) > 10000:
        raise EngineError("IndexNow accepts at most 10,000 URLs per request")

    key, key_location = _require_key()
    host = urlparse(urls[0]).netloc
    if not host:
        raise EngineError(f"Invalid URL: {urls[0]!r} (no host)")
    if any(urlparse(u).netloc != host for u in urls):
        raise EngineError("All URLs in a batch must share the same host")

    payload: dict[str, Any] = {"host": host, "key": key, "urlList": urls}
    if key_location:
        payload["keyLocation"] = key_location

    cfg = get_config()
    with httpx.Client(timeout=cfg.request_timeout_s) as c:
        r = c.post(
            INDEXNOW_ENDPOINT,
            json=payload,
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "User-Agent": cfg.user_agent,
            },
        )

    return {
        "host": host,
        "url_count": len(urls),
        "status_code": r.status_code,
        "ok": 200 <= r.status_code < 300,
        "engines_notified": ["bing", "yandex", "naver", "seznam", "yep"],
        "body": r.text[:500] if r.text else "",
    }
