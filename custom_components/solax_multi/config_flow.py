from typing import Any
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from .const import DOMAIN, CONF_TOKEN, CONF_INVERTERS, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL

STEP_USER_DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_TOKEN): str,
    vol.Required(CONF_INVERTERS, default=""): str,
    vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): int,
})

class SolaxFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: Any = None):
        if user_input is not None:
            token = user_input[CONF_TOKEN]
            inv_text = user_input[CONF_INVERTERS]
            scan = user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            inverters = [s.strip() for s in inv_text.replace('\n',',').split(',') if s.strip()]
            return self.async_create_entry(title="Solax Multi Inverter", data={
                CONF_TOKEN: token,
                CONF_INVERTERS: inverters,
                CONF_SCAN_INTERVAL: scan,
            })

        return self.async_show_form(step_id="user", data_schema=STEP_USER_DATA_SCHEMA)
