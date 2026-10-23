from __future__ import annotations

import pytest

from geoseo_mcp.engines._domains import (
    brand_from_domain,
    default_aliases,
    domain_of,
    find_mentions,
    matches_domain,
    normalize_domain,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://www.Example.com:443/a?b=1", "example.com"),
        ("example.com/path", "example.com"),
        ("WWW.example.com.", "example.com"),
        ("https://user@blog.example.com", "blog.example.com"),
        ("", ""),
    ],
)
def test_normalize_domain(raw: str, expected: str) -> None:
    assert normalize_domain(raw) == expected


def test_subdomains_match_but_lookalikes_do_not() -> None:
    assert matches_domain("blog.example.com", "example.com")
    assert matches_domain("https://docs.example.com/x", "https://www.example.com")
    assert matches_domain("example.com", "example.com")
    assert not matches_domain("notexample.com", "example.com")
    assert not matches_domain("example.com.evil.io", "example.com")
    assert not matches_domain("example.com", "blog.example.com")


def test_brand_from_domain() -> None:
    assert brand_from_domain("app.minemedata.com") == "minemedata"
    assert brand_from_domain("bbc.co.uk") == "bbc"
    assert brand_from_domain("localhost") == "localhost"


def test_default_aliases_skips_short_brand_and_dedupes() -> None:
    assert default_aliases("x.ai") == ["x.ai"]
    assert default_aliases("acme.com", ["Acme", "Acme CRM"]) == ["acme.com", "acme", "Acme CRM"]


def test_find_mentions_whole_word_only() -> None:
    aliases = ["acme.com", "acme"]
    assert find_mentions("Try Acme for this.", aliases) == ["acme"]
    assert find_mentions("See acme.com.", aliases) == ["acme.com", "acme"]
    assert find_mentions("acmeflow is different", aliases) == []
    assert find_mentions("", aliases) == []


def test_domain_of_never_raises() -> None:
    assert domain_of("not a url") == "not a url"
