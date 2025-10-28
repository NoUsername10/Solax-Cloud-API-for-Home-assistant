from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from .const import DOMAIN, RESULT_FIELDS, FIELD_MAPPINGS, NUMERIC_FIELDS, MAPPED_FIELDS, SENSOR_NAMES, SYSTEM_SENSOR_NAMES, HIDDEN_SENSORS


import logging
_LOGGER = logging.getLogger(__name__)

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    return

async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    inverters = entry.data.get("inverters", [])

    await coordinator.async_config_entry_first_refresh()
    
    entities = []

    for sn in inverters:
        inverter_data = coordinator.data.get(sn)
        
        if not inverter_data or not isinstance(inverter_data, dict):
            available_fields = RESULT_FIELDS
        else:
            available_fields = [
                field for field in RESULT_FIELDS 
                if field in inverter_data and inverter_data.get(field) is not None
            ]

        for field in available_fields:
            # Use human-readable name without serial number
            human_name = SENSOR_NAMES.get(field, f"Solax {field}")
            unique = f"{sn}_{field}".lower().replace(" ", "_")
            
            if field in NUMERIC_FIELDS:
                unit, kind = NUMERIC_FIELDS[field]
                entities.append(SolaxFieldSensor(coordinator, sn, field, human_name, unique, unit))
            else:
                entities.append(SolaxFieldSensor(coordinator, sn, field, human_name, unique, None))

        # Only create DC total sensor if at least one DC channel has data
        if inverter_data and isinstance(inverter_data, dict):
            dc_channels = [inverter_data.get(f"powerdc{i}") for i in range(1, 5)]
            if any(channel is not None for channel in dc_channels):
                human_name = SYSTEM_SENSOR_NAMES["dc_total_inverter"]  
                unique = f"{sn}_dc_total"
                entities.append(SolaxComputedSensor(coordinator, sn, "dc_total", human_name, unique))

    # System total sensors with human-readable names
    if any(coordinator.data.get(sn) for sn in inverters):
        entities.append(SolaxSystemTotalSensor(coordinator, inverters, "ac_total", SYSTEM_SENSOR_NAMES["ac_total"]))
        entities.append(SolaxSystemTotalSensor(coordinator, inverters, "dc_total", SYSTEM_SENSOR_NAMES["dc_total"]))
        entities.append(SolaxSystemTotalSensor(coordinator, inverters, "yieldtoday_total", SYSTEM_SENSOR_NAMES["yieldtoday_total"]))
        entities.append(SolaxSystemTotalSensor(coordinator, inverters, "yieldtotal_total", SYSTEM_SENSOR_NAMES["yieldtotal_total"]))

    async_add_entities(entities, update_before_add=True)


class SolaxFieldSensor(CoordinatorEntity):
    def __init__(self, coordinator, serial, field, name, unique_id, unit=None):
        super().__init__(coordinator)
        self._serial = serial
        self._field = field
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._unit = unit

        # Set entity category for hidden sensors
        if field in HIDDEN_SENSORS:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC


    @property
    def state(self):
        inv = self.coordinator.data.get(self._serial)
        if not inv or not isinstance(inv, dict):
            return None
        
        val = inv.get(self._field)
        
        # Return human-readable value if mapping exists
        if self._field in FIELD_MAPPINGS and val is not None:
            mapping = FIELD_MAPPINGS[self._field]
            return mapping.get(str(val), f"Unknown ({val})")
        
        return val

    @property
    def available(self):
        data = self.coordinator.data.get(self._serial)
        if not data or not isinstance(data, dict):
            return False
        return self._field in data and data.get(self._field) is not None

    @property
    def device_info(self):
        inv = self.coordinator.data.get(self._serial)
        ident = (DOMAIN, self._serial)
        if isinstance(inv, dict):
            inverter_sn = inv.get("inverterSN") or self._serial
            return {
                "identifiers": {(DOMAIN, inverter_sn)},
                "name": f"Solax Inverter {inverter_sn}",
                "manufacturer": "Solax",
                "model": self._get_mapped_value("inverterType"),
            }
        return {"identifiers": {ident}, "name": f"Solax Inverter {self._serial}"}

    def _get_mapped_value(self, field):
        """Helper to get mapped value for a field."""
        inv = self.coordinator.data.get(self._serial)
        if not inv or not isinstance(inv, dict):
            return None
        
        val = inv.get(field)
        if field in FIELD_MAPPINGS and val is not None:
            return FIELD_MAPPINGS[field].get(str(val), str(val))
        return val

    @property
    def state_class(self):
        if self._unit == "kWh":
            return SensorStateClass.TOTAL_INCREASING
        elif self._unit == "W":
            return SensorStateClass.MEASUREMENT
        elif self._unit == "%":
            return SensorStateClass.MEASUREMENT
        return None

    @property
    def device_class(self):
        if self._unit == "kWh":
            return SensorDeviceClass.ENERGY
        elif self._unit == "W":
            return SensorDeviceClass.POWER
        elif self._unit == "%":
            return SensorDeviceClass.BATTERY
        return None

    @property
    def extra_state_attributes(self):
        attrs = {}
        inv = self.coordinator.data.get(self._serial)
        if not inv or not isinstance(inv, dict):
            return attrs
    
        # Store raw value for THIS sensor's field if it's a mapped field
        if self._field in MAPPED_FIELDS and self._field in inv and inv[self._field] is not None:
            attrs[f"{self._field}_raw"] = inv[self._field]
            # Also include the mapped value as attribute for consistency
            if self._field in FIELD_MAPPINGS:
                mapped_value = FIELD_MAPPINGS[self._field].get(str(inv[self._field]), f"Unknown ({inv[self._field]})")
                attrs[f"{self._field}_text"] = mapped_value
    
        # Add timestamp attributes (available for all sensors)
        attrs["last_update_raw"] = inv.get("uploadTime")
        attrs["utc_date_time"] = inv.get("utcDateTime")
    
        return attrs

    @property
    def unit_of_measurement(self):
        return self._unit


