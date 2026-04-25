"""Smoke tests for the SQLite snapshot store."""

from __future__ import annotations

import os

from geoseo_mcp.storage import sqlite as store


def _set_db(tmp_path, monkeypatch):
    db = tmp_path / "geoseo.sqlite"
    monkeypatch.setenv("GEOSEO_DB", str(db))
    return db


def test_init_creates_db(tmp_path, monkeypatch):
    db = _set_db(tmp_path, monkeypatch)
    info = store.init()
    assert info["db_path"] == str(db)
    assert os.path.exists(db)


def test_gsc_insert_and_trend(tmp_path, monkeypatch):
    _set_db(tmp_path, monkeypatch)
    rows_a = [
        {"keys": ["how to quit drinking"], "clicks": 5, "impressions": 100, "ctr": 0.05, "position": 8.2},
        {"keys": ["sober dating"],         "clicks": 2, "impressions": 50,  "ctr": 0.04, "position": 12.0},
    ]
    rows_b = [
        {"keys": ["how to quit drinking"], "clicks": 9, "impressions": 140, "ctr": 0.064, "position": 6.5},
    ]

    store.insert_gsc_rows(
        site_url="sc-domain:example.com", dimensions=["query"],
        rows=rows_a, captured_at="2026-04-01T00:00:00+00:00",
    )
    store.insert_gsc_rows(
        site_url="sc-domain:example.com", dimensions=["query"],
        rows=rows_b, captured_at="2026-04-08T00:00:00+00:00",
    )

    trend_all = store.gsc_trend("sc-domain:example.com")
    assert len(trend_all["series"]) == 2
    assert trend_all["series"][0]["captured_at"] < trend_all["series"][1]["captured_at"]

    trend_q = store.gsc_trend("sc-domain:example.com", query="how to quit drinking")
    assert len(trend_q["series"]) == 2
    assert trend_q["series"][1]["clicks"] == 9


def test_citation_insert_and_trend(tmp_path, monkeypatch):
    _set_db(tmp_path, monkeypatch)
    store.insert_citation_rows(
        target_domain="example.com",
        captured_at="2026-04-01T00:00:00+00:00",
        rows=[
            {"engine": "openai", "question": "best sober app", "cited": True,  "cited_domains": ["example.com", "reddit.com"]},
            {"engine": "openai", "question": "quit drinking", "cited": False, "cited_domains": ["aa.org"]},
        ],
    )
    store.insert_citation_rows(
        target_domain="example.com",
        captured_at="2026-04-08T00:00:00+00:00",
        rows=[
            {"engine": "openai", "question": "best sober app", "cited": True, "cited_domains": ["example.com"]},
            {"engine": "openai", "question": "quit drinking",  "cited": True, "cited_domains": ["example.com", "nih.gov"]},
        ],
    )

    trend = store.citation_trend("example.com", engine="openai")
    assert len(trend["series"]) == 2
    assert trend["series"][0]["citation_share"] == 0.5
    assert trend["series"][1]["citation_share"] == 1.0


def test_stats_reports_inventory(tmp_path, monkeypatch):
    _set_db(tmp_path, monkeypatch)
    store.insert_gsc_rows(
        site_url="sc-domain:a.com", dimensions=["query"],
        rows=[{"keys": ["x"], "clicks": 1, "impressions": 1, "ctr": 1, "position": 1}],
    )
    info = store.stats()
    assert info["gsc"]["rows"] == 1
    assert info["gsc"]["sites"] == 1
