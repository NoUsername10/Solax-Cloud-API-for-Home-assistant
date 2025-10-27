from typing import Any
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from .const import DOMAIN, CONF_TOKEN, CONF_INVERTERS, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL

STEP_USER_DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_TOKEN): str,
    vol.Required(CONF_INVERTERS, default=""): str,
    vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(vol.Coerce(int), vol.Range(min=30, max=3600)),
})

class SolaxFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: Any = None):
        errors = {}
        
        if user_input is not None:
            try:
                # Validate input
                token = user_input[CONF_TOKEN].strip()
                if not token:
                    raise ValueError("API token is required")
                
                inv_text = user_input[CONF_INVERTERS]
                inverters = [s.strip() for s in inv_text.replace('\n',',').split(',') if s.strip()]
                if not inverters:
                    raise ValueError("At least one inverter serial number is required")
                
                scan_interval = user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
                
                return self.async_create_entry(
                    title="Solax Multi Inverter", 
                    data={
                        CONF_TOKEN: token,
                        CONF_INVERTERS: inverters,
                        CONF_SCAN_INTERVAL: scan_interval,
                    }
                )
                
            except ValueError as err:
                errors["base"] = str(err)

        return self.async_show_form(
            step_id="user", 
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors
        )
