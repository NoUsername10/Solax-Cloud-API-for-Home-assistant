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
            with async_timeout.timeout(15):
                resp = await session.post(API_URL, json=payload, headers=headers)
                text = await resp.text()
                if resp.status != 200:
                    _LOGGER.debug("Solax HTTP error %s for %s: %s", resp.status, sn, text)
                    return { "error": f"HTTP {resp.status}", "raw": text }
                j = await resp.json()
                return j
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

                results[sn] = resp.get("result")
        self.data = results
        return self.data
