"""SQLite snapshot store for trend tracking.

Two tables — both append-only, one row per metric per snapshot.

``gsc_snapshots`` columns:
    captured_at | site_url | query | page | country | device | clicks
    impressions | ctr | position | dimensions

``llm_citation_snapshots`` columns:
    captured_at | run_id | engine | target_domain | question | cited
    cited_domains_json | answer_excerpt

The DB lives at ``$GEOSEO_DB`` (default: platform user-data dir / ``geoseo.sqlite``).
We never modify previous rows; trends are computed by comparing snapshots
captured at different ``captured_at`` timestamps.
"""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..config import get_config

SCHEMA_VERSION = 1

_DDL = [
    """
    CREATE TABLE IF NOT EXISTS schema_meta (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS gsc_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        captured_at TEXT NOT NULL,
        site_url TEXT NOT NULL,
        dimensions TEXT NOT NULL,
        query TEXT,
        page TEXT,
        country TEXT,
        device TEXT,
        date TEXT,
        clicks REAL NOT NULL DEFAULT 0,
        impressions REAL NOT NULL DEFAULT 0,
        ctr REAL NOT NULL DEFAULT 0,
        position REAL NOT NULL DEFAULT 0
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS gsc_idx_site_time
      ON gsc_snapshots(site_url, captured_at)
    """,
    """
    CREATE INDEX IF NOT EXISTS gsc_idx_query
      ON gsc_snapshots(site_url, query, captured_at)
    """,
    """
    CREATE TABLE IF NOT EXISTS llm_citation_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        captured_at TEXT NOT NULL,
        run_id TEXT NOT NULL,
        engine TEXT NOT NULL,
        target_domain TEXT NOT NULL,
        question TEXT NOT NULL,
        cited INTEGER NOT NULL,
        cited_domains_json TEXT NOT NULL,
        answer_excerpt TEXT
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS llm_idx_target_time
      ON llm_citation_snapshots(target_domain, captured_at)
    """,
    """
    CREATE INDEX IF NOT EXISTS llm_idx_run
      ON llm_citation_snapshots(run_id)
    """,
]


def _db_path() -> Path:
    cfg = get_config()
    p = os.getenv("GEOSEO_DB")
    return Path(p).expanduser() if p else cfg.data_dir / "geoseo.sqlite"


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def _ensure_schema(conn: sqlite3.Connection) -> None:
    for stmt in _DDL:
        conn.execute(stmt)
    conn.execute(
        "INSERT OR REPLACE INTO schema_meta(key, value) VALUES('schema_version', ?)",
        (str(SCHEMA_VERSION),),
    )
    conn.commit()


def init() -> dict[str, Any]:
    """Create the DB if it doesn't exist; return its path."""
    with _connect() as conn:
        _ensure_schema(conn)
    return {"db_path": str(_db_path()), "schema_version": SCHEMA_VERSION}


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def insert_gsc_rows(
    site_url: str,
    dimensions: list[str],
    rows: list[dict[str, Any]],
    captured_at: str | None = None,
) -> dict[str, Any]:
    captured_at = captured_at or now_iso()
    dim_str = ",".join(dimensions)
    inserted = 0
    with _connect() as conn:
        _ensure_schema(conn)
        for r in rows:
            keys = r.get("keys") or []
            values = {d: keys[i] if i < len(keys) else None for i, d in enumerate(dimensions)}
            conn.execute(
                """
                INSERT INTO gsc_snapshots
                  (captured_at, site_url, dimensions, query, page, country, device, date,
                   clicks, impressions, ctr, position)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    captured_at, site_url, dim_str,
                    values.get("query"), values.get("page"),
                    values.get("country"), values.get("device"), values.get("date"),
                    float(r.get("clicks") or 0),
                    float(r.get("impressions") or 0),
                    float(r.get("ctr") or 0),
                    float(r.get("position") or 0),
                ),
            )
            inserted += 1
        conn.commit()
    return {
        "site_url": site_url, "dimensions": dimensions,
        "rows_inserted": inserted, "captured_at": captured_at,
    }


def insert_citation_rows(
    target_domain: str,
    rows: list[dict[str, Any]],
    captured_at: str | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    captured_at = captured_at or now_iso()
    run_id = run_id or uuid.uuid4().hex[:12]
    inserted = 0
    with _connect() as conn:
        _ensure_schema(conn)
        for r in rows:
            conn.execute(
                """
                INSERT INTO llm_citation_snapshots
                  (captured_at, run_id, engine, target_domain, question, cited,
                   cited_domains_json, answer_excerpt)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    captured_at, run_id, r["engine"], target_domain, r["question"],
                    1 if r.get("cited") else 0,
                    json.dumps(r.get("cited_domains") or []),
                    r.get("answer_excerpt", "")[:500],
                ),
            )
            inserted += 1
        conn.commit()
    return {
        "target_domain": target_domain, "run_id": run_id,
        "rows_inserted": inserted, "captured_at": captured_at,
    }


