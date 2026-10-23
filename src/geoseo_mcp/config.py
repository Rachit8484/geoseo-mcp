"""Runtime configuration loaded from environment variables.

All credentials are optional. Tools whose engine is unconfigured raise a clear
error at call time rather than failing at import.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from platformdirs import user_data_dir

from . import __version__

APP_NAME = "geoseo-mcp"


def _data_dir() -> Path:
    path = Path(user_data_dir(APP_NAME, appauthor=False))
    path.mkdir(parents=True, exist_ok=True)
    return path


@dataclass(frozen=True)
class Config:
    google_client_secret: Path | None
    google_token_path: Path
    indexnow_key: str | None
    indexnow_key_location: str | None
    perplexity_api_key: str | None
    perplexity_model: str | None
    perplexity_effort: str
    openai_api_key: str | None
    openai_model: str
    anthropic_api_key: str | None
    anthropic_model: str
    gemini_api_key: str | None
    gemini_model: str
    grok_api_key: str | None
    grok_model: str
    brave_api_key: str | None
    serpapi_api_key: str | None
    bing_webmaster_api_key: str | None
    citation_samples: int
    max_concurrency: int
    yandex_oauth_token: str | None
    user_agent: str
    request_timeout_s: float
    data_dir: Path

    @classmethod
    def from_env(cls) -> Config:
        data_dir = _data_dir()
        client_secret = os.getenv("GEOSEO_GOOGLE_CLIENT_SECRET")
        return cls(
            google_client_secret=Path(client_secret) if client_secret else None,
            google_token_path=Path(
                os.getenv("GEOSEO_GOOGLE_TOKEN", str(data_dir / "gsc_token.json"))
            ),
            indexnow_key=os.getenv("GEOSEO_INDEXNOW_KEY"),
            indexnow_key_location=os.getenv("GEOSEO_INDEXNOW_KEY_LOCATION"),
            perplexity_api_key=os.getenv("GEOSEO_PERPLEXITY_API_KEY"),
            perplexity_model=os.getenv("GEOSEO_PERPLEXITY_MODEL") or None,
            perplexity_effort=os.getenv("GEOSEO_PERPLEXITY_EFFORT", "fast"),
            openai_api_key=os.getenv("GEOSEO_OPENAI_API_KEY"),
            openai_model=os.getenv("GEOSEO_OPENAI_MODEL", "gpt-5-mini"),
            anthropic_api_key=os.getenv("GEOSEO_ANTHROPIC_API_KEY"),
            anthropic_model=os.getenv("GEOSEO_ANTHROPIC_MODEL", "claude-sonnet-5-5"),
            gemini_api_key=os.getenv("GEOSEO_GEMINI_API_KEY"),
            gemini_model=os.getenv("GEOSEO_GEMINI_MODEL", "gemini-3.5-flash-lite"),
            grok_api_key=os.getenv("GEOSEO_XAI_API_KEY") or os.getenv("GEOSEO_GROK_API_KEY"),
            grok_model=os.getenv("GEOSEO_GROK_MODEL", "grok-4.3"),
            brave_api_key=os.getenv("GEOSEO_BRAVE_API_KEY"),
            serpapi_api_key=os.getenv("GEOSEO_SERPAPI_API_KEY"),
            bing_webmaster_api_key=os.getenv("GEOSEO_BING_WEBMASTER_API_KEY"),
            citation_samples=int(os.getenv("GEOSEO_CITATION_SAMPLES", "3")),
            max_concurrency=int(os.getenv("GEOSEO_MAX_CONCURRENCY", "8")),
            yandex_oauth_token=os.getenv("GEOSEO_YANDEX_OAUTH_TOKEN"),
            user_agent=os.getenv(
                "GEOSEO_USER_AGENT",
                f"geoseo-mcp/{__version__} (+https://github.com/Rachit8484/geoseo-mcp)",
            ),
            request_timeout_s=float(os.getenv("GEOSEO_TIMEOUT_S", "30")),
            data_dir=data_dir,
        )


_cached: Config | None = None


def get_config() -> Config:
    global _cached
    if _cached is None:
        _cached = Config.from_env()
    return _cached


def reset_config() -> None:
    """Drop the cached config (tests, or after changing env vars at runtime)."""
    global _cached
    _cached = None
