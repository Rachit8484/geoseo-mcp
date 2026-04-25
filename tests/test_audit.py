"""Smoke tests for the on-page audit (no network required)."""

from __future__ import annotations

from pathlib import Path

from geoseo_mcp.audit import on_page

SAMPLE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <title>How to Quit Drinking: A 30-Day Guide</title>
  <meta name="description" content="A practical, evidence-based 30-day guide to cutting alcohol, including a daily plan, common withdrawal symptoms, and when to seek medical help.">
  <link rel="canonical" href="https://example.com/quit-drinking">
  <meta property="og:title" content="How to Quit Drinking">
  <meta property="og:description" content="A 30-day guide.">
  <script type="application/ld+json">
  {"@context":"https://schema.org","@type":"Article","headline":"How to Quit Drinking",
   "author":{"@type":"Person","name":"Jane Doe"},
   "datePublished":"2026-04-01"}
  </script>
</head>
<body>
  <h1>How to Quit Drinking in 30 Days</h1>
  <h2>Day 1</h2>
  <p>Roughly 14% of US adults meet criteria for alcohol use disorder.</p>
  <p>The first 72 hours involve the highest risk of withdrawal symptoms.</p>
  <p>Most people see sleep improvements within 7 days.</p>
  <img src="x.jpg" alt="A clock counting down 30 days">
  <a href="/another">Internal link</a>
  <a href="https://nih.gov">External link</a>
</body>
</html>
"""


def test_audit_local_file(tmp_path: Path) -> None:
    f = tmp_path / "page.html"
    f.write_text(SAMPLE_HTML)

    result = on_page.audit(str(f))

    assert result["title"] == "How to Quit Drinking: A 30-Day Guide"
    assert 10 <= result["title_length"] <= 70
    assert result["meta_description_length"] >= 70
    assert result["h1"] == ["How to Quit Drinking in 30 Days"]
    assert result["schema_blocks"] == 1
    assert "Article" in result["schema_types"]
    assert result["internal_links"] >= 1
    assert result["external_links"] >= 1
    assert result["images_missing_alt"] == 0
    assert result["has_article_schema"] is True
    assert result["has_published_date"] is True
    assert result["quotable_sentences"] >= 1
    assert 50 <= result["score"] <= 100


def test_audit_minimal_page_has_warnings(tmp_path: Path) -> None:
    f = tmp_path / "thin.html"
    f.write_text("<html><body><p>Hi</p></body></html>")
    result = on_page.audit(str(f))

    assert result["score"] < 30
    keys = {x["key"] for x in result["findings"] if not x["ok"]}
    assert {"title", "meta_description", "h1", "word_count", "schema"} <= keys
