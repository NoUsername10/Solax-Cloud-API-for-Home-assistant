import logging

DOMAIN = "solax_cloud_api"
CONFIG_ENTRY_VERSION = 2
PLATFORMS = ["sensor", "switch"]
CONF_TOKEN = "api_token"
CONF_API_REGION = "api_region"
CONF_INVERTERS = "inverters"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_SYSTEM_NAME = "system_name"
CONF_ENTITY_PREFIX = "entity_prefix"
CONF_RATE_LIMIT_NOTIFICATIONS = "rate_limit_notifications"
DEFAULT_ENTITY_PREFIX = "solax_cloud_api"
INVALID_ENTITY_PREFIXES = frozenset({"unknown", "unnamed"})
DEFAULT_SCAN_INTERVAL = 120
API_REGION_GLOBAL = "global"
API_REGION_INDIA = "india"
API_REGION_NA = "na"
DEFAULT_API_REGION = API_REGION_GLOBAL
API_REGIONS = {
    API_REGION_GLOBAL: "Global",
    API_REGION_INDIA: "India",
    API_REGION_NA: "North America",
}
API_URLS = {
    API_REGION_GLOBAL: "https://global.solaxcloud.com/api/v2/dataAccess/realtimeInfo/get",
    API_REGION_INDIA: "https://in.solaxcloud.com/api/v2/dataAccess/realtimeInfo/get",
    API_REGION_NA: "https://na.solaxcloud.com/api/v2/dataAccess/realtimeInfo/get",
}
SERVICE_MANUAL_REFRESH = "manual_refresh"
RUNTIME_RELOAD_STATE = f"{DOMAIN}_reload_state"
RUNTIME_INITIAL_SETUP_STATE = "__initial_setup__"

LOGGER = logging.getLogger(__package__)


def api_url_for_region(region: str | None) -> str:
    """Return the allowlisted API URL for a configured SolaX region."""
    return API_URLS.get(str(region or "").lower(), API_URLS[DEFAULT_API_REGION])

# All fields returned by result
RESULT_FIELDS = [
    "inverterSN", "sn", "acpower",
    "yieldtoday", "yieldtotal",
    "feedinpower", "feedinenergy", "consumeenergy", "feedinpowerM2",
    "soc", "peps1", "peps2", "peps3",
    "inverterType", "inverterStatus", "uploadTime", "utcDateTime",
    "batPower", "powerdc1", "powerdc2", "powerdc3", "powerdc4",
    "batStatus"
]

# Numeric fields with units
NUMERIC_FIELDS = {
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
    "soc": ("%", "battery"),
    "peps1": ("W", "power"),
    "peps2": ("W", "power"),
    "peps3": ("W", "power"),
    "feedinpowerM2": ("W", "power"),
}

HIDDEN_SENSORS = {
 #   "inverterSN": True,      # Serial numbers - usually not needed in UI
 #   "uploadTime": True,      # Raw timestamp
    "utcDateTime": True,     # UTC timestamp
}

# Fields whose states are mapped via translation files
MAPPED_FIELDS = ["inverterStatus", "batStatus", "inverterType"]
