"""JavaScript-dependency finding and the optional render path."""

from __future__ import annotations

import builtins
from pathlib import Path

import pytest

from geoseo_mcp.audit import on_page

from .test_audit import SAMPLE_HTML

SPA_SHELL = """<!doctype html><html><head><title>Acme | CRM</title>
<script type="module" src="/assets/index-abc123.js"></script></head>
<body><div id="root"></div><noscript>You need to enable JavaScript to run this app.</noscript>
</body></html>"""


def _finding(rep: dict, key: str) -> dict:
    return next(f for f in rep["findings"] if f["key"] == key)


def test_spa_shell_is_flagged(tmp_path: Path) -> None:
    f = tmp_path / "index.html"
    f.write_text(SPA_SHELL)
    rep = on_page.audit(str(f))
    assert rep["js_dependent"] is True
    js = _finding(rep, "js_rendering")
    assert js["ok"] is False and "JavaScript" in js["message"]
    assert rep["rendered"] is False


def test_server_rendered_page_passes(tmp_path: Path) -> None:
    f = tmp_path / "page.html"
    f.write_text(SAMPLE_HTML)
    rep = on_page.audit(str(f))
    assert rep["js_dependent"] is False
    assert _finding(rep, "js_rendering")["ok"] is True


def test_short_static_page_is_not_a_false_positive(tmp_path: Path) -> None:
    f = tmp_path / "short.html"
    f.write_text(
        "<html><body><p>This domain is for use in documentation examples without needing "
        "permission. This is not a service; avoid relying on it for testing.</p>"
        '<script src="/s.js"></script></body></html>'
    )
    assert on_page.audit(str(f))["js_dependent"] is False


def test_script_text_does_not_count_as_words(tmp_path: Path) -> None:
    f = tmp_path / "s.html"
    f.write_text("<html><body><div id='app'></div><script>" + "var a = 1; " * 500 + "</script>")
    rep = on_page.audit(str(f))
    assert rep["raw_word_count"] == 0
    assert rep["js_dependent"] is True


def test_render_uses_rendered_dom(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    f = tmp_path / "index.html"
    f.write_text(SPA_SHELL)
    monkeypatch.setattr(on_page, "_render_url", lambda url, timeout_s=None: SAMPLE_HTML)
    rep = on_page.audit(str(f), render=True)
    assert rep["rendered"] is True
    assert rep["word_count"] > rep["raw_word_count"]
    assert rep["js_dependent"] is True
    assert rep["score"] <= 50
    assert "words_with_js=" in _finding(rep, "js_rendering")["detail"]


def test_render_without_playwright_gives_install_hint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name.startswith("playwright"):
            raise ImportError("No module named 'playwright'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(on_page.RenderUnavailableError, match=r"geoseo-mcp\[render\]"):
        on_page._render_url("https://example.com")
