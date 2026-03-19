"""Sensor entity setup and behavior tests."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock

import pytest
from homeassistant.util import dt as dt_util

from solax_cloud_api import sensor as sensor_platform
from solax_cloud_api.const import DOMAIN


def _minimal_entity_translations() -> dict[str, str]:
    """Return enough translation keys to skip local-file fallback in tests."""
    return {
        "component.solax_cloud_api.entity.sensor.inverter_type.state.1": "X1-LX",
        "component.solax_cloud_api.entity.sensor.api_access_status.name": "API Access Status",
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


@pytest.mark.asyncio
async def test_sensor_setup_creates_api_status_and_system_totals(
    hass, mock_solax_entry, monkeypatch, payload_factory
):
    """API status should always exist and system totals should be created."""
    entry = mock_solax_entry(inverters=["SERIAL1"], entity_prefix="test_system")
    coordinator = _FakeCoordinator(
        {"SERIAL1": payload_factory(acpower=None, extra={"batPower": None})}
    )
    coordinator.last_update_attempt = dt_util.utcnow()
    coordinator.last_successful_update = dt_util.utcnow() - timedelta(seconds=10)
    coordinator.unauthorized_inverters = ["SERIAL1"]

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

    api_status_entities = [
        entity
        for entity in added
        if isinstance(entity, sensor_platform.SolaxInverterApiAccessStatusSensor)
    ]
    assert len(api_status_entities) == 1
    assert api_status_entities[0]._status_key() == "serial_unauthorized"

    system_total_entities = [
        entity
        for entity in added
        if isinstance(entity, sensor_platform.SolaxSystemTotalSensor)
    ]
    assert len(system_total_entities) == 9


@pytest.mark.asyncio
async def test_null_only_payload_does_not_create_field_sensors(
    hass, mock_solax_entry, monkeypatch
):
    """Null-only API values should not create normal field sensors."""
    entry = mock_solax_entry(inverters=["SERIAL1"], entity_prefix="null_system")
    coordinator = _FakeCoordinator(
        {
            "SERIAL1": {
                "acpower": None,
                "yieldtoday": None,
                "yieldtotal": None,
                "powerdc1": None,
                "powerdc2": None,
                "powerdc3": None,
                "powerdc4": None,
                "batPower": None,
            }
        }
    )
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
    assert field_entities == []


@pytest.mark.asyncio
async def test_estimated_battery_sensors_only_created_when_batpower_exists(
    hass, mock_solax_entry, monkeypatch, payload_factory
):
    """Estimated battery entities should only appear with valid batPower data."""
    entry = mock_solax_entry(inverters=["SERIAL1"], entity_prefix="battery_system")
    coordinator = _FakeCoordinator({"SERIAL1": payload_factory(bat_power=120)})
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

    inverter_estimated = [
        entity
        for entity in added
        if isinstance(entity, sensor_platform.SolaxEstimatedBatteryEnergySensor)
    ]
    system_estimated = [
        entity
        for entity in added
        if isinstance(entity, sensor_platform.SolaxSystemEstimatedBatteryEnergySensor)
    ]

    assert len(inverter_estimated) == 4
    assert len(system_estimated) == 4
    assert all(entity.entity_registry_enabled_default is False for entity in inverter_estimated)
    assert all(entity.entity_registry_enabled_default is False for entity in system_estimated)
