from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass, SensorEntity
from homeassistant.helpers.translation import async_get_translations
from .const import DOMAIN, RESULT_FIELDS, NUMERIC_FIELDS, MAPPED_FIELDS, HIDDEN_SENSORS

import logging
_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    return


async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    inverters = entry.data.get("inverters", [])
    system_name = entry.data.get("system_name")
    if not system_name:
        raise ValueError("System name must be provided in integration setup")
    system_slug = system_name.lower().replace(" ", "_").replace("-", "_")

    # Fetch the translations for the integration's sensor platform
    translations = await async_get_translations(
        hass, entry.data.get("lang", "en"), "sensor"
    )

    # Build inverter type map
    type_map = {}
    for k, v in translations.items():
        if "inverterType.state." in k:
            key = k.split(".")[-1]  # e.g. "1", "2"
            type_map[key] = v

    await coordinator.async_config_entry_first_refresh()
    entities = []

    for sn in inverters:
        inverter_data = coordinator.data.get(sn)

        available_fields = [
            field for field in RESULT_FIELDS
            if inverter_data and isinstance(inverter_data, dict) and field in inverter_data and inverter_data.get(field) is not None
        ] if inverter_data else RESULT_FIELDS

        # Standard sensors from API fields
        for field in available_fields:
            name_key = f"component.{DOMAIN}.entity.sensor.{field}.name"
            human_name = translations.get(name_key, f"Solax {field}")
            entities.append(SolaxFieldSensor(coordinator, sn, field, human_name, system_slug, translations))
        
        # Inverter Efficiency computed sensor
        name_key = f"component.{DOMAIN}.entity.sensor.inverterEfficiency.name"
        human_name = translations.get(name_key, "Inverter Efficiency")
        entities.append(SolaxInverterEfficiencySensor(coordinator, sn, human_name, system_slug, type_map))

        # DC Total per inverter computed sensor (based on original logic)
        if inverter_data and isinstance(inverter_data, dict) and any(inverter_data.get(f"powerdc{i}") is not None for i in range(1, 5)):
            name_key = f"component.{DOMAIN}.entity.sensor.dc_total_inverter.name"
            human_name = translations.get(name_key, "DC Power Inverter Total")
            # The metric passed to the constructor MUST be "dc_total" to match the original entity_id and unique_id pattern
            entities.append(SolaxComputedSensor(coordinator, sn, "dc_total", human_name, system_slug, type_map))
                
    # System total sensors (based on original logic)
    if any(coordinator.data.get(sn) for sn in inverters):
        system_sensor_keys = ["ac_total", "dc_total", "yieldtoday_total", "yieldtotal_total", "systemEfficiency"]
        for key in system_sensor_keys:
            name_key = f"component.{DOMAIN}.entity.sensor.{key}.name"
            sensor_name = translations.get(name_key, key.replace("_", " ").title())
            full_name = f"{system_name} {sensor_name}"
            entities.append(SolaxSystemTotalSensor(coordinator, inverters, key, full_name))

    async_add_entities(entities, update_before_add=True)


class SolaxFieldSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = False # We provide the name manually, so this must be False

    def __init__(self, coordinator, serial, field, human_name, system_slug, type_map):
        super().__init__(coordinator)
        self._serial = serial
        self._field = field
        self._translations = translations 
        self._type_map = type_map
        self._attr_name = human_name # Use the name passed from async_setup_entry
        self._attr_unique_id = f"{system_slug}_{field}_{serial}".lower().replace(" ", "_")
        
        # Manually set entity_id to match original behavior
        self.entity_id = f"sensor.{system_slug}_{field}_{serial}".lower()

        if field in HIDDEN_SENSORS: self._attr_entity_category = EntityCategory.DIAGNOSTIC
        if field in NUMERIC_FIELDS:
            unit, field_type = NUMERIC_FIELDS[field]
            if field_type == "energy":
                self._attr_state_class = SensorStateClass.TOTAL_INCREASING
                self._attr_device_class = SensorDeviceClass.ENERGY
                self._attr_suggested_display_precision = 1
            elif field_type == "power":
                self._attr_state_class = SensorStateClass.MEASUREMENT
                self._attr_device_class = SensorDeviceClass.POWER
                self._attr_suggested_display_precision = 0
            elif field_type == "battery":
                self._attr_state_class = SensorStateClass.MEASUREMENT
                self._attr_device_class = SensorDeviceClass.BATTERY
                self._attr_suggested_display_precision = 1

    @property
    def state(self):
        inv = self.coordinator.data.get(self._serial)
        if not inv or not isinstance(inv, dict):
            return 0 if self._field in NUMERIC_FIELDS else None
        
        if inv.get("error"):
            return None

        val = inv.get(self._field)
        
        if val is None:
            return None
        
        if self._field in MAPPED_FIELDS:
            # Build the translation key for this field and value
            state_key = f"component.{DOMAIN}.entity.sensor.{self._field}.state.{val}"
            # Return the translated state, or fallback to string value
            translated_state = self._translations.get(state_key)
        if translated_state:
            return translated_state
        # Fallback to raw value if no translation found
        return str(val)

        if self._field in NUMERIC_FIELDS:
            return val
        
        return val

    @property
    def device_class(self):
        if self._field in NUMERIC_FIELDS:
            field_type = NUMERIC_FIELDS[self._field][1]
            if field_type == "energy":
                return SensorDeviceClass.ENERGY
            elif field_type == "power":
                return SensorDeviceClass.POWER
            elif field_type == "battery":
                return SensorDeviceClass.BATTERY
        return None

    @property
    def state_class(self):
        if self._field in NUMERIC_FIELDS:
            field_type = NUMERIC_FIELDS[self._field][1]
            if field_type == "energy":
                return SensorStateClass.TOTAL_INCREASING
            else:
                return SensorStateClass.MEASUREMENT
        return None

    @property
    def available(self):
        data = self.coordinator.data.get(self._serial)
        if not data or not isinstance(data, dict):
            return False
    
        if data.get("error"):
            return False
        
        if self._field in MAPPED_FIELDS or self._field in NUMERIC_FIELDS:
            return data.get(self._field) is not None

        return True

    @property
    def device_info(self):
        inv = self.coordinator.data.get(self._serial)
        if not inv or not isinstance(inv, dict):
            return {
                "identifiers": {(DOMAIN, self._serial)},
                "name": f"Solax Inverter {self._serial}",
                "manufacturer": "Solax",
                "model": "Unknown",
            }
        
        inverter_sn = inv.get("inverterSN") or self._serial
        
        model = "Unknown"
        inverter_type_val = inv.get("inverterType")
        if inverter_type_val is not None:
            model = self._type_map.get(str(inverter_type_val), str(inverter_type_val))

        return {
            "identifiers": {(DOMAIN, inverter_sn)},
            "name": f"Solax Inverter {inverter_sn}",
            "manufacturer": "Solax",
            "model": model,
            "serial_number": inverter_sn,
        }

    @property
    def extra_state_attributes(self):
        attrs = {}
        inv = self.coordinator.data.get(self._serial)
        if not inv or not isinstance(inv, dict):
            return attrs
    
        # Add raw and text attributes for mapped fields
        if self._field in MAPPED_FIELDS and self._field in inv and inv[self._field] is not None:
            raw_val = inv[self._field]
            attrs[f"{self._field}_raw"] = raw_val
            
            # Get the translated text value
            state_key = f"component.{DOMAIN}.entity.sensor.{self._field}.state.{raw_val}"
            mapped_value = self._translations.get(state_key, f"Unknown ({raw_val})")
            attrs[f"{self._field}_text"] = mapped_value
    
        # Add timestamp attributes (available for all sensors)
        attrs["last_update_raw"] = inv.get("uploadTime")
        attrs["utc_date_time"] = inv.get("utcDateTime")
    
        return attrs

    @property
    def unit_of_measurement(self):
        if self._field in NUMERIC_FIELDS:
            unit, _ = NUMERIC_FIELDS[self._field]
            return unit
        return None

class SolaxInverterEfficiencySensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = False # We provide the name manually, so this must be False
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "%"
    _attr_suggested_display_precision = 1

    def __init__(self, coordinator, serial, human_name, system_slug, type_map):
        super().__init__(coordinator)
        self._serial = serial
        self._type_map = type_map
        self._attr_name = human_name
        self._attr_device_class = None
        self._attr_suggested_display_precision = 1
        self._attr_unique_id = f"{system_slug}_inverter_efficiency_{serial}"
        
        # Manually set entity_id to match original behavior
        self.entity_id = f"sensor.{system_slug}_inverter_efficiency_{serial}".lower()

    @property
    def state(self):
        inv = self.coordinator.data.get(self._serial)
        if not inv or not isinstance(inv, dict):
            return 0
        dc_total = sum(inv.get(f"powerdc{i}", 0) for i in range(1, 5))
        ac = inv.get("acpower") or 0
        if dc_total > 0:
            return round((ac / dc_total) * 100, 1)
        return 0

    @property
    def available(self):
        inv = self.coordinator.data.get(self._serial)
        if not inv or not isinstance(inv, dict):
            return False
        return any(inv.get(f"powerdc{i}") is not None for i in range(1, 5))

    @property
    def device_info(self):
        inv = self.coordinator.data.get(self._serial)
        inverter_sn = (inv.get("inverterSN") if isinstance(inv, dict) else self._serial) or self._serial
        inverter_type = str(inv.get("inverterType")) if isinstance(inv, dict) else None
        model = self._type_map.get(inverter_type, inverter_type or "Unknown")
                    
        return {
            "identifiers": {(DOMAIN, inverter_sn)},
            "name": f"Solax Inverter {inverter_sn}",
            "manufacturer": "Solax",
            "model": model,
            "serial_number": inverter_sn,
        }

class SolaxComputedSensor(CoordinatorEntity, SensorEntity):
    """Used for the 'DC Power Inverter Total' sensor"""
    _attr_has_entity_name = False # We provide the name manually
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = "W"

    def __init__(self, coordinator, serial, metric, name, system_slug, type_map):
        super().__init__(coordinator)
        self._serial = serial
        self._type_map = type_map
        self._metric = metric 
        self._attr_name = name 
     
        self._attr_unique_id = f"{system_slug}_{metric}_{serial}".lower().replace(" ", "_")
        self.entity_id = f"sensor.{system_slug}_{metric}_{serial}".lower()

    @property
    def available(self):
        data = self.coordinator.data.get(self._serial)
        if not data or not isinstance(data, dict): return False
        return any(data.get(f"powerdc{i}") is not None for i in range(1, 5))

    @property
    def device_info(self):
        inv = self.coordinator.data.get(self._serial)
        inverter_sn = (inv.get("inverterSN") if isinstance(inv, dict) else self._serial) or self._serial
            
        if inverter_type_val is not None:
            #Use type_map for human-readable model names
            model = self._type_map.get(str(inverter_type_val), str(inverter_type_val))
    
        return {
            "identifiers": {(DOMAIN, inverter_sn)},
            "name": f"Solax Inverter {inverter_sn}", 
            "manufacturer": "Solax",
            "model": model,
            "serial_number": inverter_sn,
        }
        
    @property
    def state(self):
        inv = self.coordinator.data.get(self._serial)
        if not inv or not isinstance(inv, dict): return None
        return sum(inv.get(f"powerdc{i}") or 0 for i in range(1, 5))


class SolaxSystemTotalSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = False # We provide the name manually

    def __init__(self, coordinator, inverters, metric, name):
        super().__init__(coordinator)
        self._inverters = inverters
        self._metric = metric
        self._attr_name = name 

        # Set device class and other attributes in __init__ 
        if self._metric in ("yieldtoday_total", "yieldtotal_total"):
            self._attr_device_class = SensorDeviceClass.ENERGY
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        elif self._metric == "systemEfficiency":
            self._attr_state_class = SensorStateClass.MEASUREMENT
        else: # ac_total, dc_total
            self._attr_device_class = SensorDeviceClass.POWER
            self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def unique_id(self):
        metric_map = {
            "ac_total": "ac_power", "dc_total": "dc_power", 
            "yieldtoday_total": "energy_today", "yieldtotal_total": "energy_total",
            "systemEfficiency": "system_efficiency"
        }
        system_name = self.coordinator.config_entry.data.get("system_name", "solax_system")
        system_slug = system_name.lower().replace(" ", "_").replace("-", "_")
        return f"{system_slug}_{metric_map[self._metric]}_solax"

    @property
    def device_info(self):
        total_inverters = len(self._inverters)
        active_inverters = self._count_active_inverters()
        system_name = self.coordinator.config_entry.data.get("system_name", "Solax System")
        return {"identifiers": {(DOMAIN, f"system_totals_{system_name.replace(' ', '_').lower()}")},
                "name": f"{system_name} ({active_inverters}/{total_inverters} Inverters)",
                "manufacturer": "Solax", "model": f"Multi-Inverter System ({active_inverters} active, {total_inverters} total)"}
    
    def _count_active_inverters(self):
        return sum(1 for sn in self._inverters if self.coordinator.data.get(sn) and not self.coordinator.data[sn].get("error") and self.coordinator.data[sn].get("acpower") is not None)
    
    @property
    def available(self):
        for sn in self._inverters:
            inv = self.coordinator.data.get(sn)
            if inv and isinstance(inv, dict):
                if self._metric == "ac_total" and inv.get("acpower") is not None: return True
                elif self._metric == "dc_total" and any(inv.get(f"powerdc{i}") is not None for i in range(1, 5)): return True
                elif self._metric == "yieldtoday_total" and inv.get("yieldtoday") is not None: return True
                elif self._metric == "yieldtotal_total" and inv.get("yieldtotal") is not None: return True
                elif self._metric == "systemEfficiency" and "acpower" in inv and any(f"powerdc{i}" in inv for i in range(1, 5)): return True
        return False

    @property
    def state(self):
        if self._metric == "systemEfficiency":
            total_ac = sum(inv.get("acpower", 0) or 0 for sn in self._inverters if (inv := self.coordinator.data.get(sn)) and isinstance(inv, dict) and not inv.get("error"))
            total_dc = sum(inv.get(f"powerdc{i}", 0) or 0 for sn in self._inverters if (inv := self.coordinator.data.get(sn)) and isinstance(inv, dict) and not inv.get("error"))
            return round((total_ac / total_dc) * 100, 1) if total_dc > 0 else 0
        
        total = 0
        field_map = {"ac_total": "acpower", "yieldtoday_total": "yieldtoday", "yieldtotal_total": "yieldtotal"}
        for sn in self._inverters:
            inv = self.coordinator.data.get(sn)
            if not inv or not isinstance(inv, dict) or inv.get("error"): continue
            
            if self._metric in field_map:
                total += inv.get(field_map[self._metric], 0) or 0
            elif self._metric == "dc_total":
                total += sum(inv.get(f"powerdc{i}", 0) or 0 for i in range(1, 5))
        return total

    @property
    def state_class(self):
        if self._metric in ("yieldtoday_total", "yieldtotal_total"):
            return SensorStateClass.TOTAL_INCREASING
        return SensorStateClass.MEASUREMENT

    @property
    def device_class(self):
        if self._metric in ("yieldtoday_total", "yieldtotal_total"):
            return SensorDeviceClass.ENERGY
        if self._metric == "systemEfficiency":
            return None
        return SensorDeviceClass.POWER

    @property
    def unit_of_measurement(self):
        if self._metric == "systemEfficiency":
            return "%"
        if self._metric in ("ac_total", "dc_total"):
            return "W"
        return "kWh"
