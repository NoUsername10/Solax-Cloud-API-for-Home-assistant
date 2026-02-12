from homeassistant.config_entries import ConfigEntry
from homeassistant.components import persistent_notification
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from .const import (
    DOMAIN,
    PLATFORMS,
    CONF_TOKEN,
    CONF_INVERTERS,
    CONF_SCAN_INTERVAL,
    CONF_RATE_LIMIT_NOTIFICATIONS,
    RUNTIME_INITIAL_SETUP_STATE,
    RUNTIME_RELOAD_STATE,
    SERVICE_MANUAL_REFRESH,
)
from .coordinator import SolaxCoordinator


CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


def _rate_limit_notification_id(entry_id: str) -> str:
    return f"{DOMAIN}_rate_limit_{entry_id}"


def _invalid_serial_notification_id(entry_id: str) -> str:
    return f"{DOMAIN}_invalid_serial_{entry_id}"


def _rate_limit_notifications_enabled(hass: HomeAssistant, entry_id: str) -> bool:
    entry = hass.config_entries.async_get_entry(entry_id)
    if entry is None:
        return True
    return bool(entry.options.get(CONF_RATE_LIMIT_NOTIFICATIONS, True))


def _update_rate_limit_notification(
    hass: HomeAssistant, entry_id: str, coordinator: SolaxCoordinator
) -> None:
    if not _rate_limit_notifications_enabled(hass, entry_id):
        persistent_notification.async_dismiss(hass, _rate_limit_notification_id(entry_id))
        return

    rate_limited_inverters = list(getattr(coordinator, "rate_limited_inverters", []))
    rate_limited_details = dict(getattr(coordinator, "rate_limited_details", {}))
    notification_id = _rate_limit_notification_id(entry_id)
    if not rate_limited_inverters:
        persistent_notification.async_dismiss(hass, notification_id)
        return

    inverter_list = ", ".join(rate_limited_inverters)
    details_lines = []
    for serial in rate_limited_inverters:
        info = rate_limited_details.get(serial, {})
        code = info.get("code")
        reason = info.get("exception")
        if code is not None or reason:
            details_lines.append(f"- {serial}: code={code}, reason={reason}")
    details_block = "\n".join(details_lines)
    body = (
        "SolaX Cloud API rate limit is active.\n"
        f"Affected inverter(s): {inverter_list}\n"
    )
    if details_block:
        body += f"{details_block}\n"
    body += (
        "The integration keeps previous values for affected inverters until API calls recover. "
        "Consider increasing scan interval."
    )

    persistent_notification.async_create(
        hass,
        body,
        title="SolaX Cloud API - Rate Limit",
        notification_id=notification_id,
    )


def _update_invalid_serial_notification(
    hass: HomeAssistant, entry_id: str, coordinator: SolaxCoordinator
) -> None:
    invalid_serials = list(getattr(coordinator, "unauthorized_inverters", []))
    invalid_details = dict(getattr(coordinator, "unauthorized_details", {}))
    notification_id = _invalid_serial_notification_id(entry_id)
    if not invalid_serials:
        persistent_notification.async_dismiss(hass, notification_id)
        return

    details_lines = []
    for serial in invalid_serials:
        detail = invalid_details.get(serial, {})
        code = detail.get("code", 1003)
        reason = detail.get("exception") or "Data Unauthorized"
        details_lines.append(f"- {serial}: code={code}, reason={reason}")
    details_block = "\n".join(details_lines)

    body = (
        "One or more inverter serials are unauthorized.\n"
        f"{details_block}\n"
        "These inverters are kept unavailable until serial/auth access is corrected."
    )
    persistent_notification.async_create(
        hass,
        body,
        title="SolaX Cloud API - Invalid Serial/Access",
        notification_id=notification_id,
    )


def _dedupe_serials(serials):
    unique = []
    seen = set()
    for raw in serials:
        serial = str(raw).strip()
        if not serial:
            continue
        key = serial.casefold()
        if key in seen:
            continue
        seen.add(key)
        unique.append(serial)
    return unique


def _matches_pending_initial_setup(entry: ConfigEntry, pending: dict) -> bool:
    entry_token = str(entry.data.get(CONF_TOKEN, "")).strip()
    entry_inverters = _dedupe_serials(entry.data.get(CONF_INVERTERS, []))
    match = pending.get("match", {})
    match_token = str(match.get(CONF_TOKEN, "")).strip()
    match_inverters = _dedupe_serials(match.get(CONF_INVERTERS, []))
    return (
        entry_token == match_token
        and {sn.casefold() for sn in entry_inverters}
        == {sn.casefold() for sn in match_inverters}
    )

