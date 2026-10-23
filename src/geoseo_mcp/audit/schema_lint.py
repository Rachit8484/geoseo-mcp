"""JSON-LD linter for Google structured-data requirements.

Parses every ``<script type="application/ld+json">`` block (including
``@graph`` containers and top-level arrays) and checks each typed entity
against the required/recommended properties in :mod:`._schema_rules`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from . import _schema_rules as rules
from .on_page import _load


def _empty(v: Any) -> bool:
    return v is None or v == "" or v == [] or v == {}


def _types(node: dict[str, Any]) -> list[str]:
    t = node.get("@type")
    if isinstance(t, str):
        t = [t]
    if not isinstance(t, list):
        return []
    # Strip schema.org prefixes like "schema:Product" or full URLs.
    return [str(x).rsplit("/", 1)[-1].rsplit(":", 1)[-1] for x in t if x]


def _as_list(v: Any) -> list[Any]:
    return v if isinstance(v, list) else [v]


def _missing(node: Any, path: str, prefix: str = "") -> list[str]:
    """Return the concrete paths under ``node`` that are missing ``path``."""
    head, _, rest = path.partition(".")
    each = head.endswith("[]")
    key = head[:-2] if each else head
    here = f"{prefix}{key}"
    values = [n.get(key) for n in _as_list(node) if isinstance(n, dict)]
    present = [v for v in values if not _empty(v)]
    if not present:
        return [here]
    if not rest:
        return []
    out: list[str] = []
    for v in present:
        items = _as_list(v)
        if each:
            for i, item in enumerate(items):
                out.extend(_missing(item, rest, f"{here}[{i}]."))
        else:
            # Non-list path: any one of the values satisfying it is enough.
            sub = _missing(items, rest, f"{here}.")
            if not sub:
                return []
            out = sub
    return out


def _check(node: dict[str, Any], rule_name: str, prefix: str = "") -> dict[str, list[str]]:
    rule = rules.RULES[rule_name]
    required: list[str] = []
    for p in rule.get("required", []):
        required.extend(_missing(node, p, prefix))
    for group in rule.get("any_of", []):
        if all(_missing(node, p) for p in group):
            required.append(prefix + " | ".join(group) + " (one of)")
    recommended: list[str] = []
    for p in rule.get("recommended", []):
        recommended.extend(_missing(node, p, prefix))
    for prop, sub_rule in rule.get("nested", {}).items():
        for i, child in enumerate(_as_list(node.get(prop))):
            if not isinstance(child, dict):
                continue
            target = sub_rule
            if sub_rule == "Offer" and "AggregateOffer" in _types(child):
                target = "AggregateOffer"
            label = f"{prefix}{prop}" + (f"[{i}]" if isinstance(node.get(prop), list) else "")
            sub = _check(child, target, label + ".")
            required.extend(sub["required"])
            recommended.extend(sub["recommended"])
    if rule_name == "BreadcrumbList":
        items = _as_list(node.get("itemListElement"))
        last = f"{prefix}itemListElement[{len(items) - 1}].item"
        required = [r for r in required if r != last]
    if rule_name == "JobPosting" and str(node.get("jobLocationType", "")).upper() == "TELECOMMUTE":
        required = [r for r in required if r != f"{prefix}jobLocation"]
        if _empty(node.get("applicantLocationRequirements")):
            required.append(f"{prefix}applicantLocationRequirements")
    # De-duplicate while keeping order.
    return {
        "required": list(dict.fromkeys(required)),
        "recommended": [r for r in dict.fromkeys(recommended) if r not in required],
    }


def _entities(data: Any) -> list[dict[str, Any]]:
    """Typed nodes, plus untyped nodes that carry an ``@id`` (they extend another)."""
    out: list[dict[str, Any]] = []
    for item in _as_list(data):
        if not isinstance(item, dict):
            continue
        if "@graph" in item:
            out.extend(_entities(item["@graph"]))
        if _types(item) or "@id" in item:
            out.append(item)
    return out


def _blank(block: int, line: int | None, error: str) -> dict[str, Any]:
    return {"block": block, "line_estimate": line, "type": None, "ok": False,
            "error": error, "required_missing": [], "recommended_missing": []}


def lint_html(html: str) -> list[dict[str, Any]]:
    """Lint every JSON-LD block in an HTML string.

    Nodes sharing an ``@id`` are merged before checking, so a block that only
    adds ``aggregateRating`` to ``{"@id": "...#Recipe"}`` counts toward that
    recipe instead of being reported on its own.
    """
    soup = BeautifulSoup(html, "html.parser")
    results: list[dict[str, Any]] = []
    found: list[tuple[int, int | None, dict[str, Any]]] = []
    for block_idx, tag in enumerate(soup.find_all("script", type="application/ld+json")):
        line = getattr(tag, "sourceline", None)
        raw = tag.string or tag.get_text() or ""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            results.append(_blank(block_idx, line,
                                  f"invalid JSON: {e.msg} (line {e.lineno} of block)"))
            continue
        entities = _entities(data)
        if not entities:
            results.append(_blank(block_idx, line, "no @type found in block"))
        found.extend((block_idx, line, ent) for ent in entities)

    merged: dict[str, dict[str, Any]] = {}
    for _, _, ent in found:
        if "@id" in ent:
            merged.setdefault(str(ent["@id"]), {}).update(
                {k: v for k, v in ent.items() if k != "@type" or _types(ent)}
            )
    seen_ids: set[str] = set()
    for block_idx, line, ent in found:
        ent_id = str(ent["@id"]) if "@id" in ent else None
        if ent_id is not None:
            node = merged[ent_id]
            if not _types(ent) and _types(node):
                continue  # reported with the typed node it extends
            if ent_id in seen_ids:
                continue
            seen_ids.add(ent_id)
        else:
            node = ent
        types = _types(node)
        if not types:
            results.append({
                "block": block_idx, "line_estimate": line, "type": None, "rule": None,
                "ok": True, "required_missing": [], "recommended_missing": [],
                "note": f"Untyped node {ent_id}; nothing to check.",
            })
            continue
        rule_name = next((r for r in map(rules.resolve, types) if r), None)
        entry: dict[str, Any] = {
            "block": block_idx,
            "line_estimate": line,
            "type": types[0] if len(types) == 1 else types,
            "rule": rule_name,
        }
        if rule_name is None:
            entry.update(ok=True, required_missing=[], recommended_missing=[],
                         note="No Google rich-result rules for this type; not checked.")
        else:
            missing = _check(node, rule_name)
            rule = rules.RULES[rule_name]
            entry.update(
                ok=not missing["required"],
                required_missing=missing["required"],
                recommended_missing=missing["recommended"],
                doc=rule["doc"],
            )
            if rule.get("note"):
                entry["note"] = rule["note"]
        results.append(entry)
    results.sort(key=lambda b: b["block"])
    return results


def lint(source: str) -> dict[str, Any]:
    """Lint a local HTML file or http(s) URL."""
    html, url = _load(source)
    blocks = lint_html(html)
    checked = [b for b in blocks if b.get("rule") or b.get("error")]
    return {
        "source": source,
        "url": url,
        "blocks": blocks,
        "entities": len([b for b in blocks if b.get("type")]),
        "errors": sum(1 for b in checked if not b["ok"]),
        "ok": all(b["ok"] for b in blocks),
    }


def lint_folder(folder: str, pattern: str = "*.html", limit: int = 500) -> dict[str, Any]:
    root = Path(folder).expanduser().resolve()
    if not root.exists():
        raise FileNotFoundError(f"No such folder: {root}")
    files = sorted(root.rglob(pattern))[:limit]
    per_file: list[dict[str, Any]] = []
    tally: dict[str, int] = {}
    types: dict[str, int] = {}
    no_schema: list[str] = []
    for f in files:
        rel = str(f.relative_to(root))
        try:
            rep = lint(str(f))
        except Exception as e:  # noqa: BLE001
            per_file.append({"path": rel, "error": str(e)})
            continue
        if not rep["blocks"]:
            no_schema.append(rel)
            continue
        problems = []
        for b in rep["blocks"]:
            t = b["type"] if isinstance(b["type"], str) else str(b["type"])
            types[t] = types.get(t, 0) + 1
            for m in b["required_missing"]:
                key = f"{b.get('rule') or t}: {m}"
                tally[key] = tally.get(key, 0) + 1
            if not b["ok"]:
                problems.append({k: b[k] for k in ("type", "line_estimate", "required_missing")
                                 if k in b} | ({"error": b["error"]} if "error" in b else {}))
        per_file.append({"path": rel, "ok": rep["ok"], "problems": problems})
    return {
        "folder": str(root),
        "files_scanned": len(files),
        "files_with_errors": sum(1 for p in per_file if not p.get("ok", False)),
        "files_without_schema": no_schema,
        "types_found": dict(sorted(types.items(), key=lambda kv: -kv[1])),
        "most_common_missing": [
            {"issue": k, "count": n}
            for k, n in sorted(tally.items(), key=lambda kv: -kv[1])[:25]
        ],
        "per_file": per_file,
    }
