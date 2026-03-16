from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_INVERTERS,
    CONF_RATE_LIMIT_NOTIFICATIONS,
    CONF_SCAN_INTERVAL,
    CONF_SYSTEM_NAME,
    CONF_TOKEN,
    DOMAIN,
)

_TO_REDACT = {
    CONF_TOKEN,
    "token",
    "tokenid",
    "tokenId",
    "access_token",
    "authorization",
}
_SERIAL_KEYS = {"serial", "serial_number", "sn", "wifisn", "invertersn"}
_SERIAL_LIST_KEYS = {
    "configured_inverters",
    "serials",
    "rate_limited_inverters",
    "unauthorized_inverters",
}
_BATTERY_FIELDS = ("batPower", "soc", "batStatus")


def _dt_to_iso(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    return None


def _mask_serial(value: Any) -> Any:
    if value is None:
        return None
    serial = str(value)
    if not serial:
        return serial
    if len(serial) <= 4:
        return "*" * len(serial)
    if len(serial) <= 8:
        return f"{serial[:1]}***{serial[-1:]}"
    return f"{serial[:3]}***{serial[-3:]}"


def _mask_token(value: Any) -> str | None:
    if value is None:
        return None
    token = str(value)
    if not token:
        return ""
    if len(token) <= 4:
        return "*" * len(token)
    if len(token) <= 8:
        return f"{token[:1]}***{token[-1:]}"
    return f"{token[:4]}***{token[-4:]}"


def _mask_serial_fields(value: Any, parent_key: str | None = None) -> Any:
    if isinstance(value, dict):
        masked: dict[str, Any] = {}
        for key, item in value.items():
            key_l = str(key).lower()
            if key_l in _SERIAL_KEYS:
                masked[key] = _mask_serial(item)
            elif key_l in _SERIAL_LIST_KEYS and isinstance(item, list):
                masked[key] = [_mask_serial(v) for v in item]
            else:
                masked[key] = _mask_serial_fields(item, key_l)
        return masked

    if isinstance(value, list):
        if (parent_key or "").lower() in _SERIAL_LIST_KEYS:
            return [_mask_serial(v) for v in value]
        return [_mask_serial_fields(v, parent_key) for v in value]

    return value


def _battery_field_summary(raw_payload: Any, filtered_payload: Any) -> dict[str, Any]:
    raw_result = {}
    if isinstance(raw_payload, dict):
        possible_result = raw_payload.get("result")
        if isinstance(possible_result, dict):
            raw_result = possible_result

    filtered = filtered_payload if isinstance(filtered_payload, dict) else {}
    summary: dict[str, Any] = {}

    for field in _BATTERY_FIELDS:
        in_raw = field in raw_result
        raw_val = raw_result.get(field) if in_raw else None
        in_filtered = field in filtered
        summary[field] = {
            "present_in_raw_result": in_raw,
            "raw_value_is_null": bool(in_raw and raw_val is None),
            "present_in_filtered_payload": in_filtered,
            "filtered_value": filtered.get(field) if in_filtered else None,
        }

    summary["battery_like_keys_in_raw_result"] = sorted(
        key for key in raw_result.keys() if "bat" in key.lower() or "soc" in key.lower()
    )
    return summary


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    runtime = hass.data.get(DOMAIN, {}).get(config_entry.entry_id, {})
    coordinator = runtime.get("coordinator")

    configured_inverters = list(config_entry.data.get(CONF_INVERTERS, []))
    raw_token = config_entry.data.get(CONF_TOKEN)
    diagnostics: dict[str, Any] = {
        "config_entry": {
            "entry_id": config_entry.entry_id,
            "title": config_entry.title,
            "system_name": config_entry.data.get(CONF_SYSTEM_NAME),
            "scan_interval": config_entry.data.get(CONF_SCAN_INTERVAL),
            "configured_inverters": configured_inverters,
            "rate_limit_notifications_enabled": bool(
                config_entry.options.get(CONF_RATE_LIMIT_NOTIFICATIONS, True)
            ),
            # Keep a safe masked token preview so support can verify length/entry.
            "raw_api_token_masked": _mask_token(raw_token),
            "raw_api_token_length": len(str(raw_token)) if raw_token else 0,
            "api_token_present": bool(config_entry.data.get(CONF_TOKEN)),
        },
        "coordinator": {
            "available": coordinator is not None,
        },
        "inverters": [],
    }

    if coordinator is None:
        return _mask_serial_fields(async_redact_data(diagnostics, _TO_REDACT))

    coord_data = coordinator.data if isinstance(coordinator.data, dict) else {}
    raw_data = (
        coordinator.raw_api_responses
        if isinstance(getattr(coordinator, "raw_api_responses", None), dict)
        else {}
    )
    rate_limited = set(getattr(coordinator, "rate_limited_inverters", []))
    unauthorized = set(getattr(coordinator, "unauthorized_inverters", []))
    rate_limited_details = deepcopy(getattr(coordinator, "rate_limited_details", {}))
    unauthorized_details = deepcopy(getattr(coordinator, "unauthorized_details", {}))

    diagnostics["coordinator"].update(
        {
            "name": coordinator.name,
            "last_update_attempt": _dt_to_iso(getattr(coordinator, "last_update_attempt", None)),
            "last_successful_update": _dt_to_iso(
                getattr(coordinator, "last_successful_update", None)
            ),
            "last_rate_limit_at": _dt_to_iso(getattr(coordinator, "last_rate_limit_at", None)),
            "rate_limited_inverters": list(rate_limited),
            "unauthorized_inverters": list(unauthorized),
            "rate_limited_details": [
                {"serial": serial, "details": details}
                for serial, details in rate_limited_details.items()
            ],
            "unauthorized_details": [
                {"serial": serial, "details": details}
                for serial, details in unauthorized_details.items()
            ],
        }
    )

    for serial in configured_inverters:
        raw_payload = raw_data.get(serial)
        filtered_payload = coord_data.get(serial)
        diagnostics["inverters"].append(
            {
                "serial": serial,
                "raw_api_response": deepcopy(raw_payload),
                "filtered_payload": deepcopy(filtered_payload),
                "status": {
                    "is_rate_limited": serial in rate_limited,
                    "is_unauthorized": serial in unauthorized,
                    "has_error_payload": bool(
                        isinstance(filtered_payload, dict) and filtered_payload.get("error")
                    ),
                },
                "battery_field_summary": _battery_field_summary(raw_payload, filtered_payload),
            }
        )

    redacted = async_redact_data(diagnostics, _TO_REDACT)
    return _mask_serial_fields(redacted)
