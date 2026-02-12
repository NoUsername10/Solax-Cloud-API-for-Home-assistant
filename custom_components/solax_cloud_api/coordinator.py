import asyncio
import async_timeout
import logging
from datetime import timedelta

from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.util import dt as dt_util

from .const import API_URL, DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


def _is_rate_limited_response(resp: dict) -> bool:
    """Return True when Solax response indicates API throttling/rate limit."""
    if not isinstance(resp, dict):
        return False

    code = resp.get("code")
    if code in (3, 104):
        return True

    exception = str(resp.get("exception", "")).lower()
    rate_limit_markers = (
        "rate limit",
        "maximum call threshold",
        "suspend the request",
        "current minute > threshold",
        "within the current minute",
        "too many requests",
    )
    return any(marker in exception for marker in rate_limit_markers)


class SolaxCoordinator(DataUpdateCoordinator):
    def __init__(
        self,
        hass: HomeAssistant,
        token: str,
        inverters: list,
        scan_interval: int = DEFAULT_SCAN_INTERVAL,
        initial_data: dict | None = None,
        initial_refresh_inverters: list[str] | None = None,
    ):
        super().__init__(
            hass,
            _LOGGER,
            name="Solax Multi Inverter",
            update_interval=timedelta(seconds=scan_interval),
        )
        self.token = token
        self.inverters = inverters
        self.data = {}
        if isinstance(initial_data, dict):
            for serial, payload in initial_data.items():
                if isinstance(payload, dict):
                    self.data[serial] = dict(payload)
        self.last_successful_update = None
        self.last_update_attempt = None
        self.rate_limited_inverters = []
        self.rate_limited_details = {}
        self.unauthorized_inverters = []
        self.unauthorized_details = {}
        self.last_rate_limit_at = None
        self._initial_refresh_inverters = (
            {sn.casefold() for sn in initial_refresh_inverters}
            if initial_refresh_inverters is not None
            else None
        )

    async def _fetch_one(self, session, sn):
        headers = { "Content-Type": "application/json", "tokenId": self.token }
        payload = { "wifiSn": sn }
        try:
            async with async_timeout.timeout(15):
                async with session.post(API_URL, json=payload, headers=headers) as resp:
                    text = await resp.text()
                    if resp.status != 200:
                        _LOGGER.warning("Solax HTTP error %s for %s: %s", resp.status, sn, text)
                        return { "error": f"HTTP {resp.status}", "raw": text }
                    
                    try:
                        j = await resp.json()
                    except Exception as json_err:
                        _LOGGER.warning("JSON parse error for %s: %s", sn, json_err)
                        return { "error": f"JSON Error: {json_err}", "raw": text }
                        
                    return j
        except asyncio.TimeoutError:
            _LOGGER.warning("Timeout fetching data for %s", sn)
            return { "error": "Timeout" }
        except Exception as e:
            _LOGGER.warning("Failed request for %s: %s", sn, e)
            return { "error": str(e) }

    async def _async_update_data(self):
        results = {}
        self.last_update_attempt = dt_util.utcnow()
        self.rate_limited_inverters = []
        self.rate_limited_details = {}
        self.unauthorized_inverters = []
        self.unauthorized_details = {}
        
        # Get current time for rate limit tracking
        current_time = asyncio.get_running_loop().time()
        
        session = async_get_clientsession(self.hass)
        for idx, sn in enumerate(self.inverters):
            if (
                self._initial_refresh_inverters is not None
                and sn.casefold() not in self._initial_refresh_inverters
            ):
                previous = self.data.get(sn)
                if isinstance(previous, dict):
                    results[sn] = dict(previous)
                    previous_error = previous.get("error")
                    if previous_error == "data_unauthorized":
                        self.unauthorized_inverters.append(sn)
                        self.unauthorized_details[sn] = {
                            "code": previous.get("code", 1003),
                            "exception": previous.get("exception"),
                        }
                    elif previous_error in ("rate_limit", "rate_limit_skip"):
                        self.rate_limited_inverters.append(sn)
                        self.rate_limited_details[sn] = {
                            "reason": "carried_from_preflight",
                            "code": previous.get("code"),
                            "exception": previous.get("exception"),
                        }
                        self.last_rate_limit_at = dt_util.utcnow()
                else:
                    results[sn] = {}
                continue

            # Add progressive delay based on position
            if idx > 0:
                delay = min(1 + (idx * 0.5), 5)
                _LOGGER.debug("Waiting %.1f seconds before querying inverter %s", delay, sn)
                await asyncio.sleep(delay)
            
            # Check if this inverter was rate-limited - align with scan interval
            last_rate_limit = getattr(self, f'_last_rate_limit_{sn}', 0)
            skip_until = last_rate_limit + self.update_interval.total_seconds() * 0.55  # 55% of scan interval
            
            if current_time < skip_until:
                _LOGGER.debug("Skipping %s - recently rate limited (skip until: %.1fs)", sn, skip_until - current_time)
                previous = self.data.get(sn)
                if isinstance(previous, dict) and previous.get("error") == "data_unauthorized":
                    # Keep unauthorized state sticky during temporary throttling windows.
                    results[sn] = dict(previous)
                    self.unauthorized_inverters.append(sn)
                    self.unauthorized_details[sn] = {
                        "code": previous.get("code", 1003),
                        "exception": previous.get("exception"),
                    }
                elif isinstance(previous, dict) and not previous.get("error"):
                    results[sn] = dict(previous)
                else:
                    results[sn] = {"error": "rate_limit_skip", "skip_until": skip_until}
                self.rate_limited_inverters.append(sn)
                self.rate_limited_details[sn] = {
                    "reason": "cooldown_active",
                    "retry_in_seconds": round(skip_until - current_time, 1),
                }
                self.last_rate_limit_at = dt_util.utcnow()
                continue
            
            _LOGGER.debug("Fetching data for inverter %s (%d/%d)", sn, idx + 1, len(self.inverters))
            resp = await self._fetch_one(session, sn)
            
            if isinstance(resp, Exception):
                _LOGGER.warning("Fetch exception for %s: %s", sn, resp)
                results[sn] = None
                continue

            if not isinstance(resp, dict):
                _LOGGER.warning("Bad response for %s: %s", sn, resp)
                results[sn] = None
                continue

            code = resp.get("code")
            success = resp.get("success", False)
            
            # Handle rate-limit responses from Solax (seen as code 104 and code 3)
            if _is_rate_limited_response(resp):
                _LOGGER.warning(
                    "API rate limit exceeded for %s (code=%s). Will skip for %.1f seconds.",
                    sn, code, self.update_interval.total_seconds() * 0.55
                )
                # Mark this inverter as rate-limited until next cycle
                setattr(self, f'_last_rate_limit_{sn}', current_time)
                previous = self.data.get(sn)
                if isinstance(previous, dict) and previous.get("error") == "data_unauthorized":
                    # Wrong-serial/no-access should take precedence over transient rate limiting.
                    results[sn] = dict(previous)
                    self.unauthorized_inverters.append(sn)
                    self.unauthorized_details[sn] = {
                        "code": previous.get("code", 1003),
                        "exception": previous.get("exception"),
                    }
                elif isinstance(previous, dict) and not previous.get("error"):
                    results[sn] = dict(previous)
                else:
                    results[sn] = {
                        "error": "rate_limit",
                        "code": code,
                        "exception": resp.get("exception"),
                        "skip_until": current_time + self.update_interval.total_seconds() * 0.55
                    }
                self.rate_limited_inverters.append(sn)
                self.rate_limited_details[sn] = {
                    "reason": "api_rate_limit",
                    "code": code,
                    "exception": resp.get("exception"),
                    "retry_in_seconds": round(self.update_interval.total_seconds() * 0.55, 1),
                }
                self.last_rate_limit_at = dt_util.utcnow()
                
                # Add extra delay before next inverter
                if idx < len(self.inverters) - 1:
                    _LOGGER.debug("Adding 5 second delay after rate limit")
                    await asyncio.sleep(5)
                continue

            if code == 1001:  # Token unauthorized
                _LOGGER.error("API token unauthorized. Reauthentication required.")
                raise ConfigEntryAuthFailed("API token unauthorized")

            if code == 1003:  # Data unauthorized (invalid serial or no access)
                _LOGGER.error(
                    "Data unauthorized for inverter %s (code=1003). "
                    "Marking this inverter unavailable. Exception: %s",
                    sn,
                    resp.get("exception"),
                )
                results[sn] = {
                    "error": "data_unauthorized",
                    "code": code,
                    "exception": resp.get("exception"),
                    "raw": resp,
                }
                self.unauthorized_inverters.append(sn)
                self.unauthorized_details[sn] = {
                    "code": code,
                    "exception": resp.get("exception"),
                }
                continue
                
            elif not success or (code is not None and code != 0):
                _LOGGER.warning("API error for %s: code=%s, exception=%s", sn, code, resp.get("exception"))
                results[sn] = { "error": True, "code": code, "exception": resp.get("exception"), "raw": resp }
                continue

            # Clean the result data - remove null values to save space
            result_data = resp.get("result", {})
            if result_data:
                cleaned_data = {k: v for k, v in result_data.items() if v is not None}
                results[sn] = cleaned_data
                # Clear any previous rate limit flag on success
                if hasattr(self, f'_last_rate_limit_{sn}'):
                    delattr(self, f'_last_rate_limit_{sn}')
            else:
                results[sn] = {}
                    
        successful_updates = len([r for r in results.values() if r and not r.get("error")])
        rate_limited = len(self.rate_limited_inverters)
        
        if rate_limited > 0:
            _LOGGER.warning(
                "%d/%d inverters rate limited. Consider increasing scan interval from %ds",
                rate_limited, len(self.inverters), self.update_interval.total_seconds()
            )
        
        _LOGGER.debug("Successfully updated data for %d/%d inverters", successful_updates, len(self.inverters))
        if successful_updates > 0:
            self.last_successful_update = dt_util.utcnow()

        # Only skip non-new inverters on the first refresh after a reload.
        self._initial_refresh_inverters = None

        self.data = results
        return self.data
