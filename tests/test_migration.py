"""Config-entry migration tests."""

from __future__ import annotations

import pytest
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry
from solax_cloud_api import async_migrate_entry
from solax_cloud_api.const import CONFIG_ENTRY_VERSION, DOMAIN


def _create_registry_entry(hass, entry, unique_id, disabled_by):
    registry = er.async_get(hass)
    return registry.async_get_or_create(
        "sensor",
        DOMAIN,
        unique_id,
        config_entry=entry,
        disabled_by=disabled_by,
        suggested_object_id=unique_id,
    )


@pytest.mark.asyncio
async def test_migration_enables_only_integration_disabled_battery_entities(hass):
    """Version 2 should enable old opt-in entities without overriding user choices."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Migration Test",
        version=1,
        pref_disable_new_entities=False,
    )
    entry.add_to_hass(hass)

    inverter_battery = _create_registry_entry(
        hass,
        entry,
        "test_estimated_battery_charge_energy_today_serial1",
        er.RegistryEntryDisabler.INTEGRATION,
    )
    system_battery = _create_registry_entry(
        hass,
        entry,
        "test_estimated_system_battery_charge_energy_today_solax",
        er.RegistryEntryDisabler.INTEGRATION,
    )
    user_disabled_battery = _create_registry_entry(
        hass,
        entry,
        "test_estimated_battery_discharge_energy_today_serial1",
        er.RegistryEntryDisabler.USER,
    )
    unrelated = _create_registry_entry(
        hass,
        entry,
        "test_ac_power_serial1",
        er.RegistryEntryDisabler.INTEGRATION,
    )

    assert await async_migrate_entry(hass, entry) is True

    registry = er.async_get(hass)
    assert entry.version == CONFIG_ENTRY_VERSION
    assert registry.async_get(inverter_battery.entity_id).disabled_by is None
    assert registry.async_get(system_battery.entity_id).disabled_by is None
    assert (
        registry.async_get(user_disabled_battery.entity_id).disabled_by
        is er.RegistryEntryDisabler.USER
    )
    assert (
        registry.async_get(unrelated.entity_id).disabled_by
        is er.RegistryEntryDisabler.INTEGRATION
    )


@pytest.mark.asyncio
async def test_migration_respects_disable_new_entities_preference(hass):
    """The integration must not override Home Assistant's entry-level preference."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Preference Test",
        version=1,
        pref_disable_new_entities=True,
    )
    entry.add_to_hass(hass)
    battery = _create_registry_entry(
        hass,
        entry,
        "test_estimated_battery_charge_energy_total_serial1",
        er.RegistryEntryDisabler.INTEGRATION,
    )

    assert await async_migrate_entry(hass, entry) is True

    registry = er.async_get(hass)
    assert entry.version == CONFIG_ENTRY_VERSION
    assert (
        registry.async_get(battery.entity_id).disabled_by
        is er.RegistryEntryDisabler.INTEGRATION
    )
