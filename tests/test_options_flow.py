"""Options flow behavior tests."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from homeassistant.data_entry_flow import FlowResultType

from solax_cloud_api.config_flow import SolaxOptionsFlowHandler
from solax_cloud_api.const import (
    CONF_SCAN_INTERVAL,
    CONF_SYSTEM_NAME,
    CONF_TOKEN,
    DOMAIN,
    RUNTIME_RELOAD_STATE,
)


@pytest.mark.asyncio
async def test_options_add_remove_inverters_persists_config(
    hass, mock_solax_entry, runtime_coordinator_stub, monkeypatch
):
    """Adding/removing inverters in options should update entry data."""
    entry = mock_solax_entry(
        token="token-a",
        inverters=["SERIAL1", "SERIAL2"],
        system_name="My System",
        entity_prefix="my_system",
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "coordinator": runtime_coordinator_stub(data={"SERIAL1": {"acpower": 100}})
    }
    reload_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(hass.config_entries, "async_reload", reload_mock)

    flow = SolaxOptionsFlowHandler(entry)
    flow.hass = hass
    result = await flow.async_step_manage_inverters()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manage_inverters"

    result = await flow.async_step_manage_inverters(
        user_input={
            CONF_TOKEN: "token-a",
            CONF_SYSTEM_NAME: "My System",
            CONF_SCAN_INTERVAL: 120,
            "serial": "SERIAL3",
            "remove_serial": "SERIAL2",
            "finish": True,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    updated = hass.config_entries.async_get_entry(entry.entry_id)
    assert updated is not None
    assert updated.data["inverters"] == ["SERIAL1", "SERIAL3"]
    reload_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_options_token_unchanged_marks_only_new_inverters_for_refresh(
    hass, mock_solax_entry, runtime_coordinator_stub, monkeypatch
):
    """When token is unchanged, only newly added inverters should be marked."""
    entry = mock_solax_entry(
        token="same-token",
        inverters=["SERIAL1"],
        system_name="Stable System",
        entity_prefix="stable_system",
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "coordinator": runtime_coordinator_stub(data={"SERIAL1": {"acpower": 200}})
    }
    monkeypatch.setattr(hass.config_entries, "async_reload", AsyncMock(return_value=True))

    flow = SolaxOptionsFlowHandler(entry)
    flow.hass = hass
    result = await flow.async_step_manage_inverters()
    result = await flow.async_step_manage_inverters(
        user_input={
            CONF_TOKEN: "same-token",
            CONF_SYSTEM_NAME: "Stable System",
            CONF_SCAN_INTERVAL: 120,
            "serial": "SERIAL2",
            "finish": True,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY

    state = hass.data[RUNTIME_RELOAD_STATE][entry.entry_id]
    assert state["token_changed"] is False
    assert state["added_inverters"] == ["SERIAL2"]
    assert "SERIAL1" in state["data"]


@pytest.mark.asyncio
async def test_options_token_changed_marks_full_refresh(
    hass, mock_solax_entry, runtime_coordinator_stub, monkeypatch
):
    """Changing token should set token_changed in runtime reload state."""
    entry = mock_solax_entry(
        token="old-token",
        inverters=["SERIAL1"],
        system_name="Token System",
        entity_prefix="token_system",
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "coordinator": runtime_coordinator_stub(data={"SERIAL1": {"acpower": 150}})
    }
    monkeypatch.setattr(
        "solax_cloud_api.config_flow._test_api_connection",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(hass.config_entries, "async_reload", AsyncMock(return_value=True))

    flow = SolaxOptionsFlowHandler(entry)
    flow.hass = hass
    result = await flow.async_step_manage_inverters()
    result = await flow.async_step_manage_inverters(
        user_input={
            CONF_TOKEN: "new-token",
            CONF_SYSTEM_NAME: "Token System",
            CONF_SCAN_INTERVAL: 120,
            "finish": True,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY

    state = hass.data[RUNTIME_RELOAD_STATE][entry.entry_id]
    assert state["token_changed"] is True
    assert state["added_inverters"] == []
