from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .const import DOMAIN, PLATFORMS
from .coordinator import SolaxCoordinator

async def async_setup(hass: HomeAssistant, config: dict):
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    hass.data.setdefault(DOMAIN, {})
    token = entry.data.get("api_token")
    inverters = entry.data.get("inverters", [])
    scan = entry.data.get("scan_interval", 60)

    coordinator = SolaxCoordinator(hass, token, inverters, scan)
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "entry": entry,
    }

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.helpers.discovery.async_load_platform(platform, DOMAIN, { "entry_id": entry.entry_id }, entry.data)
        )

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = all(
        await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    )
    hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
