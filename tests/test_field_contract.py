"""Field-contract tests for supported Solax API result fields."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock

import pytest
from homeassistant.util import dt as dt_util

from solax_cloud_api import sensor as sensor_platform
from solax_cloud_api.const import DOMAIN, RESULT_FIELDS
from solax_cloud_api.coordinator import SolaxCoordinator


def _full_result_payload(serial: str = "SERIAL1") -> dict:
    """Return a full non-null Solax payload that includes every supported result field."""
    return {
        "inverterSN": "INV123456789",
        "sn": serial,
        "acpower": 900,
        "yieldtoday": 4.2,
        "yieldtotal": 1234.5,
        "feedinpower": 120,
        "feedinenergy": 654.3,
        "consumeenergy": 321.1,
        "feedinpowerM2": 95,
        "soc": 56,
        "peps1": 100,
        "peps2": 110,
        "peps3": 90,
        "inverterType": 1,
        "inverterStatus": 2,
        "uploadTime": "2026-03-19 12:00:00",
        "utcDateTime": "2026-03-19T12:00:00+00:00",
        "batPower": -120,
        "powerdc1": 300,
        "powerdc2": 250,
        "powerdc3": 200,
        "powerdc4": 150,
        "batStatus": 1,
    }


def _minimal_entity_translations() -> dict[str, str]:
    """Return enough translation keys to avoid local translation-file fallback in tests."""
    return {
        "component.solax_cloud_api.entity.sensor.api_access_status.name": "API Access Status",
        "component.solax_cloud_api.entity.sensor.inverter_type.state.1": "X1-LX",
        "component.solax_cloud_api.entity.sensor.inverter_status.state.2": "Running",
        "component.solax_cloud_api.entity.sensor.bat_status.state.1": "Charging",
    }


class _FakeCoordinator:
    """Minimal coordinator protocol for CoordinatorEntity usage in tests."""

    def __init__(self, data: dict[str, dict]):
        self.data = data
        self.last_update_success = True
        self.rate_limited_inverters = []
        self.rate_limited_details = {}
        self.unauthorized_inverters = []
        self.unauthorized_details = {}
        self.last_rate_limit_at = None
        self.last_update_attempt = None
        self.last_successful_update = None
        self.update_interval = timedelta(seconds=120)
        self._listeners = []

    def async_add_listener(self, update_callback, _context=None):
        self._listeners.append(update_callback)

        def _remove():
            if update_callback in self._listeners:
                self._listeners.remove(update_callback)

        return _remove


@pytest.fixture(autouse=True)
def _patch_client_session(monkeypatch):
    """Avoid creating real aiohttp sessions in coordinator tests."""
    monkeypatch.setattr(
        "solax_cloud_api.coordinator.async_get_clientsession",
        lambda _hass: object(),
    )


@pytest.mark.asyncio
async def test_coordinator_keeps_every_supported_result_field_when_non_null(hass):
    """Coordinator should retain all declared RESULT_FIELDS when API values are non-null."""
    serial = "SERIAL1"
    coordinator = SolaxCoordinator(hass, "token", [serial], 120)
    coordinator._fetch_one = AsyncMock(
        return_value={
            "success": True,
            "code": 0,
            "exception": "operation success",
            "result": _full_result_payload(serial),
        }
    )

    data = await coordinator._async_update_data()
    assert set(data[serial].keys()) == set(RESULT_FIELDS)


@pytest.mark.asyncio
async def test_entity_setup_creates_field_sensor_for_every_supported_result_field(
    hass, mock_solax_entry, monkeypatch
):
    """A complete API payload should produce one SolaxFieldSensor per supported result field."""
    serial = "SERIAL1"
    entry = mock_solax_entry(inverters=[serial], entity_prefix="contract_system")
    coordinator = _FakeCoordinator({serial: _full_result_payload(serial)})
    coordinator.last_update_attempt = dt_util.utcnow()
    coordinator.last_successful_update = dt_util.utcnow()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {"coordinator": coordinator}
    monkeypatch.setattr(
        sensor_platform,
        "async_get_translations",
        AsyncMock(return_value=_minimal_entity_translations()),
    )

    added = []

    def _add_entities(entities, update_before_add=False):
        added.extend(entities)

    await sensor_platform.async_setup_entry(hass, entry, _add_entities)

    field_entities = [
        entity for entity in added if isinstance(entity, sensor_platform.SolaxFieldSensor)
    ]
    assert len(field_entities) == len(RESULT_FIELDS)

    by_field = {entity._field: entity for entity in field_entities}
    assert set(by_field.keys()) == set(RESULT_FIELDS)
    assert all(entity.available for entity in field_entities)
    assert all(entity.native_value is not None for entity in field_entities)

    # Spot-check mapped fields resolve to translated state text.
    assert by_field["inverterType"].native_value == "X1-LX"
    assert by_field["inverterStatus"].native_value == "Running"
    assert by_field["batStatus"].native_value == "Charging"
