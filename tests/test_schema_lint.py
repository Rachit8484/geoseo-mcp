"""Schema linter tests against small real-world-style fixtures."""

from __future__ import annotations

from pathlib import Path

from geoseo_mcp.audit import schema_lint

FIX = Path(__file__).parent / "fixtures" / "schema"


def _by_type(report):
    return {b["type"]: b for b in report["blocks"] if isinstance(b.get("type"), str)}


def test_article_missing_author_is_recommended_not_required():
    rep = schema_lint.lint(str(FIX / "article_no_author.html"))
    art = _by_type(rep)["BlogPosting"]
    assert art["rule"] == "Article"
    assert art["ok"] is True
    assert "author" in art["recommended_missing"]
    assert "dateModified" in art["recommended_missing"]
    assert art["line_estimate"] == 4


def test_product_requires_offer_review_or_rating_and_nested_checks():
    rep = schema_lint.lint(str(FIX / "product_graph.html"))
    products = [b for b in rep["blocks"] if b["type"] == "Product"]
    graph_product, bundle = products
    assert graph_product["ok"] is False
    assert graph_product["required_missing"] == ["review | aggregateRating | offers (one of)"]
    # second block: offers present but no price; rating present but no count
    assert set(bundle["required_missing"]) == {
        "offers.price",
        "aggregateRating.ratingCount | reviewCount (one of)",
    }
    crumbs = _by_type(rep)["BreadcrumbList"]
    # middle crumb is missing item, last crumb is allowed to omit it
    assert crumbs["required_missing"] == ["itemListElement[1].item"]
    assert _by_type(rep)["Organization"]["ok"] is True
    assert rep["ok"] is False


def test_faq_accepted_answer_recipe_and_invalid_json():
    rep = schema_lint.lint(str(FIX / "faq_recipe.html"))
    faq = _by_type(rep)["FAQPage"]
    assert faq["required_missing"] == ["mainEntity[1].acceptedAnswer"]
    assert "no longer" in faq["note"]
    recipe = _by_type(rep)["Recipe"]
    assert recipe["ok"] is True
    assert "recipeIngredient" in recipe["recommended_missing"]
    assert "recipeInstructions" not in recipe["recommended_missing"]
    broken = [b for b in rep["blocks"] if b.get("error")]
    assert len(broken) == 1 and "invalid JSON" in broken[0]["error"]


def test_local_business_subtype_and_unknown_type():
    rep = schema_lint.lint(str(FIX / "clean.html"))
    assert rep["ok"] is True
    rest = _by_type(rep)["Restaurant"]
    assert rest["rule"] == "LocalBusiness" and rest["required_missing"] == []
    assert _by_type(rep)["WebSite"]["rule"] is None


def test_lint_folder_summary():
    out = schema_lint.lint_folder(str(FIX))
    assert out["files_scanned"] == 4
    assert out["files_with_errors"] == 2
    issues = {i["issue"] for i in out["most_common_missing"]}
    assert "Product: review | aggregateRating | offers (one of)" in issues
    assert "FAQPage: mainEntity[1].acceptedAnswer" in issues


def test_job_posting_telecommute_and_missing_fields():
    html = """<script type="application/ld+json">{"@type":"JobPosting","title":"Engineer",
    "description":"x","datePosted":"2026-10-01","hiringOrganization":{"name":"Acme"},
    "jobLocationType":"TELECOMMUTE"}</script>"""
    (block,) = schema_lint.lint_html(html)
    assert block["required_missing"] == ["applicantLocationRequirements"]


def test_nodes_sharing_id_are_merged():
    html = """
    <script type="application/ld+json">{"@type":"Recipe","@id":"https://x.test/#r",
      "name":"Loaf","image":"https://x.test/a.jpg"}</script>
    <script type="application/ld+json">{"@id":"https://x.test/#r",
      "aggregateRating":{"@type":"AggregateRating","ratingValue":4.5}}</script>"""
    blocks = schema_lint.lint_html(html)
    assert len(blocks) == 1
    assert blocks[0]["required_missing"] == [
        "aggregateRating.ratingCount | reviewCount (one of)"
    ]