class SolaxComputedSensor(CoordinatorEntity):
    def __init__(self, coordinator, serial, metric, name, unique_id):
        super().__init__(coordinator)
        self._serial = serial
        self._metric = metric
        self._name = name
        self._unique_id = unique_id

    @property
    def name(self):
        return self._name

    @property
    def unique_id(self):
        return self._unique_id

    @property
    def available(self):
        """Return if entity is available."""
        data = self.coordinator.data.get(self._serial)
        if not data or not isinstance(data, dict):
            return False
        # Check if we have at least one DC channel with data
        dc_channels = [data.get(f"powerdc{i}") for i in range(1, 5)]
        return any(channel is not None for channel in dc_channels)

    @property
    def device_info(self):
        inv = self.coordinator.data.get(self._serial)
        inverter_sn = (inv.get("inverterSN") if isinstance(inv, dict) else self._serial) or self._serial
        return {"identifiers": {(DOMAIN, inverter_sn)}, "name": f"Solax Inverter {inverter_sn}"}

    @property
    def state(self):
        inv = self.coordinator.data.get(self._serial)
        if not inv or not isinstance(inv, dict):
            return None
        total = 0
        for i in range(1, 5):
            power = inv.get(f"powerdc{i}")
            if power is not None:
                total += power
        return total

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT

    @property
    def device_class(self):
        return SensorDeviceClass.POWER

    @property
    def unit_of_measurement(self):
        return "W"


class SolaxSystemTotalSensor(CoordinatorEntity):
    def __init__(self, coordinator, inverters, metric, name):
        super().__init__(coordinator)
        self._inverters = inverters
        self._metric = metric
        self._name = name

    @property
    def name(self):
        return self._name

    @property
    def unique_id(self):
        return f"system_{self._metric}"

    @property
    def device_info(self):
        """Return device information for the system totals device."""
        total_inverters = len(self._inverters)
        active_inverters = self._count_active_inverters()
        
        return {
            "identifiers": {(DOMAIN, "system_totals")},
            "name": f"Solax System ({active_inverters}/{total_inverters} Inverters)",
            "manufacturer": "Solax",
            "model": f"Multi-Inverter System ({active_inverters} active, {total_inverters} total)",
        }
    
    def _count_active_inverters(self):
        """Count how many inverters are currently reporting data."""
        active_count = 0
        for sn in self._inverters:
            inv_data = self.coordinator.data.get(sn)
            if (inv_data and 
                isinstance(inv_data, dict) and 
                not inv_data.get("error") and
                inv_data.get("acpower") is not None):
                active_count += 1
        return active_count
    
    @property
    def available(self):
        """Return if entity is available."""
        for sn in self._inverters:
            inv = self.coordinator.data.get(sn)
            if inv and isinstance(inv, dict):
                if self._metric == "ac_total" and inv.get("acpower") is not None:
                    return True
                elif self._metric == "dc_total" and any(inv.get(f"powerdc{i}") is not None for i in range(1, 5)):
                    return True
                elif self._metric == "yieldtoday_total" and inv.get("yieldtoday") is not None:
                    return True
                elif self._metric == "yieldtotal_total" and inv.get("yieldtotal") is not None:
                    return True
        return False

    @property
    def state(self):
        total = 0
        for sn in self._inverters:
            inv = self.coordinator.data.get(sn)
            if not inv or not isinstance(inv, dict):
                continue
            if self._metric == "ac_total":
                power = inv.get("acpower")
                if power is not None:
                    total += power
            elif self._metric == "dc_total":
                dc_total = 0
                for i in range(1, 5):
                    power = inv.get(f"powerdc{i}")
                    if power is not None:
                        dc_total += power
                total += dc_total
            elif self._metric == "yieldtoday_total":
                yield_today = inv.get("yieldtoday")
                if yield_today is not None:
                    total += yield_today
            elif self._metric == "yieldtotal_total":
                yield_total = inv.get("yieldtotal")
                if yield_total is not None:
                    total += yield_total
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
        return SensorDeviceClass.POWER

    @property
    def unit_of_measurement(self):
        if self._metric in ("ac_total", "dc_total"):
            return "W"
        return "kWh"
