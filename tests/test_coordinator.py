"""Coordinator behavior tests."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest
from homeassistant.exceptions import ConfigEntryAuthFailed
from solax_cloud_api.const import API_REGION_INDIA, API_REGION_NA, API_URLS
from solax_cloud_api.coordinator import SolaxCoordinator


class _FakeResponse:
    status = 200

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def text(self):
        return "ok"

    async def json(self):
        return {"success": True, "code": 0, "result": {"acpower": 100}}


class _RecordingSession:
    def __init__(self):
        self.url = None

    def post(self, url, **_kwargs):
        self.url = url
        return _FakeResponse()


@pytest.fixture(autouse=True)
def _patch_client_session(monkeypatch):
    """Avoid creating real aiohttp sessions in unit tests."""
    monkeypatch.setattr(
        "solax_cloud_api.coordinator.async_get_clientsession",
        lambda _hass: object(),
    )


@pytest.mark.asyncio
async def test_coordinator_india_region_uses_india_endpoint(hass):
    """India region must send requests only to the allowlisted India endpoint."""
    coordinator = SolaxCoordinator(
        hass, "token", ["SERIAL1"], 120, api_region=API_REGION_INDIA
    )
    session = _RecordingSession()

    result = await coordinator._fetch_one(session, "SERIAL1")

    assert result["code"] == 0
    assert session.url == API_URLS[API_REGION_INDIA]


@pytest.mark.asyncio
async def test_coordinator_na_region_uses_na_endpoint(hass):
    """North America region must send requests only to the allowlisted NA endpoint."""
    coordinator = SolaxCoordinator(
        hass, "token", ["SERIAL1"], 120, api_region=API_REGION_NA
    )
    session = _RecordingSession()

    result = await coordinator._fetch_one(session, "SERIAL1")

    assert result["code"] == 0
    assert session.url == API_URLS[API_REGION_NA]


def test_coordinator_unknown_region_falls_back_to_global(hass):
    """Unknown stored region values must not become arbitrary request URLs."""
    coordinator = SolaxCoordinator(hass, "token", ["SERIAL1"], 120, api_region="other")

    assert coordinator.api_url == API_URLS["global"]


@pytest.mark.asyncio
async def test_coordinator_success_filters_null_fields(hass):
    """Successful payloads should keep only non-null result fields."""
    coordinator = SolaxCoordinator(hass, "token", ["SERIAL1"], 120)
    coordinator._fetch_one = AsyncMock(
        return_value={
            "success": True,
            "code": 0,
            "exception": "operation success",
            "result": {
                "acpower": 900,
                "yieldtoday": 4.2,
                "soc": None,
                "inverterType": 1,
            },
        }
    )

    data = await coordinator._async_update_data()
    assert data["SERIAL1"]["acpower"] == 900
    assert "soc" not in data["SERIAL1"]
    assert coordinator.last_successful_update is not None


@pytest.mark.asyncio
async def test_coordinator_marks_data_unauthorized(hass):
    """Code 1003 should mark inverter as unauthorized/unavailable."""
    coordinator = SolaxCoordinator(hass, "token", ["SERIAL1"], 120)
    coordinator._fetch_one = AsyncMock(
        return_value={
            "success": False,
            "code": 1003,
            "exception": "no auth!",
            "result": None,
        }
    )

    data = await coordinator._async_update_data()
    assert data["SERIAL1"]["error"] == "data_unauthorized"
    assert "SERIAL1" in coordinator.unauthorized_inverters
    assert coordinator.unauthorized_details["SERIAL1"]["code"] == 1003


@pytest.mark.asyncio
async def test_coordinator_marks_code_less_no_auth_as_data_unauthorized(hass):
    """Code-less no-auth should mark only the affected inverter unauthorized."""
    coordinator = SolaxCoordinator(hass, "token", ["SERIAL1"], 120)
    coordinator._fetch_one = AsyncMock(
        return_value={
            "success": False,
            "exception": "no auth!",
            "result": None,
        }
    )

    data = await coordinator._async_update_data()

    assert data["SERIAL1"]["error"] == "data_unauthorized"
    assert "SERIAL1" in coordinator.unauthorized_inverters
    assert coordinator.unauthorized_details["SERIAL1"]["code"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize("token_code", [103, 1001])
async def test_coordinator_token_failure_requires_reauthentication(hass, token_code):
    """Observed and documented token failures should trigger reauthentication."""
    coordinator = SolaxCoordinator(hass, "bad-token", ["SERIAL1"], 120)
    coordinator._fetch_one = AsyncMock(
        return_value={
            "success": False,
            "code": token_code,
            "exception": "token invalid!",
            "result": None,
        }
    )

    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()


@pytest.mark.asyncio
@pytest.mark.parametrize("rate_code", [104, 3])
async def test_coordinator_rate_limit_keeps_previous_good_values(hass, rate_code):
    """Rate-limited responses should keep previous good payload."""
    coordinator = SolaxCoordinator(hass, "token", ["SERIAL1"], 120)
    coordinator.data = {"SERIAL1": {"acpower": 321, "yieldtoday": 1.5}}
    coordinator._fetch_one = AsyncMock(
        return_value={
            "success": False,
            "code": rate_code,
            "exception": "Request calls within the current minute > threshold",
            "result": None,
        }
    )

    data = await coordinator._async_update_data()
    assert data["SERIAL1"]["acpower"] == 321
    assert "SERIAL1" in coordinator.rate_limited_inverters
    assert coordinator.rate_limited_details["SERIAL1"]["code"] == rate_code


@pytest.mark.asyncio
async def test_coordinator_cooldown_skips_request_and_keeps_cache(hass):
    """Active cooldown should skip API call and retain cached values."""
    coordinator = SolaxCoordinator(hass, "token", ["SERIAL1"], 120)
    coordinator.data = {"SERIAL1": {"acpower": 111}}
    coordinator._last_rate_limit_SERIAL1 = asyncio.get_running_loop().time()
    fetch_mock = AsyncMock(
        return_value={
            "success": True,
            "code": 0,
            "result": {"acpower": 999},
        }
    )
    coordinator._fetch_one = fetch_mock

    data = await coordinator._async_update_data()
    fetch_mock.assert_not_awaited()
    assert data["SERIAL1"]["acpower"] == 111
    assert "SERIAL1" in coordinator.rate_limited_inverters
    assert coordinator.rate_limited_details["SERIAL1"]["reason"] == "cooldown_active"
