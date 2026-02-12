import re
from datetime import timedelta
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.translation import async_get_translations
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util, slugify

from .const import (
    CONF_ENTITY_PREFIX,
    CONF_INVERTERS,
    CONF_SYSTEM_NAME,
    DOMAIN,
    HIDDEN_SENSORS,
    MAPPED_FIELDS,
    NUMERIC_FIELDS,
    RESULT_FIELDS,
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    return


def get_translation_name(translations, domain, sensor_key, state_value=None, default=None):
    normalized_sensor_key = _translation_sensor_key(sensor_key)
    if state_value is not None:
        flat_state_key = f"component.{domain}.entity.sensor.{normalized_sensor_key}.state.{state_value}"
        if flat_state_key in translations:
            return translations[flat_state_key]
        return str(state_value)

    flat_name_key = f"component.{domain}.entity.sensor.{normalized_sensor_key}.name"
    return translations.get(flat_name_key, default or sensor_key)


def _translation_sensor_key(sensor_key):
    key = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", str(sensor_key))
    key = re.sub(r"[^a-zA-Z0-9_-]+", "_", key)
    return key.lower().strip("_-")


def _flatten_translations(data, parent_key=""):
    items = {}
    for key, value in data.items():
        new_key = f"{parent_key}.{key}" if parent_key else key
        if isinstance(value, dict):
            state_dict = value.get("state")
            if isinstance(state_dict, dict):
                for state_key, state_val in state_dict.items():
                    items[f"{new_key}.state.{state_key}"] = state_val
            nested = {k: v for k, v in value.items() if k != "state"}
            items.update(_flatten_translations(nested, new_key))
        else:
            items[new_key] = value
    return items

async def _load_local_translations(hass, lang):
    import json
    import os

    translations_file = os.path.join(
        hass.config.path(f"custom_components/{DOMAIN}/translations"), f"{lang}.json"
    )
    if not os.path.exists(translations_file):
        translations_file = os.path.join(
            hass.config.path(f"custom_components/{DOMAIN}/translations"), "en.json"
        )

    def _load():
        with open(translations_file, "r", encoding="utf-8") as file:
            return json.load(file)

    loaded = await hass.async_add_executor_job(_load)

    # translations/*.json for custom integrations are rooted at the integration
    # level (title/config/options/entity/...). Keep backward compatibility with
    # older nested "component.<domain>" layouts if encountered.
    if isinstance(loaded, dict) and "component" in loaded and isinstance(loaded.get("component"), dict):
        domain_block = loaded.get("component", {}).get(DOMAIN, {})
    else:
        domain_block = loaded

    flattened = _flatten_translations(domain_block)
    return {f"component.{DOMAIN}.{key}": value for key, value in flattened.items()}


def _cleanup_removed_inverter_artifacts(hass, entry, system_slug, inverters):
    configured_casefold = {sn.casefold() for sn in inverters}
    slug_prefix = f"{system_slug}_".casefold()
    entity_registry = er.async_get(hass)
    for reg_entry in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
        unique_id = reg_entry.unique_id or ""
        unique_id_casefold = unique_id.casefold()
        if not unique_id_casefold.startswith(slug_prefix):
            continue
        # Keep system total sensors.
        if unique_id_casefold.endswith("_solax"):
            continue
        has_serial_suffix = any(
            unique_id_casefold.endswith(f"_{serial}") for serial in configured_casefold
        )
        if not has_serial_suffix:
            entity_registry.async_remove(reg_entry.entity_id)

    device_registry = dr.async_get(hass)
    for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id):
        domain_ids = [ident for ident in device.identifiers if ident[0] == DOMAIN]
        if not domain_ids:
            continue
        removable = True
        for _, identifier in domain_ids:
            if identifier.startswith("system_totals_"):
                removable = False
                break
            if identifier.casefold() in configured_casefold:
                removable = False
                break
        if removable:
            device_registry.async_remove_device(device.id)


