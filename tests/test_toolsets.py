from __future__ import annotations

import pytest

from geoseo_mcp.server import TOOLSETS, build_server, resolve_toolsets


async def _names(**kw) -> set[str]:
    tools = await build_server(**kw).list_tools()
    return {t.name for t in tools}


def test_resolve_defaults_to_all() -> None:
    assert resolve_toolsets("") == list(TOOLSETS)
    assert resolve_toolsets("all") == list(TOOLSETS)
    assert resolve_toolsets(" audit , LLM ") == ["llm", "audit"]


def test_resolve_rejects_unknown() -> None:
    with pytest.raises(ValueError, match="nope"):
        resolve_toolsets("audit,nope")


async def test_full_server_registers_everything() -> None:
    names = await _names()
    assert len(names) >= 36
    assert {"geoseo_status", "audit_page", "multi_llm_citation_check", "aio_check"} <= names


async def test_filtered_server(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEOSEO_TOOLSETS", "audit")
    names = await _names()
    assert "geoseo_status" in names and "audit_page" in names
    assert not any(n.startswith(("gsc_", "bing_")) for n in names)
    assert "multi_llm_citation_check" not in names
