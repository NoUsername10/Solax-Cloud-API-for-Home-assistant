"""Classify SolaX Cloud API response payloads."""

from __future__ import annotations

from typing import Any


def _exception_text(payload: dict[str, Any]) -> str:
    """Return a normalized API exception message."""
    return str(payload.get("exception", "")).strip().lower()


def is_token_invalid_response(payload: dict[str, Any]) -> bool:
    """Return whether a response indicates an invalid API token.

    SolaX documents code 1001 for unauthorized API access, while both the
    Global and India endpoints have also been observed returning code 103 with
    ``token invalid!``.
    """
    if not isinstance(payload, dict):
        return False

    if payload.get("code") in (103, 1001):
        return True

    exception = _exception_text(payload)
    return "token" in exception and "invalid" in exception


def is_data_unauthorized_response(payload: dict[str, Any]) -> bool:
    """Return whether a response indicates serial/data authorization failure."""
    if not isinstance(payload, dict):
        return False

    code = payload.get("code")
    if code == 1003:
        return True

    # The API can omit its documented 1003 code and return only ``no auth!``.
    # Token failures are classified separately as 1001/103 or ``token invalid``.
    return (
        payload.get("success") is False
        and code is None
        and "no auth" in _exception_text(payload)
    )
