"""Common types shared across engines."""

from __future__ import annotations


class EngineNotConfiguredError(RuntimeError):
    """Raised when a tool is invoked but its engine has no credentials.

    The message is shown to the user/LLM verbatim, so it must be actionable
    (which env var to set, where to get the credential).
    """

    def __init__(self, engine: str, hint: str) -> None:
        super().__init__(f"{engine} is not configured. {hint}")
        self.engine = engine
        self.hint = hint


class EngineError(RuntimeError):
    """Wraps an upstream API error with a user-readable message."""