def gsc_trend(
    site_url: str,
    query: str | None = None,
    page: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """Return time-series for clicks/impressions/position grouped by snapshot.

    If both ``query`` and ``page`` are None, aggregates the whole property.
    """
    with _connect() as conn:
        _ensure_schema(conn)
        clauses = ["site_url = ?"]
        args: list[Any] = [site_url]
        if query is not None:
            clauses.append("query = ?")
            args.append(query)
        if page is not None:
            clauses.append("page = ?")
            args.append(page)
        sql = f"""
            SELECT captured_at,
                   SUM(clicks) AS clicks,
                   SUM(impressions) AS impressions,
                   AVG(position) AS position,
                   AVG(ctr) AS ctr
            FROM gsc_snapshots
            WHERE {' AND '.join(clauses)}
            GROUP BY captured_at
            ORDER BY captured_at DESC
            LIMIT ?
        """
        cur = conn.execute(sql, [*args, limit])
        rows = [dict(r) for r in cur.fetchall()]
    rows.reverse()
    return {"site_url": site_url, "query": query, "page": page, "series": rows}


def citation_trend(
    target_domain: str,
    engine: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """Per-snapshot citation share over time, optionally filtered by engine."""
    with _connect() as conn:
        _ensure_schema(conn)
        clauses = ["target_domain = ?"]
        args: list[Any] = [target_domain]
        if engine:
            clauses.append("engine = ?")
            args.append(engine)
        sql = f"""
            SELECT captured_at, engine,
                   COUNT(*) AS questions,
                   SUM(cited) AS cited
            FROM llm_citation_snapshots
            WHERE {' AND '.join(clauses)}
            GROUP BY captured_at, engine
            ORDER BY captured_at DESC
            LIMIT ?
        """
        cur = conn.execute(sql, [*args, limit])
        rows = [
            {
                "captured_at": r["captured_at"],
                "engine": r["engine"],
                "questions": r["questions"],
                "cited": r["cited"],
                "citation_share": (r["cited"] / r["questions"]) if r["questions"] else 0.0,
            }
            for r in cur.fetchall()
        ]
    rows.reverse()
    return {"target_domain": target_domain, "engine": engine, "series": rows}


def stats() -> dict[str, Any]:
    """Inventory of what's stored."""
    with _connect() as conn:
        _ensure_schema(conn)
        gsc = conn.execute(
            "SELECT COUNT(*) c, COUNT(DISTINCT site_url) s, MIN(captured_at) a, MAX(captured_at) b FROM gsc_snapshots"
        ).fetchone()
        llm = conn.execute(
            "SELECT COUNT(*) c, COUNT(DISTINCT target_domain) d, MIN(captured_at) a, MAX(captured_at) b FROM llm_citation_snapshots"
        ).fetchone()
    return {
        "db_path": str(_db_path()),
        "gsc": {"rows": gsc["c"], "sites": gsc["s"], "oldest": gsc["a"], "newest": gsc["b"]},
        "llm_citations": {
            "rows": llm["c"], "domains": llm["d"], "oldest": llm["a"], "newest": llm["b"],
        },
    }
