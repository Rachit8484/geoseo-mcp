"""Shared fixtures. Nothing here touches the network."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator

import httpx
import pytest

from geoseo_mcp import config

_ENV_PREFIX = "GEOSEO_"


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch, tmp_path) -> Iterator[None]:
    """Every test starts with no credentials and a throwaway DB."""
    import os

    for k in list(os.environ):
        if k.startswith(_ENV_PREFIX):
            monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("GEOSEO_DB", str(tmp_path / "geoseo.sqlite"))
    config.reset_config()
    yield
    config.reset_config()


@pytest.fixture
def set_env(monkeypatch: pytest.MonkeyPatch) -> Callable[..., None]:
    def _set(**env: str) -> None:
        for k, v in env.items():
            monkeypatch.setenv(k, v)
        config.reset_config()

    return _set


Handler = Callable[[httpx.Request], httpx.Response]


@pytest.fixture
def mock_http(monkeypatch: pytest.MonkeyPatch) -> Callable[[Handler], list[httpx.Request]]:
    """Route every ``httpx.Client`` through ``handler``. Returns the request log."""
    real_client = httpx.Client

    def install(handler: Handler) -> list[httpx.Request]:
        seen: list[httpx.Request] = []

        def wrapped(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return handler(request)

        def factory(*args, **kwargs):
            kwargs.pop("transport", None)
            return real_client(*args, transport=httpx.MockTransport(wrapped), **kwargs)

        monkeypatch.setattr(httpx, "Client", factory)
        return seen

    return install


def body(request: httpx.Request) -> dict:
    return json.loads(request.content or b"{}")
