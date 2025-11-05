# String definitions

# Device class descriptions (optional)
DEVICE_CLASS_DESCRIPTIONS = {
    "power": "power sensor",
    "energy": "energy sensor", 
    "battery": "battery sensor",
    "status": "status sensor",
}

# Sensors that should be hidden by default (diagnostic/configuration sensors)
HIDDEN_SENSORS = {
 #   "inverterSN": True,      # Serial numbers - usually not needed in UI
 #   "sn": True,              # Wi-Fi module serial
 #   "inverterType": True,    # Static inverter type
 #   "uploadTime": True,      # Raw timestamp
    "utcDateTime": True,     # UTC timestamp
}
