import asyncio
from typing import Any
import voluptuous as vol
import logging
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv
import aiohttp
import async_timeout
from .const import (
    DOMAIN,
    CONF_TOKEN,
    CONF_INVERTERS,
    CONF_SCAN_INTERVAL,
    CONF_SYSTEM_NAME,
    CONF_ENTITY_PREFIX,
    CONF_RATE_LIMIT_NOTIFICATIONS,
    DEFAULT_SCAN_INTERVAL,
    API_URL,
    RUNTIME_INITIAL_SETUP_STATE,
    RUNTIME_RELOAD_STATE,
)

_LOGGER = logging.getLogger(__name__)

def _slugify_name(value: str) -> str:
    return value.lower().replace(" ", "_").replace("-", "_")

def _normalize_serial(value: str) -> str:
    return value.strip()

def _serial_exists(serial: str, serials: list[str]) -> bool:
    serial_key = serial.casefold()
    return any(existing.casefold() == serial_key for existing in serials)

def _dedupe_serials(serials: list[str]) -> list[str]:
    unique = []
    seen = set()
    for raw in serials:
        normalized = _normalize_serial(str(raw))
        if not normalized:
            continue
        key = normalized.casefold()
        if key in seen:
            continue
        seen.add(key)
        unique.append(normalized)
    return unique


def _rate_limit_acknowledge_label(inverters_list: str, scan_interval: int) -> str:
    return (
        "API Rate Limit occurred. "
        f"Affected inverter(s): {inverters_list}. "
        f"Current scan interval: {scan_interval}s. "
        "Some values may be delayed until next refresh."
    )


def _format_invalid_serial_details(
    inverters: list[str], details: dict[str, dict[str, Any]]
) -> str:
    formatted = []
    for serial in inverters:
        detail = details.get(serial, {})
        code = detail.get("code", 1003)
        reason = detail.get("exception") or "Data Unauthorized"
        formatted.append(f"{serial} (code={code}, reason={reason})")
    return "; ".join(formatted) if formatted else "Unknown"


def _invalid_serial_acknowledge_label(details_text: str) -> str:
    return (
        "Invalid Serial/Access detected. "
        f"Affected inverter(s): {details_text}. "
        "These inverters are kept unavailable until serial/auth access is corrected."
    )


def _build_initial_setup_match(entry_data: dict[str, Any]) -> dict[str, Any]:
    return {
        CONF_TOKEN: str(entry_data.get(CONF_TOKEN, "")).strip(),
        CONF_INVERTERS: _dedupe_serials(entry_data.get(CONF_INVERTERS, [])),
        CONF_SCAN_INTERVAL: int(entry_data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)),
        CONF_SYSTEM_NAME: str(entry_data.get(CONF_SYSTEM_NAME, "")),
    }


async def _test_api_connection(token: str, serial: str = "TEST123") -> bool:
    """Test if the API token is valid."""
    try:
        headers = {"Content-Type": "application/json", "tokenId": token}
        payload = {"wifiSn": serial}
        
        async with async_timeout.timeout(10):
            async with aiohttp.ClientSession() as session:
                async with session.post(API_URL, json=payload, headers=headers) as resp:
                    if resp.status != 200:
                        return False

                    data = await resp.json()
                    code = data.get("code")
                    exception = str(data.get("exception", "")).lower()

                    # Known invalid-auth/invalid-request responses from Solax API.
                    # 1001 = Interface Unauthorized, 1002 = Parameter validation failed.
                    if code in (1001, 1002):
                        return False
                    if "token" in exception and "invalid" in exception:
                        return False

                    # Any other well-formed API response means token reached Solax correctly.
                    # (e.g. 1003 Data Unauthorized can happen with wrong/placeholder serial)
                    return True
    except Exception:
        return False


def _is_rate_limited_payload(data: dict) -> bool:
    code = data.get("code")
    if code in (3, 104):
        return True

    exception = str(data.get("exception", "")).lower()
    return any(
        marker in exception
        for marker in (
            "rate limit",
            "maximum call threshold",
            "suspend the request",
            "current minute > threshold",
            "within the current minute",
            "too many requests",
        )
    )


