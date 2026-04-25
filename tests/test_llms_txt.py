"""Tests for the llms.txt generator + validator (no network)."""

from __future__ import annotations

from pathlib import Path

from geoseo_mcp.audit import llms_txt

INDEX_HTML = """<!DOCTYPE html><html><head>
<title>Soberpath: Quit Drinking, Stay Sober</title>
<meta name="description" content="Free sobriety counter, daily check-ins, and a community for people quitting alcohol.">
</head><body><h1>Soberpath</h1></body></html>"""

BLOG_HTML = """<!DOCTYPE html><html><head>
<title>How to Quit Drinking</title>
<meta name="description" content="Evidence-based 30-day plan.">
</head><body><h1>Quit</h1></body></html>"""


def test_generate_groups_by_first_path_segment(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text(INDEX_HTML)
    blog_dir = tmp_path / "blog"
    blog_dir.mkdir()
    (blog_dir / "quit-drinking.html").write_text(BLOG_HTML)

    result = llms_txt.generate(
        folder=str(tmp_path),
        site_url="https://soberpathapp.com",
        site_title="Soberpath",
        site_summary="Quit drinking, stay sober.",
    )

    assert "error" not in result
    content = result["content"]
    assert content.startswith("# Soberpath\n")
    assert "> Quit drinking, stay sober." in content
    assert "## Blog" in content
    assert "[How to Quit Drinking](https://soberpathapp.com/blog/quit-drinking)" in content
    assert result["entry_count"] == 2


def test_validate_clean_file(tmp_path: Path) -> None:
    f = tmp_path / "llms.txt"
    f.write_text(
        "# Soberpath\n\n> Quit drinking, stay sober.\n\n"
        "## Blog\n\n- [Quit Drinking](https://soberpathapp.com/blog/quit-drinking): A 30-day plan.\n"
    )
    result = llms_txt.validate(str(f))
    assert result["ok"] is True
    assert result["title"] == "Soberpath"
    assert result["section_count"] == 1
    assert result["link_count"] == 1
    assert result["issues"] == []


def test_validate_missing_h1(tmp_path: Path) -> None:
    f = tmp_path / "llms.txt"
    f.write_text("Soberpath\n\n## Blog\n- [x](https://x.com)\n")
    result = llms_txt.validate(str(f))
    assert result["ok"] is False
    assert any("H1" in i["message"] for i in result["issues"])


def test_validate_non_http_url(tmp_path: Path) -> None:
    f = tmp_path / "llms.txt"
    f.write_text("# Site\n\n## Blog\n- [Mail](mailto:hi@example.com)\n")
    result = llms_txt.validate(str(f))
    assert result["ok"] is False
    assert any("Non-http" in i["message"] for i in result["issues"])
