"""Basic smoke tests for the Solax Cloud API integration."""

from importlib import import_module
import sys

import pytest


def _load_symbols():
    if sys.version_info < (3, 10):
        pytest.skip("Integration imports require Python 3.10+.")
    const = import_module("solax_cloud_api.const")
    config_flow = import_module("solax_cloud_api.config_flow")
    coordinator = import_module("solax_cloud_api.coordinator")
    return (
        const,
        config_flow._is_rate_limited_payload,
        config_flow._slugify_name,
        coordinator._is_rate_limited_response,
    )


def test_pytest_smoke_runs():
    """Ensure pytest is collecting/running tests in CI."""
    assert True


def test_domain_constant():
    """Sanity check that core constants are importable."""
    const, _, _, _ = _load_symbols()
    assert const.DOMAIN == "solax_cloud_api"


def test_slugify_name_fallback():
    """Ensure invalid system names still produce a safe slug."""
    const, _, _slugify_name, _ = _load_symbols()
    assert _slugify_name("###") == const.DEFAULT_ENTITY_PREFIX
    assert _slugify_name("My Solax System") == "my_solax_system"


def test_rate_limit_detection_from_response():
    """Coordinator should detect known Solax rate-limit signals."""
    _, _, _, _is_rate_limited_response = _load_symbols()
    assert _is_rate_limited_response({"code": 104})
    assert _is_rate_limited_response({"code": 3})
    assert _is_rate_limited_response(
        {"code": 999, "exception": "Request calls within the current minute > threshold"}
    )
    assert not _is_rate_limited_response({"code": 0, "success": True})


def test_rate_limit_detection_from_preflight_payload():
    """Config flow preflight should classify known rate-limit payloads."""
    _, _is_rate_limited_payload, _, _ = _load_symbols()
    assert _is_rate_limited_payload({"code": 104})
    assert _is_rate_limited_payload({"code": 3})
    assert _is_rate_limited_payload(
        {"exception": "Accumulated 3 requests within 5 minutes exceed the maximum call threshold"}
    )
    assert not _is_rate_limited_payload({"code": 0, "success": True})