async def _classify_preflight_inverters(
    token: str, inverters: list[str], scan_interval: int
) -> dict[str, Any] | None:
    """Single-pass setup preflight for all serials.

    Returns normalized data/error payloads so the initial coordinator refresh can
    reuse this state and avoid a second immediate API round-trip.
    """
    results: dict[str, dict[str, Any]] = {}
    rate_limited: list[str] = []
    rate_limited_details: dict[str, dict[str, Any]] = {}
    unauthorized: list[str] = []
    unauthorized_details: dict[str, dict[str, Any]] = {}
    headers = {"Content-Type": "application/json", "tokenId": token}
    now_monotonic = asyncio.get_running_loop().time()
    cooldown_seconds = scan_interval * 0.55

    try:
        async with async_timeout.timeout(20):
            async with aiohttp.ClientSession() as session:
                for idx, serial in enumerate(inverters):
                    if idx > 0:
                        await asyncio.sleep(0.2)
                    payload = {"wifiSn": serial}
                    try:
                        async with session.post(API_URL, json=payload, headers=headers) as resp:
                            text = await resp.text()
                            if resp.status != 200:
                                results[serial] = {"error": f"HTTP {resp.status}", "raw": text}
                                continue
                            try:
                                data = await resp.json()
                            except Exception as json_err:
                                results[serial] = {
                                    "error": f"JSON Error: {json_err}",
                                    "raw": text,
                                }
                                continue
                    except asyncio.TimeoutError:
                        results[serial] = {"error": "Timeout"}
                        continue
                    except Exception as request_err:
                        results[serial] = {"error": str(request_err)}
                        continue

                    code = data.get("code")
                    success = data.get("success", False)
                    exception = str(data.get("exception", "")).lower()

                    if code in (1001, 1002):
                        return {"token_invalid": True}
                    if "token" in exception and "invalid" in exception:
                        return {"token_invalid": True}

                    if _is_rate_limited_payload(data):
                        rate_limited.append(serial)
                        rate_limited_details[serial] = {
                            "reason": "api_rate_limit",
                            "code": code,
                            "exception": data.get("exception"),
                            "retry_in_seconds": round(cooldown_seconds, 1),
                        }
                        results[serial] = {
                            "error": "rate_limit",
                            "code": code,
                            "exception": data.get("exception"),
                            "skip_until": now_monotonic + cooldown_seconds,
                        }
                        continue

                    if code == 1003:
                        unauthorized.append(serial)
                        unauthorized_details[serial] = {
                            "code": code,
                            "exception": data.get("exception"),
                        }
                        results[serial] = {
                            "error": "data_unauthorized",
                            "code": code,
                            "exception": data.get("exception"),
                            "raw": data,
                        }
                        continue

                    if not success or (code is not None and code != 0):
                        results[serial] = {
                            "error": True,
                            "code": code,
                            "exception": data.get("exception"),
                            "raw": data,
                        }
                        continue

                    result_data = data.get("result", {})
                    if result_data:
                        results[serial] = {
                            key: value for key, value in result_data.items() if value is not None
                        }
                    else:
                        results[serial] = {}
    except Exception:
        # Setup should never fail only because preflight classification failed.
        return None

    return {
        "token_invalid": False,
        "data": results,
        "rate_limited_inverters": rate_limited,
        "rate_limited_details": rate_limited_details,
        "unauthorized_inverters": unauthorized,
        "unauthorized_details": unauthorized_details,
    }


class SolaxFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self):
        super().__init__()
        self._inverters = []
        self._token = None
        self._scan_interval = DEFAULT_SCAN_INTERVAL
        self._system_name = "Solax System"
        self._pending_entry_data = None
        self._rate_limit_notice_inverters = []
        self._initial_setup_state = None

    def _stash_initial_setup_state(self, entry_data: dict[str, Any]) -> None:
        if self.hass is None or not isinstance(self._initial_setup_state, dict):
            return
        self.hass.data.setdefault(RUNTIME_RELOAD_STATE, {})[RUNTIME_INITIAL_SETUP_STATE] = {
            "match": _build_initial_setup_match(entry_data),
            "state": dict(self._initial_setup_state),
        }

    async def async_step_user(self, user_input: Any = None):
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")

        errors = {}
        
        if user_input is not None:
            # Validate token first
            token = user_input[CONF_TOKEN].strip()
            if not token:
                errors["base"] = "invalid_token"
            
            # Only test API if token is provided
            if token and not errors:
                if not await _test_api_connection(token):
                    errors["base"] = "invalid_token"
            
            self._system_name = user_input.get(CONF_SYSTEM_NAME, "Solax System").strip()
            if not self._system_name:
                errors["base"] = "no_system_name"
            
            # Only proceed to next step if no errors
            if not errors:
                self._token = token
                self._scan_interval = user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
                return await self.async_step_add_inverter()

        # Initial form - include system name
        data_schema = vol.Schema({
            vol.Required(CONF_TOKEN): str,
            vol.Required(CONF_SYSTEM_NAME, default="Solax System"): str,
            vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): 
                vol.All(vol.Coerce(int), vol.Range(min=120, max=3600)),
        })

        return self.async_show_form(
            step_id="user", 
            data_schema=data_schema,
            errors=errors
        )

    async def async_step_add_inverter(self, user_input: Any = None):
        errors = {}
        
        if user_input is not None:
            if "serial" in user_input and user_input["serial"]:
                # Adding a new inverter
                serial = _normalize_serial(user_input["serial"])
                if serial and not _serial_exists(serial, self._inverters):
                    self._inverters.append(serial)
                elif serial:
                    errors["base"] = "duplicate_inverter"
                
            if "finish" in user_input and user_input["finish"]:
                if errors:
                    pass
                elif not self._inverters:
                    errors["base"] = "no_inverters"
                else:
                    self._pending_entry_data = {
                        CONF_TOKEN: self._token,
                        CONF_INVERTERS: self._inverters,
                        CONF_SCAN_INTERVAL: self._scan_interval,
                        CONF_SYSTEM_NAME: self._system_name,
                        CONF_ENTITY_PREFIX: _slugify_name(self._system_name),
                    }
                    self._initial_setup_state = await _classify_preflight_inverters(
                        self._token, self._inverters, self._scan_interval
                    )
                    if (
                        isinstance(self._initial_setup_state, dict)
                        and self._initial_setup_state.get("token_invalid")
                    ):
                        self._initial_setup_state = None
                        self._rate_limit_notice_inverters = []
                        errors["base"] = "invalid_token"
                    elif isinstance(self._initial_setup_state, dict):
                        self._rate_limit_notice_inverters = list(
                            self._initial_setup_state.get("rate_limited_inverters", [])
                        )
                    else:
                        self._rate_limit_notice_inverters = []
                    if errors:
                        pass
                    if self._rate_limit_notice_inverters:
                        return await self.async_step_rate_limit_notice()

                    if not errors:
                        self._stash_initial_setup_state(self._pending_entry_data)
                        return self.async_create_entry(
                            title=self._system_name,
                            data=self._pending_entry_data,
                        )

        # Show current inverters and option to add more
        inverters_list = "\n".join([f"• {sn}" for sn in self._inverters]) if self._inverters else "No inverters added yet"
        
        data_schema = vol.Schema({
            vol.Optional("serial"): str,
            vol.Required("finish", default=bool(self._inverters)): cv.boolean,
        })

        return self.async_show_form(
            step_id="add_inverter",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "count": len(self._inverters),
                "inverters_list": inverters_list,
                "system_name": self._system_name
            }
        )

    async def async_step_rate_limit_notice(self, user_input: Any = None):
        inverters_list = ", ".join(self._rate_limit_notice_inverters) or "Unknown"
        acknowledge_label = _rate_limit_acknowledge_label(
            inverters_list, self._scan_interval
        )
        errors = {}
        if user_input is not None:
            if user_input.get(acknowledge_label):
                data = self._pending_entry_data or {
                    CONF_TOKEN: self._token,
                    CONF_INVERTERS: self._inverters,
                    CONF_SCAN_INTERVAL: self._scan_interval,
                    CONF_SYSTEM_NAME: self._system_name,
                    CONF_ENTITY_PREFIX: _slugify_name(self._system_name),
                }
                self._stash_initial_setup_state(data)
                self._rate_limit_notice_inverters = []
                self._pending_entry_data = None
                return self.async_create_entry(title=self._system_name, data=data)
            errors["base"] = "acknowledge_rate_limit"

        return self.async_show_form(
            step_id="rate_limit_notice",
            data_schema=vol.Schema(
                {vol.Required(acknowledge_label, default=False): cv.boolean}
            ),
            errors=errors,
            description_placeholders={
                "count": len(self._rate_limit_notice_inverters),
                "inverters_list": inverters_list,
                "scan_interval": self._scan_interval,
            },
        )

    async def async_step_import(self, import_config: dict) -> FlowResult:
        """Handle configuration import from YAML."""
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")

        # Add this method for YAML import support
        _LOGGER.debug("Importing Solax configuration from YAML: %s", import_config)
        
        # Validate imported config
        token = import_config.get(CONF_TOKEN)
        if not token:
            return self.async_abort(reason="invalid_token")
        
        inverters = _dedupe_serials(import_config.get(CONF_INVERTERS, []))
        if not inverters:
            return self.async_abort(reason="no_inverters")
        
        # Set the configuration
        self._token = token
        self._inverters = inverters
        self._scan_interval = import_config.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        self._system_name = import_config.get(CONF_SYSTEM_NAME, "Solax System")
        
        # Create the entry
        return self.async_create_entry(
            title=self._system_name,
            data={
                CONF_TOKEN: self._token,
                CONF_INVERTERS: self._inverters,
                CONF_SCAN_INTERVAL: self._scan_interval,
                CONF_SYSTEM_NAME: self._system_name,
                CONF_ENTITY_PREFIX: import_config.get(CONF_ENTITY_PREFIX, _slugify_name(self._system_name)),
            }
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return SolaxOptionsFlowHandler(config_entry)


class SolaxOptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry):
        self._config_entry = config_entry
        self._inverters = _dedupe_serials(config_entry.data.get(CONF_INVERTERS, []))
        self._token = config_entry.data.get(CONF_TOKEN)
        self._scan_interval = config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        self._system_name = config_entry.data.get(CONF_SYSTEM_NAME, "Solax System")
        self._rate_limit_notice_inverters = []
        self._invalid_serial_notice_inverters = []
        self._invalid_serial_notice_details = {}
        self._show_rate_limit_after_invalid = False
        self._added_inverters = []
        self._token_changed = False

    async def async_step_init(self, user_input: Any = None):
        """Manage the options."""
        return await self.async_step_manage_inverters()

    async def async_step_manage_inverters(self, user_input: Any = None):
        errors = {}
        token = self._token
        system_name = self._system_name
        scan_interval = self._scan_interval
        
        if user_input is not None:
            token = user_input.get(CONF_TOKEN, self._token).strip()
            system_name = user_input.get(CONF_SYSTEM_NAME, self._system_name).strip()
            scan_interval = user_input.get(CONF_SCAN_INTERVAL, self._scan_interval)

            if "serial" in user_input and user_input["serial"]:
                # Adding a new inverter
                serial = _normalize_serial(user_input["serial"])
                if serial and not _serial_exists(serial, self._inverters):
                    self._inverters.append(serial)
                elif serial:
                    errors["base"] = "duplicate_inverter"
            
            if "remove_serial" in user_input and user_input["remove_serial"]:
                # Remove selected inverter
                remove_sn = user_input["remove_serial"]
                if remove_sn in self._inverters:
                    self._inverters.remove(remove_sn)
            
            if "finish" in user_input and user_input["finish"]:
                if not token:
                    errors["base"] = "invalid_token"

                if not system_name:
                    errors["base"] = "no_system_name"

                if not self._inverters:
                    errors["base"] = "no_inverters"

                # Validate token when saving options, especially if changed
                if not errors and token != self._token:
                    test_serial = self._inverters[0] if self._inverters else "TEST123"
                    if not await _test_api_connection(token, test_serial):
                        errors["base"] = "invalid_token"

                if not errors:
                    # Update the config entry
                    hass = self.hass
                    entry_id = self._config_entry.entry_id
                    self._token = token
                    self._system_name = system_name
                    self._scan_interval = scan_interval

                    old_inverters = _dedupe_serials(
                        self._config_entry.data.get(CONF_INVERTERS, [])
                    )
                    old_inverter_keys = {sn.casefold() for sn in old_inverters}
                    added_inverters = [
                        sn for sn in self._inverters if sn.casefold() not in old_inverter_keys
                    ]
                    token_changed = token != str(
                        self._config_entry.data.get(CONF_TOKEN, "")
                    ).strip()
                    self._added_inverters = list(added_inverters)
                    self._token_changed = token_changed

                    previous_data = {}
                    current_runtime = hass.data.get(DOMAIN, {}).get(entry_id, {})
                    current_coordinator = current_runtime.get("coordinator")
                    if current_coordinator and isinstance(
                        getattr(current_coordinator, "data", None), dict
                    ):
                        for serial, payload in current_coordinator.data.items():
                            if isinstance(payload, dict):
                                previous_data[serial] = dict(payload)

                    hass.data.setdefault(RUNTIME_RELOAD_STATE, {})[entry_id] = {
                        "data": previous_data,
                        "added_inverters": added_inverters,
                        "token_changed": token_changed,
                    }
                    
                    # Create updated data
                    updated_data = dict(self._config_entry.data)
                    updated_data[CONF_TOKEN] = token
                    updated_data[CONF_INVERTERS] = self._inverters
                    updated_data[CONF_SCAN_INTERVAL] = scan_interval
                    updated_data[CONF_SYSTEM_NAME] = system_name
                    # Keep entity prefix stable so system-name changes do not regenerate entities.
                    updated_data[CONF_ENTITY_PREFIX] = self._config_entry.data.get(
                        CONF_ENTITY_PREFIX,
                        _slugify_name(self._config_entry.data.get(CONF_SYSTEM_NAME, system_name)),
                    )
                    
                    hass.config_entries.async_update_entry(
                        self._config_entry,
                        data=updated_data
                    )
                    
                    # Reload the entry to apply changes
                    await hass.config_entries.async_reload(entry_id)

                    current_entry = hass.config_entries.async_get_entry(entry_id)
                    notifications_enabled = True
                    if current_entry is not None:
                        notifications_enabled = bool(
                            current_entry.options.get(CONF_RATE_LIMIT_NOTIFICATIONS, True)
                        )

                    coordinator_data = hass.data.get(DOMAIN, {}).get(entry_id, {})
                    coordinator = coordinator_data.get("coordinator")
                    observed_rate_limited = list(
                        getattr(coordinator, "rate_limited_inverters", []) if coordinator else []
                    )
                    observed_unauthorized = list(
                        getattr(coordinator, "unauthorized_inverters", []) if coordinator else []
                    )
                    observed_unauthorized_details = dict(
                        getattr(coordinator, "unauthorized_details", {}) if coordinator else {}
                    )

                    if self._token_changed:
                        self._invalid_serial_notice_inverters = observed_unauthorized
                    else:
                        added_casefold = {sn.casefold() for sn in self._added_inverters}
                        self._invalid_serial_notice_inverters = [
                            sn
                            for sn in observed_unauthorized
                            if sn.casefold() in added_casefold
                        ]
                    self._invalid_serial_notice_details = {
                        sn: observed_unauthorized_details.get(sn, {})
                        for sn in self._invalid_serial_notice_inverters
                    }

                    invalid_casefold = {
                        sn.casefold() for sn in self._invalid_serial_notice_inverters
                    }
                    if self._token_changed:
                        self._rate_limit_notice_inverters = [
                            sn
                            for sn in observed_rate_limited
                            if sn.casefold() not in invalid_casefold
                        ]
                    else:
                        added_casefold = {sn.casefold() for sn in self._added_inverters}
                        self._rate_limit_notice_inverters = [
                            sn
                            for sn in observed_rate_limited
                            if sn.casefold() in added_casefold
                            and sn.casefold() not in invalid_casefold
                        ]
                    self._show_rate_limit_after_invalid = bool(
                        notifications_enabled and self._rate_limit_notice_inverters
                    )
                    if self._invalid_serial_notice_inverters:
                        return await self.async_step_invalid_serial_notice()
                    if notifications_enabled and self._rate_limit_notice_inverters:
                        return await self.async_step_rate_limit_notice()
                    
                    return self.async_create_entry(title="", data={})

        self._token = token
        self._system_name = system_name
        self._scan_interval = scan_interval

        # Create options for remove dropdown
        remove_options = {sn: sn for sn in self._inverters} if self._inverters else {"": "No inverters to remove"}
        
        inverters_list = "\n".join([f"• {sn}" for sn in self._inverters]) if self._inverters else "No inverters configured"

        data_schema = vol.Schema({
            vol.Required(CONF_TOKEN, default=self._token): str,
            vol.Required(CONF_SYSTEM_NAME, default=self._system_name): str,
            vol.Required(CONF_SCAN_INTERVAL, default=self._scan_interval):
                vol.All(vol.Coerce(int), vol.Range(min=120, max=3600)),
            vol.Optional("serial"): str,
            vol.Optional("remove_serial"): vol.In(remove_options),
            vol.Required("finish", default=False): cv.boolean,
        })

        return self.async_show_form(
            step_id="manage_inverters",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "count": len(self._inverters),
                "inverters_list": inverters_list
            }
        )

    async def async_step_invalid_serial_notice(self, user_input: Any = None):
        details_text = _format_invalid_serial_details(
            self._invalid_serial_notice_inverters, self._invalid_serial_notice_details
        )
        acknowledge_label = _invalid_serial_acknowledge_label(details_text)
        errors = {}
        if user_input is not None:
            if user_input.get(acknowledge_label):
                self._invalid_serial_notice_inverters = []
                self._invalid_serial_notice_details = {}
                if self._show_rate_limit_after_invalid:
                    self._show_rate_limit_after_invalid = False
                    return await self.async_step_rate_limit_notice()
                return self.async_create_entry(title="", data={})
            errors["base"] = "acknowledge_invalid_serial"

        return self.async_show_form(
            step_id="invalid_serial_notice",
            data_schema=vol.Schema(
                {vol.Required(acknowledge_label, default=False): cv.boolean}
            ),
            errors=errors,
            description_placeholders={
                "count": len(self._invalid_serial_notice_inverters),
                "details": details_text,
            },
        )

    async def async_step_rate_limit_notice(self, user_input: Any = None):
        inverters_list = ", ".join(self._rate_limit_notice_inverters) or "Unknown"
        acknowledge_label = _rate_limit_acknowledge_label(
            inverters_list, self._scan_interval
        )
        errors = {}
        if user_input is not None:
            if user_input.get(acknowledge_label):
                self._rate_limit_notice_inverters = []
                return self.async_create_entry(title="", data={})
            errors["base"] = "acknowledge_rate_limit"

        return self.async_show_form(
            step_id="rate_limit_notice",
            data_schema=vol.Schema(
                {vol.Required(acknowledge_label, default=False): cv.boolean}
            ),
            errors=errors,
            description_placeholders={
                "count": len(self._rate_limit_notice_inverters),
                "inverters_list": inverters_list,
                "scan_interval": self._scan_interval,
            },
        )
