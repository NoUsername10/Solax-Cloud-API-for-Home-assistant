"""Config flow behavior tests."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from homeassistant.data_entry_flow import FlowResultType

from solax_cloud_api.config_flow import SolaxFlowHandler
from solax_cloud_api.const import (
    CONF_INVERTERS,
    CONF_SCAN_INTERVAL,
    CONF_SYSTEM_NAME,
    CONF_TOKEN,
)


@pytest.mark.asyncio
async def test_user_step_invalid_token_stays_on_user_form(hass, monkeypatch):
    """Invalid token must block the flow at user step."""
    monkeypatch.setattr(
        "solax_cloud_api.config_flow._test_api_connection",
        AsyncMock(return_value=False),
    )
    flow = SolaxFlowHandler()
    flow.hass = hass
    monkeypatch.setattr(flow, "_async_current_entries", lambda: [])

    result = await flow.async_step_user(
        user_input={
            CONF_TOKEN: "bad-token",
            CONF_SYSTEM_NAME: "My System",
            CONF_SCAN_INTERVAL: 120,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"]["base"] == "invalid_token"


@pytest.mark.asyncio
async def test_add_inverter_duplicate_and_no_inverters_validation(hass, monkeypatch):
    """Duplicate serial and empty finish path should be rejected."""
    monkeypatch.setattr(
        "solax_cloud_api.config_flow._test_api_connection",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        "solax_cloud_api.config_flow._classify_preflight_inverters",
        AsyncMock(
            return_value={
                "token_invalid": False,
                "data": {},
                "rate_limited_inverters": [],
                "rate_limited_details": {},
                "unauthorized_inverters": [],
                "unauthorized_details": {},
            }
        ),
    )
    flow = SolaxFlowHandler()
    flow.hass = hass
    monkeypatch.setattr(flow, "_async_current_entries", lambda: [])

    result = await flow.async_step_user(
        user_input={
            CONF_TOKEN: "good-token",
            CONF_SYSTEM_NAME: "My System",
            CONF_SCAN_INTERVAL: 120,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "add_inverter"

    result = await flow.async_step_add_inverter(user_input={"finish": True})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "add_inverter"
    assert result["errors"]["base"] == "no_inverters"

    result = await flow.async_step_add_inverter(
        user_input={"serial": "SERIAL1", "finish": False}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "add_inverter"

    result = await flow.async_step_add_inverter(
        user_input={"serial": "SERIAL1", "finish": False}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "add_inverter"
    assert result["errors"]["base"] == "duplicate_inverter"


@pytest.mark.asyncio
async def test_rate_limit_notice_requires_acknowledge(hass, monkeypatch):
    """Rate-limit notice must be acknowledged before entry creation."""
    monkeypatch.setattr(
        "solax_cloud_api.config_flow._test_api_connection",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        "solax_cloud_api.config_flow._classify_preflight_inverters",
        AsyncMock(
            return_value={
                "token_invalid": False,
                "data": {
                    "SERIAL1": {
                        "error": "rate_limit",
                        "code": 104,
                        "exception": "Request calls within the current minute > threshold",
                    }
                },
                "rate_limited_inverters": ["SERIAL1"],
                "rate_limited_details": {
                    "SERIAL1": {
                        "code": 104,
                        "exception": "Request calls within the current minute > threshold",
                    }
                },
                "unauthorized_inverters": [],
                "unauthorized_details": {},
            }
        ),
    )
    flow = SolaxFlowHandler()
    flow.hass = hass
    monkeypatch.setattr(flow, "_async_current_entries", lambda: [])

    result = await flow.async_step_user(
        user_input={
            CONF_TOKEN: "good-token",
            CONF_SYSTEM_NAME: "Rate Limit System",
            CONF_SCAN_INTERVAL: 120,
        },
    )
    result = await flow.async_step_add_inverter(
        user_input={"serial": "SERIAL1", "finish": False}
    )
    result = await flow.async_step_add_inverter(user_input={"finish": True})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "rate_limit_notice"

    result = await flow.async_step_rate_limit_notice(user_input={"acknowledge": False})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "rate_limit_notice"
    assert result["errors"]["base"] == "acknowledge_rate_limit"

    result = await flow.async_step_rate_limit_notice(user_input={"acknowledge": True})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Rate Limit System"
    assert result["data"][CONF_INVERTERS] == ["SERIAL1"]
    assert result["data"][CONF_TOKEN] == "good-token"
