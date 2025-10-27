import asyncio
import async_timeout
import logging
from datetime import timedelta

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.core import HomeAssistant
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
        timeout = aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            tasks = [ self._fetch_one(session, sn) for sn in self.inverters ]
            responses = await asyncio.gather(*tasks, return_exceptions=True)

            for idx, resp in enumerate(responses):
                sn = self.inverters[idx]
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
                if not success or (code is not None and code != 0):
                    _LOGGER.warning("API error for %s: code=%s, exception=%s", sn, code, resp.get("exception"))
                    results[sn] = { "error": True, "code": code, "exception": resp.get("exception"), "raw": resp }
                    continue

                # Clean the result data - remove null values to save space
                result_data = resp.get("result", {})
                if result_data:
                    # Remove keys with None values
                    cleaned_data = {k: v for k, v in result_data.items() if v is not None}
                    results[sn] = cleaned_data
                else:
                    results[sn] = {}
        
        successful_updates = len([r for r in results.values() if r and not r.get("error")])
        _LOGGER.debug("Successfully updated data for %d/%d inverters", successful_updates, len(self.inverters))
        
        self.data = results
        return self.data
