"""Sensor entity setup and behavior tests."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock

import pytest
from homeassistant.components.sensor import SensorStateClass
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
    assert not any(
        isinstance(
            entity,
            (
                sensor_platform.SolaxEstimatedBatteryEnergySensor,
                sensor_platform.SolaxSystemEstimatedBatteryEnergySensor,
            ),
        )
        for entity in added
    )


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
    assert all(entity.entity_registry_enabled_default is True for entity in inverter_estimated)
    assert all(entity.entity_registry_enabled_default is True for entity in system_estimated)

    inverter_daily = [entity for entity in inverter_estimated if entity._period == "today"]
    inverter_total = [entity for entity in inverter_estimated if entity._period == "total"]
    system_daily = [entity for entity in system_estimated if entity._period == "today"]
    system_total = [entity for entity in system_estimated if entity._period == "total"]

    assert all(entity.state_class is SensorStateClass.TOTAL for entity in inverter_daily)
    assert all(entity.state_class is SensorStateClass.TOTAL_INCREASING for entity in inverter_total)
    assert all(entity.state_class is SensorStateClass.TOTAL for entity in system_daily)
    assert all(entity.state_class is SensorStateClass.TOTAL_INCREASING for entity in system_total)

    # Trigger computation once so daily sensors initialize their reset boundary.
    for entity in inverter_daily + system_daily:
        _ = entity.native_value

    assert all(entity.last_reset is not None for entity in inverter_daily)
    assert all(entity.last_reset is not None for entity in system_daily)
    assert all(entity.last_reset is None for entity in inverter_total)
    assert all(entity.last_reset is None for entity in system_total)


@pytest.mark.asyncio
async def test_yieldtoday_and_yieldtotal_energy_metadata_are_statistics_safe(
    hass, mock_solax_entry, monkeypatch, payload_factory
):
    """yieldtoday should be daily-total with reset, while yieldtotal stays total_increasing."""
    serial = "SERIAL1"
    entry = mock_solax_entry(inverters=[serial], entity_prefix="yield_meta")
    coordinator = _FakeCoordinator({serial: payload_factory()})
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

    yieldtoday_field = next(
        entity
        for entity in added
        if isinstance(entity, sensor_platform.SolaxFieldSensor) and entity._field == "yieldtoday"
    )
    yieldtotal_field = next(
        entity
        for entity in added
        if isinstance(entity, sensor_platform.SolaxFieldSensor) and entity._field == "yieldtotal"
    )
    yieldtoday_total = next(
        entity
        for entity in added
        if isinstance(entity, sensor_platform.SolaxSystemTotalSensor)
        and entity._metric == "yieldtoday_total"
    )
    yieldtotal_total = next(
        entity
        for entity in added
        if isinstance(entity, sensor_platform.SolaxSystemTotalSensor)
        and entity._metric == "yieldtotal_total"
    )

    assert yieldtoday_field.state_class is SensorStateClass.TOTAL
    assert yieldtotal_field.state_class is SensorStateClass.TOTAL_INCREASING
    assert yieldtoday_total.state_class is SensorStateClass.TOTAL
    assert yieldtotal_total.state_class is SensorStateClass.TOTAL_INCREASING

    assert yieldtoday_field.last_reset is not None
    assert yieldtotal_field.last_reset is None
    assert yieldtoday_total.last_reset is not None
    assert yieldtotal_total.last_reset is None


@pytest.mark.asyncio
async def test_estimated_total_battery_energy_does_not_reset_on_new_day(
    hass, mock_solax_entry, monkeypatch, payload_factory
):
    """Estimated total battery energy must keep increasing across day boundaries."""
    serial = "SERIAL1"
    entry = mock_solax_entry(inverters=[serial], entity_prefix="battery_rollover")
    coordinator = _FakeCoordinator(
        {
            serial: payload_factory(
                bat_power=100,
                upload_time="2026-03-19 10:00:00",
                utc_datetime="2026-03-19T10:00:00+00:00",
            )
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

    inverter_total_charge = next(
        entity
        for entity in added
        if isinstance(entity, sensor_platform.SolaxEstimatedBatteryEnergySensor)
        and entity._period == "total"
        and entity._direction == "charge"
    )
    system_total_charge = next(
        entity
        for entity in added
        if isinstance(entity, sensor_platform.SolaxSystemEstimatedBatteryEnergySensor)
        and entity._period == "total"
        and entity._direction == "charge"
    )

    first_inverter_total = inverter_total_charge.native_value
    first_system_total = system_total_charge.native_value

    # Advance to the next local day and provide a new sample.
    coordinator.data[serial] = payload_factory(
        bat_power=100,
        upload_time="2026-03-20 10:05:00",
        utc_datetime="2026-03-20T10:05:00+00:00",
    )

    second_inverter_total = inverter_total_charge.native_value
    second_system_total = system_total_charge.native_value

    assert first_inverter_total == 0
    assert first_system_total == 0
    assert second_inverter_total is not None and second_inverter_total > first_inverter_total
    assert second_system_total is not None and second_system_total > first_system_total


@pytest.mark.asyncio
async def test_estimated_daily_battery_energy_rolls_over_on_new_day(
    hass, mock_solax_entry, monkeypatch, payload_factory
):
    """Estimated daily battery energy should reset at day rollover."""
    tz = dt_util.DEFAULT_TIME_ZONE

    def _payload_for_local_dt(year, month, day, hour, minute):
        local_dt = dt_util.now().replace(
            year=year,
            month=month,
            day=day,
            hour=hour,
            minute=minute,
            second=0,
            microsecond=0,
        )
        # Use the active HA local timezone for both timestamps so rollover logic is deterministic.
        local_dt = local_dt.astimezone(tz)
        return payload_factory(
            bat_power=100,
            upload_time=local_dt.strftime("%Y-%m-%d %H:%M:%S"),
            utc_datetime=local_dt.isoformat(),
        )

    serial = "SERIAL1"
    entry = mock_solax_entry(inverters=[serial], entity_prefix="battery_daily_rollover")
    coordinator = _FakeCoordinator({serial: _payload_for_local_dt(2026, 3, 19, 23, 45)})
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

    inverter_daily_charge = next(
        entity
        for entity in added
        if isinstance(entity, sensor_platform.SolaxEstimatedBatteryEnergySensor)
        and entity._period == "today"
        and entity._direction == "charge"
    )
    system_daily_charge = next(
        entity
        for entity in added
        if isinstance(entity, sensor_platform.SolaxSystemEstimatedBatteryEnergySensor)
        and entity._period == "today"
        and entity._direction == "charge"
    )

    _ = inverter_daily_charge.native_value
    _ = system_daily_charge.native_value

    coordinator.data[serial] = _payload_for_local_dt(2026, 3, 19, 23, 50)
    day1_mid_inverter = inverter_daily_charge.native_value
    day1_mid_system = system_daily_charge.native_value

    coordinator.data[serial] = _payload_for_local_dt(2026, 3, 19, 23, 55)
    day1_end_inverter = inverter_daily_charge.native_value
    day1_end_system = system_daily_charge.native_value

    coordinator.data[serial] = _payload_for_local_dt(2026, 3, 20, 0, 0)
    day2_start_inverter = inverter_daily_charge.native_value
    day2_start_system = system_daily_charge.native_value

    assert day1_mid_inverter is not None and day1_mid_inverter > 0
    assert day1_end_inverter is not None and day1_end_inverter > day1_mid_inverter
    assert day2_start_inverter is not None and day2_start_inverter < day1_end_inverter

    assert day1_mid_system is not None and day1_mid_system > 0
    assert day1_end_system is not None and day1_end_system > day1_mid_system
    assert day2_start_system is not None and day2_start_system < day1_end_system
