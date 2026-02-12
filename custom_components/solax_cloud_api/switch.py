from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.translation import async_get_translations
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_ENTITY_PREFIX,
    CONF_RATE_LIMIT_NOTIFICATIONS,
    CONF_SYSTEM_NAME,
    DOMAIN,
)


async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]

    system_name = entry.data.get(CONF_SYSTEM_NAME)
    if not system_name:
        raise ValueError("System name must be provided in integration setup")

    system_slug = entry.data.get(
        CONF_ENTITY_PREFIX,
        system_name.lower().replace(" ", "_").replace("-", "_"),
    )

    lang = getattr(hass.config, "language", "en")
    translations = await async_get_translations(hass, lang, "entity", [DOMAIN])
    name_key = f"component.{DOMAIN}.entity.switch.rate_limit_notifications.name"
    switch_name = translations.get(name_key, "API Rate Limit Notifications")

    async_add_entities(
        [
            SolaxRateLimitNotificationSwitch(
                hass, entry.entry_id, coordinator, system_name, system_slug, switch_name
            )
        ]
    )


class SolaxRateLimitNotificationSwitch(CoordinatorEntity, SwitchEntity):
    _attr_has_entity_name = False

    def __init__(self, hass, entry_id, coordinator, system_name, system_slug, switch_name):
        super().__init__(coordinator)
        self.hass = hass
        self._entry_id = entry_id
        self._system_name = system_name
        self._system_slug = system_slug
        self._attr_name = switch_name
        self._attr_unique_id = f"{system_slug}_rate_limit_notifications_solax"
        self.entity_id = f"switch.{system_slug}_rate_limit_notifications".lower()

    @property
    def is_on(self):
        entry = self.hass.config_entries.async_get_entry(self._entry_id)
        if entry is None:
            return True
        return bool(entry.options.get(CONF_RATE_LIMIT_NOTIFICATIONS, True))

    @property
    def available(self):
        return True

    @property
    def device_info(self):
        total_inverters = len(getattr(self.coordinator, "inverters", []))
        if total_inverters == 1:
            system_model = "Single Inverter System"
        else:
            system_model = "Multi-Inverter System"
        return {
            "identifiers": {(DOMAIN, f"system_totals_{self._system_slug}")},
            "name": f"{self._system_name} System Totals",
            "manufacturer": "Solax",
            "model": system_model,
        }

    async def async_turn_on(self, **kwargs):
        await self._async_set_notification_state(True)

    async def async_turn_off(self, **kwargs):
        await self._async_set_notification_state(False)

    async def _async_set_notification_state(self, enabled: bool):
        entry = self.hass.config_entries.async_get_entry(self._entry_id)
        if entry is None:
            return

        updated_options = dict(entry.options)
        updated_options[CONF_RATE_LIMIT_NOTIFICATIONS] = enabled
        self.hass.config_entries.async_update_entry(entry, options=updated_options)

        entry_data = self.hass.data.get(DOMAIN, {}).get(self._entry_id, {})
        refresh_notification = entry_data.get("refresh_rate_limit_notification")
        if refresh_notification:
            refresh_notification()

        self.async_write_ha_state()
