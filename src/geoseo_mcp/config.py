"""Runtime configuration loaded from environment variables.

All credentials are optional. Tools whose engine is unconfigured raise a clear
error at call time rather than failing at import.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from platformdirs import user_data_dir

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
    perplexity_model: str
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
            perplexity_model=os.getenv("GEOSEO_PERPLEXITY_MODEL", "sonar"),
            user_agent=os.getenv(
                "GEOSEO_USER_AGENT",
                "geoseo-mcp/0.1 (+https://github.com/your-org/geoseo-mcp)",
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
