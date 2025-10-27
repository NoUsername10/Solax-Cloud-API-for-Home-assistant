from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.const import DEVICE_CLASS_POWER, DEVICE_CLASS_ENERGY
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from .const import DOMAIN, RESULT_FIELDS, INVERTER_STATUSES, ERROR_CODES, INVERTER_TYPES

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    return

async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    inverters = entry.data.get("inverters", [])

    entities = []
    numeric_map = {
        "acpower": ("W", "power"),
        "powerdc1": ("W", "power"),
        "powerdc2": ("W", "power"),
        "powerdc3": ("W", "power"),
        "powerdc4": ("W", "power"),
        "yieldtoday": ("kWh", "energy"),
        "yieldtotal": ("kWh", "energy"),
        "feedinpower": ("W", "power"),
        "feedinenergy": ("kWh", "energy"),
        "consumeenergy": ("kWh", "energy"),
        "batPower": ("W", "power"),
    }

    for sn in inverters:
        for field in RESULT_FIELDS:
            name = f"Solax {field} {sn}"
            unique = f"{sn}_{field}".lower().replace(" ", "_")
            if field in numeric_map:
                unit, kind = numeric_map[field]
                entities.append(SolaxFieldSensor(coordinator, sn, field, name, unique, unit))
            else:
                entities.append(SolaxFieldSensor(coordinator, sn, field, name, unique, None))

        entities.append(SolaxComputedSensor(coordinator, sn, "dc_total", f"Solax DC Total {sn}", f"{sn}_dc_total"))

    entities.append(SolaxSystemTotalSensor(coordinator, inverters, "ac_total", "Solax AC Total System"))
    entities.append(SolaxSystemTotalSensor(coordinator, inverters, "dc_total", "Solax DC Total System"))
    entities.append(SolaxSystemTotalSensor(coordinator, inverters, "yieldtoday_total", "Solax Yield Today Total"))
    entities.append(SolaxSystemTotalSensor(coordinator, inverters, "yieldtotal_total", "Solax Yield Total System"))

    async_add_entities(entities, update_before_add=True)


class SolaxFieldSensor(CoordinatorEntity):
    def __init__(self, coordinator, serial, field, name, unique_id, unit=None):
        super().__init__(coordinator)
        self._serial = serial
        self._field = field
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._unit = unit

    @property
    def name(self):
        return self._attr_name

    @property
    def unique_id(self):
        return self._attr_unique_id

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
                "model": inv.get("inverterType"),
            }
        return {"identifiers": {ident}, "name": f"Solax Inverter {self._serial}"}

    @property
    def state(self):
        inv = self.coordinator.data.get(self._serial)
        if not inv or not isinstance(inv, dict):
            return None
        val = inv.get(self._field)
        return val

    @property
    def state_class(self):
        if self._unit == "kWh":
            return SensorStateClass.TOTAL_INCREASING
        elif self._unit == "W":
            return SensorStateClass.MEASUREMENT
        return None

    @property
    def device_class(self):
        if self._unit == "kWh":
            return SensorDeviceClass.ENERGY
        elif self._unit == "W":
            return SensorDeviceClass.POWER
        return None

    @property
    def extra_state_attributes(self):
        attrs = {}
        inv = self.coordinator.data.get(self._serial)
        if not inv or not isinstance(inv, dict):
            return attrs
        status = inv.get("inverterStatus")
        if status is not None:
            attrs["inverter_status_text"] = INVERTER_STATUSES.get(str(status), f"Unknown ({status})")
        # map inverter type to friendly name if available
        itype = inv.get("inverterType")
        if itype is not None:
            attrs["inverter_type"] = INVERTER_TYPES.get(str(itype), str(itype))
        attrs["last_update_raw"] = inv.get("uploadTime")
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
    def device_info(self):
        inv = self.coordinator.data.get(self._serial)
        inverter_sn = (inv.get("inverterSN") if isinstance(inv, dict) else self._serial) or self._serial
        return {"identifiers": {(DOMAIN, inverter_sn)}, "name": f"Solax Inverter {inverter_sn}"}

    @property
    def state(self):
        inv = self.coordinator.data.get(self._serial)
        if not inv or not isinstance(inv, dict):
            return None
        dc1 = inv.get("powerdc1") or 0
        dc2 = inv.get("powerdc2") or 0
        dc3 = inv.get("powerdc3") or 0
        dc4 = inv.get("powerdc4") or 0
        return dc1 + dc2 + dc3 + dc4

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
    def state(self):
        total = 0
        for sn in self._inverters:
            inv = self.coordinator.data.get(sn)
            if not inv or not isinstance(inv, dict):
                continue
            if self._metric == "ac_total":
                total += inv.get("acpower") or 0
            elif self._metric == "dc_total":
                total += (inv.get("powerdc1") or 0) + (inv.get("powerdc2") or 0) + (inv.get("powerdc3") or 0) + (inv.get("powerdc4") or 0)
            elif self._metric == "yieldtoday_total":
                total += inv.get("yieldtoday") or 0
            elif self._metric == "yieldtotal_total":
                total += inv.get("yieldtotal") or 0
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
