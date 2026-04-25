"""Google OAuth helper for Search Console (and later, Indexing API).

Uses installed-app flow. Token is cached to disk at the path configured by
``GEOSEO_GOOGLE_TOKEN`` (default: platform user-data dir). The MCP runs in a
non-interactive subprocess, so we run the OAuth consent flow only when no
cached token exists, using ``run_local_server`` which briefly opens a browser
on the user's machine.
"""

from __future__ import annotations

from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from ..config import get_config
from ..engines.base import EngineNotConfiguredError

GSC_SCOPES = [
    "https://www.googleapis.com/auth/webmasters.readonly",
    "https://www.googleapis.com/auth/webmasters",
]


def get_credentials(scopes: list[str] | None = None) -> Credentials:
    """Return valid Google credentials, running OAuth flow if needed."""
    cfg = get_config()
    if cfg.google_client_secret is None:
        raise EngineNotConfiguredError(
            "google_search_console",
            "Set GEOSEO_GOOGLE_CLIENT_SECRET to the path of your OAuth "
            "client_secret.json. See docs/setup-gsc.md.",
        )

    scopes = scopes or GSC_SCOPES
    token_path: Path = cfg.google_token_path
    creds: Credentials | None = None

    if token_path.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(token_path), scopes)
        except ValueError:
            creds = None

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_path.write_text(creds.to_json())
        return creds

    flow = InstalledAppFlow.from_client_secrets_file(str(cfg.google_client_secret), scopes)
    creds = flow.run_local_server(port=0, prompt="consent")
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json())
    return creds
