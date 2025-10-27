DOMAIN = "solax_multi"
PLATFORMS = ["sensor"]
CONF_TOKEN = "api_token"
CONF_INVERTERS = "inverters"
CONF_SCAN_INTERVAL = "scan_interval"
DEFAULT_SCAN_INTERVAL = 60
API_URL = "https://global.solaxcloud.com/api/v2/dataAccess/realtimeInfo/get"

# All fields returned by result (we'll expose most as sensors or attributes)
RESULT_FIELDS = [
    "inverterSN", "sn", "acpower",
    "yieldtoday", "yieldtotal",
    "feedinpower", "feedinenergy", "consumeenergy", "feedinpowerM2",
    "soc", "peps1", "peps2", "peps3",
    "inverterType", "inverterStatus", "uploadTime",
    "batPower", "powerdc1", "powerdc2", "powerdc3", "powerdc4",
    "batStatus"
]

# Human readable inverter status mapping (Appendix 8.1)
INVERTER_STATUSES = {
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
}

# Known error codes (Appendix 8.2)
ERROR_CODES = {
    0: "Success",
    1001: "Interface Unauthorized",
    1002: "Parameter validation failed",
    1003: "Data Unauthorized",
    1004: "Duplicate data",
    2001: "Operation failed",
    2002: "Data not found",
}

# Update INVERTER_TYPES in const.py
INVERTER_TYPES = {
    "1": "Solax X1 Mini",
    "2": "Solax X1 Boost", 
    "3": "Solax X1 Pro",
    "4": "Solax X3", 
    "28": "Solax X1 Micro 2 in 1",
    # Add more as discovered
}

# Battery information
BATTERY_STATUSES = {
    "0": "Normal",
    "1": "Fault", 
    "2": "Disconnected"
}
