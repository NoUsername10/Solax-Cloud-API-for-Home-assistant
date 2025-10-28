import asyncio
import async_timeout
import logging
from datetime import timedelta

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
import aiohttp

from .const import API_URL, DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

class SolaxCoordinator(DataUpdateCoordinator):
    def __init__(self, hass: HomeAssistant, token: str, inverters: list, scan_interval: int = DEFAULT_SCAN_INTERVAL):
        super().__init__(
            hass,
            _LOGGER,
            name="Solax Multi Inverter",
            update_interval=timedelta(seconds=scan_interval),
        )
        self.token = token
        self.inverters = inverters
        self.data = {}

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
        timeout = aiohttp.ClientTimeout(total=30)
        
        # Get current time for rate limit tracking
        current_time = asyncio.get_event_loop().time()
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            for idx, sn in enumerate(self.inverters):
                # Add progressive delay based on position
                if idx > 0:
                    delay = min(2 + (idx * 0.5), 5)
                    _LOGGER.debug("Waiting %.1f seconds before querying inverter %s", delay, sn)
                    await asyncio.sleep(delay)
                
                # Check if this inverter was rate-limited - align with scan interval
                last_rate_limit = getattr(self, f'_last_rate_limit_{sn}', 0)
                skip_until = last_rate_limit + self.update_interval.total_seconds() * 0.55  # 55% of scan interval
                
                if current_time < skip_until:
                    _LOGGER.debug("Skipping %s - recently rate limited (skip until: %.1fs)", 
                                 sn, skip_until - current_time)
                    results[sn] = {"error": "rate_limit_skip", "skip_until": skip_until}
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
                
                # Handle specific error codes
                if code == 104:  # Rate limit exceeded
                    _LOGGER.warning(
                        "API rate limit exceeded for %s. Will skip for %.1f seconds.",
                        sn, self.update_interval.total_seconds() * 0.55
                    )
                    # Mark this inverter as rate-limited until next cycle
                    setattr(self, f'_last_rate_limit_{sn}', current_time)
                    results[sn] = { 
                        "error": "rate_limit", 
                        "code": code, 
                        "exception": resp.get("exception"),
                        "skip_until": current_time + self.update_interval.total_seconds() * 0.55
                    }
                    
                    # Add extra delay before next inverter
                    if idx < len(self.inverters) - 1:
                        _LOGGER.debug("Adding 5 second delay after rate limit")
                        await asyncio.sleep(5)
                    continue
                    
                elif code == 1003:  # Data Unauthorized
                    _LOGGER.error("API unauthorized for %s. Check token and inverter serial.", sn)
                    raise ConfigEntryAuthFailed(f"API unauthorized for {sn}")
                    
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
        rate_limited = len([r for r in results.values() if r and r.get("error") == "rate_limit"])
        
        if rate_limited > 0:
            _LOGGER.warning(
                "%d/%d inverters rate limited. Consider increasing scan interval from %ds",
                rate_limited, len(self.inverters), self.update_interval.total_seconds()
            )
        
        _LOGGER.debug("Successfully updated data for %d/%d inverters", successful_updates, len(self.inverters))
        
        self.data = results
        return self.data
