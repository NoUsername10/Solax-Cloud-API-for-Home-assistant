DOMAIN = "solax_multi"
PLATFORMS = ["sensor"]
CONF_TOKEN = "api_token"
CONF_INVERTERS = "inverters"
CONF_SCAN_INTERVAL = "scan_interval"
DEFAULT_SCAN_INTERVAL = 120
API_URL = "https://global.solaxcloud.com/api/v2/dataAccess/realtimeInfo/get"

import logging
LOGGER = logging.getLogger(__package__)

# Import string definitions
from .strings import SENSOR_NAMES, SYSTEM_SENSOR_NAMES, HIDDEN_SENSORS

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

# Field mappings for human-readable values
FIELD_MAPPINGS = {
    # Inverter status mapping (Appendix 8.1)
    "inverterStatus": {
        "100": "Waiting for operation",
        "101": "Self-test",
        "102": "Normal",
        "103": "Recoverable fault",
        "104": "Permanent fault",
        "105": "Firmware upgrade",
        "106": "EPS detection",
        "107": "Off-grid",
        "108": "Self-test mode (Italian safety regulations)",
        "109": "Sleep mode",
        "110": "Standby mode",
        "111": "Photovoltaic wake-up battery mode",
        "112": "Generator detection mode",
        "113": "Generator mode",
        "114": "Fast shutdown standby mode",
        "130": "VPP mode",
        "131": "TOU - Self use",
        "132": "TOU - Charging",
        "133": "TOU - Discharging",
    },
    
    # Battery status mapping
    "batStatus": {
        "0": "Normal",
        "1": "Fault",
        "2": "Disconnected",
    },
    
    # Inverter type mapping
    "inverterType": {
        "1": "Solax X1 Mini",
        "2": "Solax X1 Boost", 
        "3": "Solax X1 Pro",
        "4": "Solax X3",
        "28": "Solax X1 Micro 2 in 1",
        # Add more as discovered
    },
    
    # Error codes mapping (Appendix 8.2)
    "code": {
        "0": "Success",
        "1001": "Interface Unauthorized",
        "1002": "Parameter validation failed",
        "1003": "Data Unauthorized", 
        "1004": "Duplicate data",
        "2001": "Operation failed",
        "2002": "Data not found",
    }
}

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

# Fields that should be displayed as human-readable
MAPPED_FIELDS = ["inverterStatus", "batStatus", "inverterType"]

# Backward compatibility (for existing code)
INVERTER_STATUSES = FIELD_MAPPINGS["inverterStatus"]
BATTERY_STATUSES = FIELD_MAPPINGS["batStatus"]
INVERTER_TYPES = FIELD_MAPPINGS["inverterType"]
ERROR_CODES = FIELD_MAPPINGS["code"]