async def async_setup(hass: HomeAssistant, config: dict):
    async def _handle_manual_refresh(_call):
        domain_data = hass.data.get(DOMAIN, {})
        for entry_data in domain_data.values():
            coordinator = entry_data["coordinator"]
            await coordinator.async_request_refresh()

    if not hass.services.has_service(DOMAIN, SERVICE_MANUAL_REFRESH):
        hass.services.async_register(DOMAIN, SERVICE_MANUAL_REFRESH, _handle_manual_refresh)

    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    hass.data.setdefault(DOMAIN, {})
    hass.data.setdefault(RUNTIME_RELOAD_STATE, {})
    token = entry.data.get(CONF_TOKEN) 
    inverters = _dedupe_serials(entry.data.get(CONF_INVERTERS, []))
    scan = entry.data.get(CONF_SCAN_INTERVAL, 120)

    runtime_reload_state = hass.data.get(RUNTIME_RELOAD_STATE, {})
    reload_state = runtime_reload_state.pop(entry.entry_id, None)
    initial_data = {}
    initial_refresh_inverters = None
    if isinstance(reload_state, dict):
        token_changed = bool(reload_state.get("token_changed", False))
        cached_data = reload_state.get("data", {})
        added_inverters = reload_state.get("added_inverters")
        if not token_changed and isinstance(cached_data, dict):
            configured = {sn.casefold() for sn in inverters}
            for serial, payload in cached_data.items():
                if serial.casefold() in configured and isinstance(payload, dict):
                    initial_data[serial] = dict(payload)

            if isinstance(added_inverters, list):
                initial_refresh_inverters = [
                    sn for sn in added_inverters if sn.casefold() in configured
                ]
    else:
        pending_initial_setup = runtime_reload_state.get(RUNTIME_INITIAL_SETUP_STATE)
        if isinstance(pending_initial_setup, dict) and _matches_pending_initial_setup(
            entry, pending_initial_setup
        ):
            runtime_reload_state.pop(RUNTIME_INITIAL_SETUP_STATE, None)
            preflight_state = pending_initial_setup.get("state", {})
            if isinstance(preflight_state, dict):
                preflight_data = preflight_state.get("data", {})
                if isinstance(preflight_data, dict):
                    configured = {sn.casefold() for sn in inverters}
                    for serial, payload in preflight_data.items():
                        if serial.casefold() in configured and isinstance(payload, dict):
                            initial_data[serial] = dict(payload)

                    preflight_known = {sn.casefold() for sn in initial_data}
                    initial_refresh_inverters = [
                        serial
                        for serial in inverters
                        if serial.casefold() not in preflight_known
                    ]

    coordinator = SolaxCoordinator(
        hass,
        token,
        inverters,
        scan,
        initial_data=initial_data,
        initial_refresh_inverters=initial_refresh_inverters,
    )
    await coordinator.async_config_entry_first_refresh()
    _update_rate_limit_notification(hass, entry.entry_id, coordinator)
    _update_invalid_serial_notification(hass, entry.entry_id, coordinator)

    def _handle_coordinator_update():
        _update_rate_limit_notification(hass, entry.entry_id, coordinator)
        _update_invalid_serial_notification(hass, entry.entry_id, coordinator)

    rate_limit_unsub = coordinator.async_add_listener(_handle_coordinator_update)

    def _refresh_rate_limit_notification():
        _update_rate_limit_notification(hass, entry.entry_id, coordinator)

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "entry": entry,
        "rate_limit_unsub": rate_limit_unsub,
        "refresh_rate_limit_notification": _refresh_rate_limit_notification,
    }

    # Forward the setup to the sensor platform
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        entry_data = hass.data[DOMAIN].pop(entry.entry_id, None)
        if entry_data:
            rate_limit_unsub = entry_data.get("rate_limit_unsub")
            if rate_limit_unsub:
                rate_limit_unsub()
        persistent_notification.async_dismiss(hass, _rate_limit_notification_id(entry.entry_id))
        persistent_notification.async_dismiss(hass, _invalid_serial_notification_id(entry.entry_id))
        if not hass.data[DOMAIN] and hass.services.has_service(DOMAIN, SERVICE_MANUAL_REFRESH):
            hass.services.async_remove(DOMAIN, SERVICE_MANUAL_REFRESH)
    return unload_ok
