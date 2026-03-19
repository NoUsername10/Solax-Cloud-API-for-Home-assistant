"""Diagnostics payload tests."""

from __future__ import annotations

from datetime import timedelta

import pytest
from homeassistant.util import dt as dt_util

from solax_cloud_api import diagnostics
from solax_cloud_api.coordinator import SolaxCoordinator
from solax_cloud_api.const import DOMAIN


@pytest.mark.asyncio
async def test_diagnostics_masks_sensitive_values_and_includes_battery_summary(
    hass, mock_solax_entry
):
    """Diagnostics should mask token/serial and include raw vs filtered data."""
    token = "ABCDEFGHIJKLMNOPQRSTUVWX"
    serial = "30M3Y10115037N"

    entry = mock_solax_entry(
        token=token,
        inverters=[serial],
        system_name="Diag System",
        entity_prefix="diag_system",
        options={"rate_limit_notifications": True},
    )
    coordinator = SolaxCoordinator(hass, token, [serial], 120)
    coordinator.data = {
        serial: {
            "acpower": 500,
            "soc": 44,
            "batPower": 100,
            "uploadTime": "2026-03-19 10:00:00",
        }
    }
    coordinator.raw_api_responses = {
        serial: {
            "success": True,
            "code": 0,
            "exception": "operation success",
            "result": {
                "acpower": 500,
                "soc": 44,
                "batPower": None,
                "batStatus": 1,
            },
        }
    }
    coordinator.rate_limited_inverters = [serial]
    coordinator.unauthorized_inverters = [serial]
    coordinator.rate_limited_details = {
        serial: {"code": 104, "exception": "threshold", "reason": "api_rate_limit"}
    }
    coordinator.unauthorized_details = {serial: {"code": 1003, "exception": "no auth!"}}
    coordinator.last_update_attempt = dt_util.utcnow()
    coordinator.last_successful_update = dt_util.utcnow() - timedelta(seconds=30)
    coordinator.last_rate_limit_at = dt_util.utcnow() - timedelta(seconds=5)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {"coordinator": coordinator}

    payload = await diagnostics.async_get_config_entry_diagnostics(hass, entry)

    config_block = payload["config_entry"]
    assert config_block["raw_api_token_masked"] != token
    assert "***" in config_block["raw_api_token_masked"]
    assert config_block["raw_api_token_length"] == len(token)
    assert config_block["api_token_present"] is True
    assert config_block["configured_inverters"][0] != serial

    inverter_payload = payload["inverters"][0]
    assert inverter_payload["serial"] != serial
    assert inverter_payload["raw_api_response"]["result"]["soc"] == 44
    assert inverter_payload["filtered_payload"]["acpower"] == 500

    battery_summary = inverter_payload["battery_field_summary"]
    assert battery_summary["batPower"]["present_in_raw_result"] is True
    assert battery_summary["batPower"]["raw_value_is_null"] is True
    assert battery_summary["batPower"]["present_in_filtered_payload"] is True
