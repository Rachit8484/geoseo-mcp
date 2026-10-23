"""Domain normalization + matching shared by every citation engine.

Citation checks used to require an exact host match, so a citation of
``blog.example.com`` didn't count for ``example.com``. Everything now goes
through ``matches_domain`` which treats subdomains as belonging to the target.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse


def normalize_domain(value: str) -> str:
    """``https://www.Example.com:443/path`` -> ``example.com``."""
    value = (value or "").strip().lower()
    if not value:
        return ""
    value = urlparse(value).netloc if "://" in value else value.split("/", 1)[0]
    value = value.rsplit("@", 1)[-1]  # strip userinfo
    value = value.split(":", 1)[0]  # strip port
    value = value.rstrip(".")
    return value[4:] if value.startswith("www.") else value


def domain_of(url: str) -> str:
    try:
        return normalize_domain(url)
    except Exception:
        return url


def matches_domain(host: str, target: str) -> bool:
    """True if ``host`` is ``target`` or any subdomain of it."""
    host = normalize_domain(host)
    target = normalize_domain(target)
    if not host or not target:
        return False
    return host == target or host.endswith("." + target)


def any_match(hosts: list[str], target: str) -> bool:
    return any(matches_domain(h, target) for h in hosts)


# Second-level labels that are part of a public suffix (co.uk, com.au, ...).
_SECOND_LEVEL = {"co", "com", "net", "org", "gov", "ac", "edu"}


def brand_from_domain(target: str) -> str:
    """Best-effort brand label: ``app.minemedata.com`` -> ``minemedata``."""
    parts = normalize_domain(target).split(".")
    if len(parts) >= 3 and parts[-2] in _SECOND_LEVEL and len(parts[-1]) == 2:
        return parts[-3]
    if len(parts) >= 2:
        return parts[-2]
    return parts[0] if parts else ""


def default_aliases(target: str, extra: list[str] | None = None) -> list[str]:
    target = normalize_domain(target)
    aliases = [target]
    brand = brand_from_domain(target)
    # Very short labels ("ai", "x") produce too many false positives.
    if brand and len(brand) >= 4:
        aliases.append(brand)
    for a in extra or []:
        a = a.strip()
        if a and a.lower() not in {x.lower() for x in aliases}:
            aliases.append(a)
    return aliases


def find_mentions(text: str, aliases: list[str]) -> list[str]:
    """Return the aliases that appear in ``text`` as whole words (case-insensitive)."""
    if not text:
        return []
    found: list[str] = []
    for alias in aliases:
        pattern = r"(?<![\w.-])" + re.escape(alias) + r"(?![\w-])"
        if re.search(pattern, text, flags=re.IGNORECASE):
            found.append(alias)
    return found