async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    inverters = entry.data.get(CONF_INVERTERS, [])
    system_name = entry.data.get(CONF_SYSTEM_NAME)
    if not system_name:
        raise ValueError("System name must be provided in integration setup")

    system_slug = entry.data.get(
        CONF_ENTITY_PREFIX,
        system_name.lower().replace(" ", "_").replace("-", "_"),
    )
    _cleanup_removed_inverter_artifacts(hass, entry, system_slug, inverters)
    lang = getattr(hass.config, "language", "en")
    translations = await async_get_translations(hass, lang, "entity", [DOMAIN])
    translation_prefix = f"component.{DOMAIN}.entity.sensor."
    if not any(key.startswith(translation_prefix) for key in translations):
        translations = await _load_local_translations(hass, lang)

    # Build inverter type map once
    inverter_type_key = _translation_sensor_key("inverterType")
    type_map = {
        k.split(".")[-1]: v
        for k, v in translations.items()
        if f"entity.sensor.{inverter_type_key}.state." in k
    }

    entities = []
    created_field_entities = set()
    created_dc_total_entities = set()
    created_efficiency_entities = set()

    # Always expose inverter API access status so invalid serials are visible in UI.
    for sn in inverters:
        human_name = (
            get_translation_name(translations, DOMAIN, "apiAccessStatus")
            or "API Access Status"
        )
        entities.append(
            SolaxInverterApiAccessStatusSensor(
                coordinator, sn, human_name, system_slug, translations, type_map
            )
        )

    def _build_new_field_entities():
        new_entities = []
        for sn in inverters:
            inverter_data = coordinator.data.get(sn)
            if not isinstance(inverter_data, dict) or inverter_data.get("error"):
                continue

            for field in RESULT_FIELDS:
                if inverter_data.get(field) is None:
                    continue
                key = (sn.casefold(), field)
                if key in created_field_entities:
                    continue
                created_field_entities.add(key)
                human_name = get_translation_name(translations, DOMAIN, field)
                new_entities.append(
                    SolaxFieldSensor(
                        coordinator, sn, field, human_name, system_slug, translations, type_map
                    )
                )

            serial_key = sn.casefold()
            if serial_key not in created_efficiency_entities:
                created_efficiency_entities.add(serial_key)
                human_name = (
                    get_translation_name(translations, DOMAIN, "inverterEfficiency")
                    or "Inverter Efficiency"
                )
                new_entities.append(
                    SolaxInverterEfficiencySensor(
                        coordinator, sn, human_name, system_slug, type_map
                    )
                )

            has_dc_values = any(
                inverter_data.get(f"powerdc{i}") is not None for i in range(1, 5)
            )
            if has_dc_values and serial_key not in created_dc_total_entities:
                created_dc_total_entities.add(serial_key)
                human_name = (
                    get_translation_name(translations, DOMAIN, "dc_total_inverter")
                    or "DC Power Inverter Total"
                )
                new_entities.append(
                    SolaxComputedSensor(
                        coordinator, sn, "dc_total", human_name, system_slug, type_map
                    )
                )
        return new_entities

    # Create field/DC sensors that are available right now.
    entities.extend(_build_new_field_entities())

    system_sensor_keys = [
        "ac_total",
        "dc_total",
        "yieldtoday_total",
        "yieldtotal_total",
        "systemEfficiency",
        "systemHealth",
        "rateLimitStatus",
        "lastPollAttempt",
        "nextScheduledPoll",
    ]
    for key in system_sensor_keys:
        human_name = get_translation_name(translations, DOMAIN, key) or key.replace(
            "_", " "
        ).title()
        legacy_entity_name = f"{system_name} {human_name}"
        entities.append(
            SolaxSystemTotalSensor(
                coordinator,
                inverters,
                key,
                human_name,
                system_name,
                system_slug,
                translations,
                legacy_entity_name,
            )
        )

    async_add_entities(entities, update_before_add=True)

    def _handle_coordinator_update():
        # Add newly available field/DC sensors without requiring an integration reload.
        new_entities = _build_new_field_entities()
        if new_entities:
            async_add_entities(new_entities, update_before_add=True)

    entry.async_on_unload(coordinator.async_add_listener(_handle_coordinator_update))


class SolaxFieldSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = False

    def __init__(
        self, coordinator, serial, field, human_name, system_slug, translations, type_map
    ):
        super().__init__(coordinator)
        self._serial = serial
        self._field = field
        self._translations = translations
        self._type_map = type_map
        self._attr_name = human_name
        self._attr_unique_id = f"{system_slug}_{field}_{serial}".lower().replace(" ", "_")
        self.entity_id = f"sensor.{system_slug}_{field}_{serial}".lower()

        if field in HIDDEN_SENSORS:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
            self._attr_entity_registry_enabled_default = False

        if field in NUMERIC_FIELDS:
            unit, field_type = NUMERIC_FIELDS[field]
            self._attr_native_unit_of_measurement = unit
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
    def native_value(self):
        inv = self.coordinator.data.get(self._serial)
        if not inv or not isinstance(inv, dict):
            return None

        if inv.get("error"):
            return None

        val = inv.get(self._field)
        if val is None:
            return None

        if self._field in MAPPED_FIELDS:
            return get_translation_name(
                self._translations, DOMAIN, self._field, state_value=val, default=str(val)
            )

        return val

    @property
    def available(self):
        data = self.coordinator.data.get(self._serial)
        if not data or not isinstance(data, dict):
            return False
        if data.get("error"):
            return False
        return data.get(self._field) is not None

    @property
    def device_info(self):
        inv = self.coordinator.data.get(self._serial)
        inverter_sn = inv.get("inverterSN") if isinstance(inv, dict) else None
        inverter_type_val = inv.get("inverterType") if isinstance(inv, dict) else None

        model = "Unknown"
        if inverter_type_val is not None:
            model = self._type_map.get(str(inverter_type_val), str(inverter_type_val))

        return {
            "identifiers": {(DOMAIN, self._serial)},
            "name": f"Solax Inverter {self._serial}",
            "manufacturer": "Solax",
            "model": model,
            "serial_number": inverter_sn or self._serial,
        }

    @property
    def extra_state_attributes(self):
        attrs = {}
        inv = self.coordinator.data.get(self._serial)
        if not inv or not isinstance(inv, dict):
            return attrs

        if self._field in MAPPED_FIELDS and self._field in inv and inv[self._field] is not None:
            raw_val = inv[self._field]
            attrs[f"{self._field}_raw"] = raw_val
            field_key = _translation_sensor_key(self._field)
            state_key = f"component.{DOMAIN}.entity.sensor.{field_key}.state.{raw_val}"
            mapped_value = self._translations.get(state_key, f"Unknown ({raw_val})")
            attrs[f"{self._field}_text"] = mapped_value

        attrs["last_update_raw"] = inv.get("uploadTime")
        attrs["utc_date_time"] = inv.get("utcDateTime")
        return attrs


class SolaxInverterApiAccessStatusSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = False

    def __init__(self, coordinator, serial, human_name, system_slug, translations, type_map):
        super().__init__(coordinator)
        self._serial = serial
        self._translations = translations
        self._type_map = type_map
        self._attr_name = human_name
        self._attr_unique_id = f"{system_slug}_api_access_status_{serial}".lower()
        self.entity_id = f"sensor.{system_slug}_api_access_status_{serial}".lower()
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    def _status_key(self):
        if self._serial in getattr(self.coordinator, "unauthorized_inverters", []):
            return "serial_unauthorized"
        if self._serial in getattr(self.coordinator, "rate_limited_inverters", []):
            return "rate_limited"

        inv = self.coordinator.data.get(self._serial)
        if not isinstance(inv, dict):
            return "unknown"

        error = inv.get("error")
        code = inv.get("code")
        exception = str(inv.get("exception", "")).lower()

        if error == "data_unauthorized" or code == 1003 or "no auth" in exception:
            return "serial_unauthorized"
        if error in ("rate_limit", "rate_limit_skip"):
            return "rate_limited"
        if error:
            return "api_error"
        return "ok"

    @property
    def native_value(self):
        status_key = self._status_key()
        return get_translation_name(
            self._translations,
            DOMAIN,
            "apiAccessStatus",
            state_value=status_key,
            default=status_key,
        )

    @property
    def available(self):
        return True

    @property
    def device_info(self):
        inv = self.coordinator.data.get(self._serial)
        inverter_sn = inv.get("inverterSN") if isinstance(inv, dict) else None
        inverter_type_val = inv.get("inverterType") if isinstance(inv, dict) else None

        model = "Unknown"
        if inverter_type_val is not None:
            model = self._type_map.get(str(inverter_type_val), str(inverter_type_val))

        return {
            "identifiers": {(DOMAIN, self._serial)},
            "name": f"Solax Inverter {self._serial}",
            "manufacturer": "Solax",
            "model": model,
            "serial_number": inverter_sn or self._serial,
        }

    @property
    def extra_state_attributes(self):
        attrs = {
            "status_raw": self._status_key(),
        }
        inv = self.coordinator.data.get(self._serial)
        if isinstance(inv, dict):
            if inv.get("code") is not None:
                attrs["code"] = inv.get("code")
            if inv.get("exception"):
                attrs["exception"] = inv.get("exception")
            if inv.get("uploadTime"):
                attrs["last_update_raw"] = inv.get("uploadTime")
            if inv.get("utcDateTime"):
                attrs["utc_date_time"] = inv.get("utcDateTime")
        return attrs


class SolaxInverterEfficiencySensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = False
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "%"
    _attr_suggested_display_precision = 1

    def __init__(self, coordinator, serial, human_name, system_slug, type_map):
        super().__init__(coordinator)
        self._serial = serial
        self._type_map = type_map
        self._attr_name = human_name
        self._attr_unique_id = f"{system_slug}_inverter_efficiency_{serial}"
        self.entity_id = f"sensor.{system_slug}_inverter_efficiency_{serial}".lower()

    @property
    def native_value(self):
        inv = self.coordinator.data.get(self._serial)
        if not inv or not isinstance(inv, dict):
            return 0
        if inv.get("error"):
            return 0
        dc_total = sum(inv.get(f"powerdc{i}", 0) for i in range(1, 5))
        ac = inv.get("acpower") or 0
        if dc_total > 0:
            return round((ac / dc_total) * 100, 1)
        return 0

    @property
    def available(self):
        return True

    @property
    def device_info(self):
        inv = self.coordinator.data.get(self._serial)
        inverter_sn = inv.get("inverterSN") if isinstance(inv, dict) else None
        inverter_type = str(inv.get("inverterType")) if isinstance(inv, dict) else None
        model = self._type_map.get(inverter_type, inverter_type or "Unknown")

        return {
            "identifiers": {(DOMAIN, self._serial)},
            "name": f"Solax Inverter {self._serial}",
            "manufacturer": "Solax",
            "model": model,
            "serial_number": inverter_sn or self._serial,
        }


class SolaxComputedSensor(CoordinatorEntity, SensorEntity):
    """Used for the 'DC Power Inverter Total' sensor."""

    _attr_has_entity_name = False
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
        if not data or not isinstance(data, dict):
            return False
        if data.get("error"):
            return False
        return any(data.get(f"powerdc{i}") is not None for i in range(1, 5))

    @property
    def device_info(self):
        inv = self.coordinator.data.get(self._serial)
        inverter_sn = inv.get("inverterSN") if isinstance(inv, dict) else None
        inverter_type_val = inv.get("inverterType") if isinstance(inv, dict) else None

        model = "Unknown"
        if inverter_type_val is not None:
            model = self._type_map.get(str(inverter_type_val), str(inverter_type_val))

        return {
            "identifiers": {(DOMAIN, self._serial)},
            "name": f"Solax Inverter {self._serial}",
            "manufacturer": "Solax",
            "model": model,
            "serial_number": inverter_sn or self._serial,
        }

    @property
    def native_value(self):
        inv = self.coordinator.data.get(self._serial)
        if not inv or not isinstance(inv, dict):
            return None
        if inv.get("error"):
            return None
        return sum(inv.get(f"powerdc{i}") or 0 for i in range(1, 5))


class SolaxSystemTotalSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = False
    _unrecorded_attributes = frozenset({"seconds_until_next_poll"})

    def __init__(
        self,
        coordinator,
        inverters,
        metric,
        name,
        system_name,
        system_slug,
        translations,
        legacy_entity_name,
    ):
        super().__init__(coordinator)
        self._inverters = inverters
        self._metric = metric
        self._system_name = system_name
        self._system_slug = system_slug
        self._translations = translations
        self._attr_name = name
        # Keep entity_id stable with pre-existing naming scheme while allowing
        # a cleaner friendly name without the system prefix.
        self.entity_id = f"sensor.{slugify(legacy_entity_name)}"

        metric_map = {
            "ac_total": "ac_power",
            "dc_total": "dc_power",
            "yieldtoday_total": "yield_today",
            "yieldtotal_total": "yield_total",
            "systemEfficiency": "system_efficiency",
            "systemHealth": "system_health",
            "rateLimitStatus": "rate_limit_status",
            "lastPollAttempt": "last_poll_attempt",
            "nextScheduledPoll": "next_scheduled_poll",
        }
        self._attr_unique_id = f"{self._system_slug}_{metric_map[self._metric]}_solax"

        if self._metric in ("yieldtoday_total", "yieldtotal_total"):
            self._attr_device_class = SensorDeviceClass.ENERGY
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING
            self._attr_native_unit_of_measurement = "kWh"
        elif self._metric == "systemEfficiency":
            self._attr_state_class = SensorStateClass.MEASUREMENT
            self._attr_native_unit_of_measurement = "%"
        elif self._metric == "systemHealth":
            self._attr_native_unit_of_measurement = None
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
        elif self._metric == "rateLimitStatus":
            self._attr_native_unit_of_measurement = None
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
        elif self._metric in ("lastPollAttempt", "nextScheduledPoll"):
            self._attr_device_class = SensorDeviceClass.TIMESTAMP
            self._attr_native_unit_of_measurement = None
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
            self._attr_entity_registry_enabled_default = False
        else:
            self._attr_device_class = SensorDeviceClass.POWER
            self._attr_state_class = SensorStateClass.MEASUREMENT
            self._attr_native_unit_of_measurement = "W"

    @property
    def device_info(self):
        total_inverters = len(self._inverters)
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

    def _count_active_inverters(self):
        total = 0
        for sn in self._inverters:
            inv = self.coordinator.data.get(sn)
            if not inv or not isinstance(inv, dict):
                continue
            if inv.get("error"):
                continue
            if inv.get("acpower") is not None:
                total += 1
        return total

    def _health_counts(self):
        total = len(self._inverters)
        healthy = 0
        error_counts = {}

        for sn in self._inverters:
            inv = self.coordinator.data.get(sn)
            if not inv or not isinstance(inv, dict):
                error_counts["no_data"] = error_counts.get("no_data", 0) + 1
                continue
            if inv.get("error"):
                error_key = str(inv.get("error"))
                error_counts[error_key] = error_counts.get(error_key, 0) + 1
                continue
            healthy += 1

        return total, healthy, error_counts

    def _health_status_raw(self):
        total, healthy, _ = self._health_counts()
        if total == 0:
            return "unknown"
        if healthy == total:
            return "ok"
        if healthy == 0:
            return "error"
        return "degraded"

    @property
    def available(self):
        if self._metric == "systemHealth":
            return len(self._inverters) > 0
        if self._metric == "rateLimitStatus":
            return len(self._inverters) > 0
        if self._metric in ("lastPollAttempt", "nextScheduledPoll"):
            return len(self._inverters) > 0

        for sn in self._inverters:
            inv = self.coordinator.data.get(sn)
            if not inv or not isinstance(inv, dict) or inv.get("error"):
                continue
            if self._metric == "ac_total" and inv.get("acpower") is not None:
                return True
            if self._metric == "dc_total" and any(
                inv.get(f"powerdc{i}") is not None for i in range(1, 5)
            ):
                return True
            if self._metric == "yieldtoday_total" and inv.get("yieldtoday") is not None:
                return True
            if self._metric == "yieldtotal_total" and inv.get("yieldtotal") is not None:
                return True
            if self._metric == "systemEfficiency" and inv.get("acpower") is not None and any(
                inv.get(f"powerdc{i}") is not None for i in range(1, 5)
            ):
                return True
        return False

    @property
    def native_value(self):
        if self._metric == "lastPollAttempt":
            return self.coordinator.last_update_attempt

        if self._metric == "nextScheduledPoll":
            if self.coordinator.last_update_attempt is None:
                return None
            return self.coordinator.last_update_attempt + timedelta(
                seconds=self.coordinator.update_interval.total_seconds()
            )

        if self._metric == "rateLimitStatus":
            if len(self._inverters) == 0:
                status = "unknown"
            elif self.coordinator.rate_limited_inverters:
                status = "rate_limited"
            else:
                status = "ok"
            return get_translation_name(
                self._translations, DOMAIN, "rateLimitStatus", state_value=status, default=status
            )

        if self._metric == "systemHealth":
            status = self._health_status_raw()
            return get_translation_name(
                self._translations, DOMAIN, "systemHealth", state_value=status, default=status
            )

        if self._metric == "systemEfficiency":
            total_ac = 0
            total_dc = 0
            for sn in self._inverters:
                inv = self.coordinator.data.get(sn)
                if not inv or not isinstance(inv, dict) or inv.get("error"):
                    continue
                total_ac += inv.get("acpower", 0) or 0
                for i in range(1, 5):
                    total_dc += inv.get(f"powerdc{i}", 0) or 0

            if total_dc > 0:
                return round((total_ac / total_dc) * 100, 1)
            return None

        total = 0
        field_map = {
            "ac_total": "acpower",
            "yieldtoday_total": "yieldtoday",
            "yieldtotal_total": "yieldtotal",
        }
        for sn in self._inverters:
            inv = self.coordinator.data.get(sn)
            if not inv or not isinstance(inv, dict) or inv.get("error"):
                continue

            if self._metric in field_map:
                total += inv.get(field_map[self._metric], 0) or 0
            elif self._metric == "dc_total":
                total += sum(inv.get(f"powerdc{i}", 0) or 0 for i in range(1, 5))
        return total

    @property
    def extra_state_attributes(self):
        attrs = {
            "active_inverters": self._count_active_inverters(),
            "total_inverters": len(self._inverters),
        }
        if self._metric == "rateLimitStatus":
            attrs["rate_limit_status_raw"] = (
                "rate_limited" if self.coordinator.rate_limited_inverters else "ok"
            )
            attrs["rate_limited_inverters"] = list(self.coordinator.rate_limited_inverters)
            attrs["rate_limited_count"] = len(self.coordinator.rate_limited_inverters)
            attrs["rate_limited_details"] = dict(
                getattr(self.coordinator, "rate_limited_details", {})
            )
            if self.coordinator.last_rate_limit_at is not None:
                attrs["last_rate_limit_at"] = self.coordinator.last_rate_limit_at.isoformat()

        if self._metric == "nextScheduledPoll":
            next_poll = self.native_value
            if next_poll is not None:
                seconds_left = int((next_poll - dt_util.utcnow()).total_seconds())
                attrs["seconds_until_next_poll"] = max(0, seconds_left)

        if self._metric == "systemHealth":
            total, healthy, error_counts = self._health_counts()
            failed = max(total - healthy, 0)
            attrs["health_raw"] = self._health_status_raw()
            attrs["healthy_inverters"] = healthy
            attrs["failed_inverters"] = failed
            attrs["error_breakdown"] = error_counts

            if self.coordinator.last_successful_update is not None:
                now = dt_util.utcnow()
                delta = now - self.coordinator.last_successful_update
                attrs["last_successful_refresh"] = self.coordinator.last_successful_update.isoformat()
                attrs["seconds_since_last_successful_refresh"] = int(delta.total_seconds())
        return attrs
