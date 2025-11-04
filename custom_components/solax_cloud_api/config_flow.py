from typing import Any
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
import aiohttp
import async_timeout
from .const import DOMAIN, CONF_TOKEN, CONF_INVERTERS, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, API_URL

class SolaxFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self):
        super().__init__()
        self._inverters = []
        self._token = None
        self._scan_interval = DEFAULT_SCAN_INTERVAL
        self._system_name = "Solax System"

    async def _test_api_connection(self, token: str, serial: str = "TEST123") -> bool:
        """Test if the API token is valid."""
        try:
            headers = {"Content-Type": "application/json", "tokenId": token}
            payload = {"wifiSn": "TEST123"}
            
            async with async_timeout.timeout(10):
                async with aiohttp.ClientSession() as session:
                    async with session.post(API_URL, json=payload, headers=headers) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            # Check if we get proper error response (not 1001 unauthorized)
                            return data.get("code") != 1001
                        return False
        except Exception:
            return False

    async def async_step_user(self, user_input: Any = None):
        errors = {}
        
        if user_input is not None:
            try:
                # Validate token first
                token = user_input[CONF_TOKEN].strip()
                if not token:
                    raise ValueError("invalid_token")
                
                # Test API connection
                if not await self._test_api_connection(token):
                    raise ValueError("invalid_token")
                
                self._token = token
                self._scan_interval = user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
                self._system_name = user_input.get("system_name", "Solax System").strip()
                
                if not self._system_name:
                    raise ValueError("no_system_name")
                
                # Move to inverter entry step
                return await self.async_step_add_inverter()
                
            except ValueError as err:
                errors["base"] = str(err.args[0]) if err.args else str(err)

        # Initial form - include system name
        data_schema = vol.Schema({
            vol.Required(CONF_TOKEN): str,
            vol.Required("system_name", default="Solax System"): str,
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
                serial = user_input["serial"].strip()
                if serial and serial not in self._inverters:
                    self._inverters.append(serial)
                
            if "finish" in user_input and user_input["finish"]:
                if not self._inverters:
                    errors["base"] = "no_inverters"
                else:
                    return self.async_create_entry(
                        title=self._system_name,
                        data={
                            CONF_TOKEN: self._token,
                            CONF_INVERTERS: self._inverters,
                            CONF_SCAN_INTERVAL: self._scan_interval,
                            "system_name": self._system_name,
                        }
                    )

        # Show current inverters and option to add more
        inverters_list = "\n".join([f"• {sn}" for sn in self._inverters]) if self._inverters else "No inverters added yet"
        
        data_schema = vol.Schema({
            vol.Optional("serial"): str,
            vol.Required("finish", default=bool(self._inverters)): bool,
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

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return SolaxOptionsFlowHandler(config_entry)


class SolaxOptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry):
        self.config_entry = config_entry
        self._inverters = list(config_entry.data.get(CONF_INVERTERS, []))
        self._token = config_entry.data.get(CONF_TOKEN)
        self._scan_interval = config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        self._system_name = config_entry.data.get("system_name", "Solax System")

    async def async_step_init(self, user_input: Any = None):
        """Manage the options."""
        return await self.async_step_manage_inverters()

    async def async_step_manage_inverters(self, user_input: Any = None):
        errors = {}
        
        if user_input is not None:
            if "serial" in user_input and user_input["serial"]:
                # Adding a new inverter
                serial = user_input["serial"].strip()
                if serial and serial not in self._inverters:
                    self._inverters.append(serial)
            
            if "remove_serial" in user_input and user_input["remove_serial"]:
                # Remove selected inverter
                remove_sn = user_input["remove_serial"]
                if remove_sn in self._inverters:
                    self._inverters.remove(remove_sn)
            
            if "finish" in user_input and user_input["finish"]:
                if not self._inverters:
                    errors["base"] = "no_inverters"
                else:
                    # Update the config entry
                    hass = self.hass
                    entry_id = self.config_entry.entry_id
                    
                    # Create updated data
                    updated_data = dict(self.config_entry.data)
                    updated_data[CONF_INVERTERS] = self._inverters
                    updated_data[CONF_SCAN_INTERVAL] = self._scan_interval
                    updated_data["system_name"] = self._system_name
                    
                    hass.config_entries.async_update_entry(
                        self.config_entry,
                        data=updated_data
                    )
                    
                    # Reload the entry to apply changes
                    await hass.config_entries.async_reload(entry_id)
                    
                    return self.async_create_entry(title="", data={})

        # Create options for remove dropdown
        remove_options = {sn: sn for sn in self._inverters} if self._inverters else {"": "No inverters to remove"}
        
        inverters_list = "\n".join([f"• {sn}" for sn in self._inverters]) if self._inverters else "No inverters configured"
        
        data_schema = vol.Schema({
            vol.Optional("serial"): str,
            vol.Optional("remove_serial"): vol.In(remove_options),
            vol.Required("finish", default=False): bool,
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
