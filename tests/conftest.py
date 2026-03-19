"""Shared fixtures and bootstrap for integration tests."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry


ROOT = Path(__file__).resolve().parents[1]
CUSTOM_COMPONENTS = ROOT / "custom_components"

if str(CUSTOM_COMPONENTS) not in sys.path:
    sys.path.insert(0, str(CUSTOM_COMPONENTS))

from solax_cloud_api.const import (  # noqa: E402
    CONF_ENTITY_PREFIX,
    CONF_INVERTERS,
    CONF_SCAN_INTERVAL,
    CONF_SYSTEM_NAME,
    CONF_TOKEN,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)


@pytest.fixture
def enable_custom_integrations() -> bool:
    """Enable loading this custom integration in HA test runtime."""
    return True


@pytest.fixture(autouse=True)
def _auto_enable_custom_integrations(enable_custom_integrations):
    """Apply custom integration loader patch for all tests."""
    return enable_custom_integrations


@pytest.fixture
def mock_solax_entry(hass) -> Callable[..., MockConfigEntry]:
    """Create and register a config entry for this integration."""

    def _factory(
        *,
        token: str = "token-123456",
        inverters: list[str] | None = None,
        system_name: str = "Test System",
        scan_interval: int = DEFAULT_SCAN_INTERVAL,
        entity_prefix: str = "test_system",
        options: dict | None = None,
        title: str | None = None,
    ) -> MockConfigEntry:
        entry = MockConfigEntry(
            domain=DOMAIN,
            title=title or system_name,
            data={
                CONF_TOKEN: token,
                CONF_INVERTERS: inverters or ["SERIAL1"],
                CONF_SCAN_INTERVAL: scan_interval,
                CONF_SYSTEM_NAME: system_name,
                CONF_ENTITY_PREFIX: entity_prefix,
            },
            options=options or {},
        )
        entry.add_to_hass(hass)
        return entry

    return _factory


@pytest.fixture
def payload_factory() -> Callable[..., dict]:
    """Build standard Solax payloads for tests."""

    def _factory(
        *,
        acpower: int | None = 900,
        bat_power: int | None = None,
        inverter_type: int = 1,
        upload_time: str = "2026-03-19 12:00:00",
        utc_datetime: str = "2026-03-19T12:00:00+00:00",
        extra: dict | None = None,
    ) -> dict:
        payload = {
            "inverterSN": "INV123456",
            "sn": "SERIAL1",
            "acpower": acpower,
            "yieldtoday": 4.2,
            "yieldtotal": 1234.5,
            "inverterType": inverter_type,
            "uploadTime": upload_time,
            "utcDateTime": utc_datetime,
            "batPower": bat_power,
            "powerdc1": 1000,
            "powerdc2": 1000,
            "powerdc3": None,
            "powerdc4": None,
        }
        if extra:
            payload.update(extra)
        return payload

    return _factory


@pytest.fixture
def runtime_coordinator_stub():
    """Build a lightweight coordinator-like object for options-flow tests."""

    def _factory(
        *,
        data: dict | None = None,
        rate_limited_inverters: list[str] | None = None,
        unauthorized_inverters: list[str] | None = None,
        unauthorized_details: dict | None = None,
    ):
        return SimpleNamespace(
            data=data or {},
            rate_limited_inverters=rate_limited_inverters or [],
            unauthorized_inverters=unauthorized_inverters or [],
            unauthorized_details=unauthorized_details or {},
        )

    return _factory
