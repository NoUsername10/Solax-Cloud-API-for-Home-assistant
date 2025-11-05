DOMAIN = "solax_cloud_api"
PLATFORMS = ["sensor"]
CONF_TOKEN = "api_token"
CONF_INVERTERS = "inverters"
CONF_SCAN_INTERVAL = "scan_interval"
DEFAULT_SCAN_INTERVAL = 120
API_URL = "https://global.solaxcloud.com/api/v2/dataAccess/realtimeInfo/get"

import logging
LOGGER = logging.getLogger(__package__)

# Import string definitions
from .strings import HIDDEN_SENSORS

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
