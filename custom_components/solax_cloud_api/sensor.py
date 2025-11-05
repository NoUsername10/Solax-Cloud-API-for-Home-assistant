from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass, SensorEntity
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

        # Sensors per inverter
        for field in available_fields:
            unique = f"{system_slug}_{field}_{sn}".lower().replace(" ", "_")
            unit = NUMERIC_FIELDS[field][0] if field in NUMERIC_FIELDS else None

            entities.append(SolaxFieldSensor(coordinator, sn, field, unique, unit, system_slug))
        
        # Add inverter efficiency sensor
        entities.append(SolaxInverterEfficiencySensor(coordinator, sn, f"{system_slug}_inverter_efficiency_{sn}", system_slug))

        # DC total per inverter
        # Use a consistent key for the unique_id and the metric/translation_key
        metric_inverter_dc = "dc_total_inverter"
        unique_dc_total = f"{system_slug}_{metric_inverter_dc}_{sn}".lower().replace(" ", "_")
        entities.append(SolaxComputedSensor(coordinator, sn, metric_inverter_dc, unique_dc_total, system_slug))
                
    # System totals (only once)
    if any(coordinator.data.get(sn) for sn in inverters):
        entities.append(SolaxSystemTotalSensor(coordinator, inverters, "ac_total"))
        entities.append(SolaxSystemTotalSensor(coordinator, inverters, "dc_total"))
        entities.append(SolaxSystemTotalSensor(coordinator, inverters, "yieldtoday_total"))
        entities.append(SolaxSystemTotalSensor(coordinator, inverters, "yieldtotal_total"))
        entities.append(SolaxSystemTotalSensor(coordinator, inverters, "systemEfficiency"))

    async_add_entities(entities, update_before_add=True)


class SolaxFieldSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, serial, field, unique_id, unit=None, system_slug=None):
        super().__init__(coordinator)
        self._serial = serial
        self._field = field
        self._unit = unit
        self._attr_unique_id = unique_id
        self._attr_entity_registry_enabled_default = True

        if not system_slug:
            raise ValueError("System slug must be provided for SolaxFieldSensor")

        self.translation_key = field

        # Entity ID includes system prefix + field + serial
        suggested_id = f"{system_slug}_{field}_{serial}".lower()
        self._attr_suggested_object_id = suggested_id
        self.entity_id = f"sensor.{suggested_id}"  # hard-set ID

        if field in HIDDEN_SENSORS:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC


        if field in NUMERIC_FIELDS:
            unit, field_type = NUMERIC_FIELDS[field]
            self._unit = unit

            if field_type == "energy":  # kWh
                self._attr_state_class = SensorStateClass.TOTAL_INCREASING
                self._attr_device_class = SensorDeviceClass.ENERGY
                self._attr_suggested_display_precision = 1
            elif field_type == "power":  # W
                self._attr_state_class = SensorStateClass.MEASUREMENT
                self._attr_device_class = SensorDeviceClass.POWER
                self._attr_suggested_display_precision = 0
            elif field_type == "battery":  # %
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
            model = str(inverter_type_val)

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
    
        attrs["last_update_raw"] = inv.get("uploadTime")
        attrs["utc_date_time"] = inv.get("utcDateTime")
    
        return attrs

    @property
    def unit_of_measurement(self):
        return self._unit


class SolaxInverterEfficiencySensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    translation_key = "inverterEfficiency"

    def __init__(self, coordinator, serial, unique_id, system_slug=None):
        super().__init__(coordinator)
        self._serial = serial
        self._attr_unique_id = unique_id
        self._attr_device_class = None
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_suggested_display_precision = 1
        if system_slug:
            self._attr_suggested_object_id = f"{system_slug}_inverter_efficiency_{serial}".lower()

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
    def unit_of_measurement(self):
        return "%"

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
        
        model = "Unknown"
        if isinstance(inv, dict) and inv.get("inverterType") is not None:
            model = str(inv.get("inverterType"))

        return {
            "identifiers": {(DOMAIN, inverter_sn)},
            "name": f"Solax Inverter {inverter_sn}",
            "manufacturer": "Solax",
            "model": model,
            "serial_number": inverter_sn,
        }

class SolaxComputedSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    
    def __init__(self, coordinator, serial, metric, unique_id, system_slug=None):
        super().__init__(coordinator)
        self._serial = serial
        self._metric = metric
        self.translation_key = metric
        self._unique_id = unique_id
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_device_class = SensorDeviceClass.POWER

        if not system_slug:
            raise ValueError("System slug must be provided for SolaxComputedSensor")

        self.entity_id = f"sensor.{system_slug}_{metric}_{serial}".lower()

    @property
    def available(self):
        data = self.coordinator.data.get(self._serial)
        if not data or not isinstance(data, dict):
            return False
        return not data.get("error")

    @property
    def device_info(self):
        inv = self.coordinator.data.get(self._serial)
        inverter_sn = (inv.get("inverterSN") if isinstance(inv, dict) else self._serial) or self._serial

        model = "Unknown"
        if isinstance(inv, dict) and inv.get("inverterType") is not None:
            model = str(inv.get("inverterType"))

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
        if not inv or not isinstance(inv, dict):
            return 0
        
        total = 0
        has_any_dc_field = False
        for i in range(1, 5):
            field = f"powerdc{i}"
            if field in inv:
                has_any_dc_field = True
                power = inv.get(field)
                if power is not None:
                    total += power
        
        if not has_any_dc_field:
            if inv.get("acpower") is None:
                return 0
            return None

        return total

    @property
    def unit_of_measurement(self):
        return "W"


class SolaxSystemTotalSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, inverters, metric):
        super().__init__(coordinator)
        self._inverters = inverters
        self._metric = metric
        self.translation_key = metric
        
        metric_map = {
            "ac_total": "ac_power",
            "dc_total": "dc_power", 
            "yieldtoday_total": "energy_today",
            "yieldtotal_total": "energy_total",
            "systemEfficiency": "system_efficiency"
        }
        
        system_name = self.coordinator.config_entry.data.get("system_name", "solax_system")
        system_slug = system_name.lower().replace(" ", "_").replace("-", "_")
        
        self._attr_unique_id = f"{system_slug}_{metric_map.get(self._metric, self._metric)}_solax"


    @property
    def device_info(self):
        total_inverters = len(self._inverters)
        active_inverters = self._count_active_inverters()
        system_name = self.coordinator.config_entry.data.get("system_name", "Solax System")
        return {
            "identifiers": {(DOMAIN, f"system_totals_{system_name.replace(' ', '_').lower()}")},
            "name": f"{system_name} ({active_inverters}/{total_inverters} Inverters)",
            "manufacturer": "Solax",
            "model": f"Multi-Inverter System ({active_inverters} active, {total_inverters} total)",
        }
    
    def _count_active_inverters(self):
        active_count = 0
        for sn in self._inverters:
            inv_data = self.coordinator.data.get(sn)
            if (inv_data and isinstance(inv_data, dict) and not inv_data.get("error") and inv_data.get("acpower") is not None):
                active_count += 1
        return active_count
    
    @property
    def available(self):
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
                elif self._metric == "systemEfficiency":
                    if inv.get("acpower") is not None and any(inv.get(f"powerdc{i}") is not None for i in range(1, 5)):
                        return True
        return False

    @property
    def state(self):
        if self._metric == "systemEfficiency":
            total_ac, total_dc = 0, 0
            for sn in self._inverters:
                inv = self.coordinator.data.get(sn)
                if not inv or not isinstance(inv, dict) or inv.get("error"):
                    continue
                ac = inv.get("acpower") or 0
                dc = sum(inv.get(f"powerdc{i}", 0) for i in range(1, 5))
                total_ac += ac
                total_dc += dc
            if total_dc > 0:
                return round((total_ac / total_dc) * 100, 1)
            return 0

        total = 0
        for sn in self._inverters:
            inv = self.coordinator.data.get(sn)
            if not inv or not isinstance(inv, dict) or inv.get("error"):
                continue

            field_map = {
                "ac_total": "acpower",
                "yieldtoday_total": "yieldtoday",
                "yieldtotal_total": "yieldtotal"
            }

            if self._metric in field_map:
                value = inv.get(field_map[self._metric])
                if value is not None:
                    total += value
            elif self._metric == "dc_total":
                dc_total = 0
                for i in range(1, 5):
                    power = inv.get(f"powerdc{i}")
                    if power is not None:
                        dc_total += power
                total += dc_total

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
