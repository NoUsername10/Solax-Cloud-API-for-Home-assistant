"""Config flow behavior tests."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from homeassistant.data_entry_flow import FlowResultType
from solax_cloud_api.config_flow import (
    SolaxFlowHandler,
    _classify_preflight_inverters,
    _test_api_connection,
)
from solax_cloud_api.const import (
    API_REGION_INDIA,
    API_REGION_NA,
    CONF_API_REGION,
    CONF_INVERTERS,
    CONF_SCAN_INTERVAL,
    CONF_SYSTEM_NAME,
    CONF_TOKEN,
)


class _ApiResponse:
    """Minimal aiohttp response stub for config-flow API classification."""

    status = 200

    def __init__(self, payload):
        self.payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def json(self):
        return self.payload

    async def text(self):
        return "response"


class _ApiSession:
    """Return one configured response payload for every POST."""

    def __init__(self, payload):
        self.payload = payload

    def post(self, _url, **_kwargs):
        return _ApiResponse(self.payload)


@pytest.mark.asyncio
async def test_connection_test_rejects_observed_token_error_103(hass, monkeypatch):
    """The live Global/India code 103 response must reject the token."""
    monkeypatch.setattr(
        "solax_cloud_api.config_flow.async_get_clientsession",
        lambda _hass: _ApiSession(
            {"success": False, "code": 103, "exception": "token invalid!"}
        ),
    )

    assert not await _test_api_connection(hass, "bad-token")


@pytest.mark.asyncio
async def test_connection_test_accepts_token_with_code_less_no_auth(hass, monkeypatch):
    """A placeholder-serial no-auth response proves connectivity, not token failure."""
    monkeypatch.setattr(
        "solax_cloud_api.config_flow.async_get_clientsession",
        lambda _hass: _ApiSession(
            {"success": False, "exception": "no auth!", "result": None}
        ),
    )

    assert await _test_api_connection(hass, "accepted-token")


@pytest.mark.asyncio
async def test_preflight_classifies_code_less_no_auth_as_serial_failure(
    hass, monkeypatch
):
    """Setup preflight should retain code-less no-auth as serial/access failure."""
    monkeypatch.setattr(
        "solax_cloud_api.config_flow.async_get_clientsession",
        lambda _hass: _ApiSession(
            {"success": False, "exception": "no auth!", "result": None}
        ),
    )

    result = await _classify_preflight_inverters(
        hass, "accepted-token", ["SERIAL1"], 120
    )

    assert result is not None
    assert result["token_invalid"] is False
    assert result["unauthorized_inverters"] == ["SERIAL1"]
    assert result["data"]["SERIAL1"]["error"] == "data_unauthorized"
    assert result["unauthorized_details"]["SERIAL1"]["code"] is None


@pytest.mark.asyncio
async def test_user_step_india_region_is_used_and_stored(hass, monkeypatch):
    """India onboarding must validate, preflight, and store the India region."""
    connection_test = AsyncMock(return_value=True)
    preflight_test = AsyncMock(
        return_value={
            "token_invalid": False,
            "data": {"SERIAL1": {"acpower": 500}},
            "rate_limited_inverters": [],
            "rate_limited_details": {},
            "unauthorized_inverters": [],
            "unauthorized_details": {},
        }
    )
    monkeypatch.setattr(
        "solax_cloud_api.config_flow._test_api_connection", connection_test
    )
    monkeypatch.setattr(
        "solax_cloud_api.config_flow._classify_preflight_inverters", preflight_test
    )
    flow = SolaxFlowHandler()
    flow.hass = hass
    monkeypatch.setattr(flow, "_async_current_entries", lambda: [])

    result = await flow.async_step_user(
        user_input={
            CONF_API_REGION: API_REGION_INDIA,
            CONF_TOKEN: "india-token",
            CONF_SYSTEM_NAME: "India System",
            CONF_SCAN_INTERVAL: 120,
        }
    )
    assert result["step_id"] == "add_inverter"
    connection_test.assert_awaited_once_with(hass, "india-token", API_REGION_INDIA)

    await flow.async_step_add_inverter(
        user_input={"serial": "SERIAL1", "finish": False}
    )
    result = await flow.async_step_add_inverter(user_input={"finish": True})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_API_REGION] == API_REGION_INDIA
    preflight_test.assert_awaited_once_with(
        hass, "india-token", ["SERIAL1"], 120, API_REGION_INDIA
    )


@pytest.mark.asyncio
async def test_user_step_na_region_is_used_and_stored(hass, monkeypatch):
    """North America onboarding must validate, preflight, and store the NA region."""
    connection_test = AsyncMock(return_value=True)
    preflight_test = AsyncMock(
        return_value={
            "token_invalid": False,
            "data": {"SERIAL1": {"acpower": 500}},
            "rate_limited_inverters": [],
            "rate_limited_details": {},
            "unauthorized_inverters": [],
            "unauthorized_details": {},
        }
    )
    monkeypatch.setattr(
        "solax_cloud_api.config_flow._test_api_connection", connection_test
    )
    monkeypatch.setattr(
        "solax_cloud_api.config_flow._classify_preflight_inverters", preflight_test
    )
    flow = SolaxFlowHandler()
    flow.hass = hass
    monkeypatch.setattr(flow, "_async_current_entries", lambda: [])

    result = await flow.async_step_user(
        user_input={
            CONF_API_REGION: API_REGION_NA,
            CONF_TOKEN: "na-token",
            CONF_SYSTEM_NAME: "NA System",
            CONF_SCAN_INTERVAL: 120,
        }
    )
    assert result["step_id"] == "add_inverter"
    connection_test.assert_awaited_once_with(hass, "na-token", API_REGION_NA)

    await flow.async_step_add_inverter(
        user_input={"serial": "SERIAL1", "finish": False}
    )
    result = await flow.async_step_add_inverter(user_input={"finish": True})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_API_REGION] == API_REGION_NA
    preflight_test.assert_awaited_once_with(
        hass, "na-token", ["SERIAL1"], 120, API_REGION_NA
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
