"""Google Search Console engine.

Thin wrapper over the official ``google-api-python-client``. Returns plain
dicts; tool layer handles MCP-shaped responses.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from ..auth.google import GSC_SCOPES, get_credentials
from .base import EngineError


def _client():
    creds = get_credentials(GSC_SCOPES)
    return build("searchconsole", "v1", credentials=creds, cache_discovery=False)


def list_sites() -> list[dict[str, Any]]:
    try:
        resp = _client().sites().list().execute()
    except HttpError as e:
        raise EngineError(f"GSC list_sites failed: {e}") from e
    return resp.get("siteEntry", [])


def query_performance(
    site_url: str,
    start_date: str | None = None,
    end_date: str | None = None,
    dimensions: list[str] | None = None,
    row_limit: int = 1000,
    search_type: str = "web",
    country: str | None = None,
    device: str | None = None,
) -> dict[str, Any]:
    today = date.today()
    start_date = start_date or (today - timedelta(days=28)).isoformat()
    end_date = end_date or (today - timedelta(days=2)).isoformat()
    dimensions = dimensions or ["query"]

    body: dict[str, Any] = {
        "startDate": start_date,
        "endDate": end_date,
        "dimensions": dimensions,
        "rowLimit": min(row_limit, 25000),
        "type": search_type,
    }
    filters = []
    if country:
        filters.append({"dimension": "country", "operator": "equals", "expression": country})
    if device:
        filters.append({"dimension": "device", "operator": "equals", "expression": device})
    if filters:
        body["dimensionFilterGroups"] = [{"filters": filters}]

    try:
        resp = (
            _client()
            .searchanalytics()
            .query(siteUrl=site_url, body=body)
            .execute()
        )
    except HttpError as e:
        raise EngineError(f"GSC performance query failed: {e}") from e
    return {"site_url": site_url, "request": body, "rows": resp.get("rows", [])}


def inspect_url(site_url: str, url: str, language_code: str = "en-US") -> dict[str, Any]:
    body = {
        "inspectionUrl": url,
        "siteUrl": site_url,
        "languageCode": language_code,
    }
    try:
        resp = _client().urlInspection().index().inspect(body=body).execute()
    except HttpError as e:
        raise EngineError(f"GSC URL inspect failed: {e}") from e
    return resp


def submit_sitemap(site_url: str, feedpath: str) -> dict[str, Any]:
    try:
        _client().sitemaps().submit(siteUrl=site_url, feedpath=feedpath).execute()
    except HttpError as e:
        raise EngineError(f"GSC sitemap submit failed: {e}") from e
    return {"site_url": site_url, "feedpath": feedpath, "submitted": True}
