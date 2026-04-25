"""Smoke tests for the internal-link graph + suggestions."""

from __future__ import annotations

from geoseo_mcp.graph import internal_links

HTML_A = """<html><head>
<title>How to quit drinking alcohol</title>
<meta name="description" content="A practical guide to quitting drinking.">
</head><body>
<h1>Quit drinking guide</h1>
<a href="b.html">related</a>
</body></html>"""

HTML_B = """<html><head>
<title>Sober dating tips for early sobriety</title>
<meta name="description" content="How to date while sober.">
</head><body>
<h1>Sober dating</h1>
<a href="c.html">support meetings</a>
<a href="missing.html">missing</a>
</body></html>"""

HTML_C = """<html><head>
<title>AA meetings and what to expect</title>
<meta name="description" content="What to expect at your first AA meeting.">
</head><body>
<h1>AA meetings</h1>
<p>About sobriety and quit drinking and recovery support.</p>
</body></html>"""


def _seed(tmp_path):
    (tmp_path / "a.html").write_text(HTML_A)
    (tmp_path / "b.html").write_text(HTML_B)
    (tmp_path / "c.html").write_text(HTML_C)


def test_build_graph(tmp_path):
    _seed(tmp_path)
    g = internal_links.build(str(tmp_path))
    assert g["files"] == 3
    assert g["edges"] == 2  # a->b, b->c
    assert "a.html" in g["orphans"]
    assert "c.html" in g["dead_ends"]
    assert "missing.html" in g["dangling"]["b.html"]


def test_suggest_excludes_existing(tmp_path):
    _seed(tmp_path)
    res = internal_links.suggest(str(tmp_path), top_k=3)
    suggestions = res["suggestions"]
    a_suggested = {s["target"] for s in suggestions["a.html"]}
    assert "b.html" not in a_suggested
    assert "a.html" not in a_suggested
    assert "c.html" in a_suggested


def test_suggest_for_single_page(tmp_path):
    _seed(tmp_path)
    res = internal_links.suggest(str(tmp_path), page="c.html", top_k=2)
    assert list(res["suggestions"].keys()) == ["c.html"]
