# String definitions for Solax Multi Inverter integration.

# Human-readable sensor names
SENSOR_NAMES = {
    # Power sensors
    "acpower": "AC Output Power",
    "powerdc1": "DC Power String 1", 
    "powerdc2": "DC Power String 2",
    "powerdc3": "DC Power String 3",
    "powerdc4": "DC Power String 4",
    "feedinpower": "Grid Feed-in Power",
    "feedinpowerM2": "Grid Feed-in Power Meter 2",
    "batPower": "Battery Power",
    
    # Energy sensors
    "yieldtoday": "Yield Today",
    "yieldtotal": "Yield Total", 
    "feedinenergy": "Grid Feed-in Energy",
    "consumeenergy": "Grid Consumption Energy",
    
    # Status sensors
    "inverterStatus": "Inverter Status",
    "batStatus": "Battery Status",
    "inverterType": "Inverter Type",
    
    # Battery sensors
    "soc": "Battery State of Charge",
    
    # EPS sensors
    "peps1": "EPS Phase 1 Power",
    "peps2": "EPS Phase 2 Power", 
    "peps3": "EPS Phase 3 Power",
    
    # Identification sensors
    "inverterSN": "Inverter Serial",
    "sn": "Inverter Wi-Fi Serial",
    
    # Timestamp sensors
    "uploadTime": "Inverter Upload Time",
    "utcDateTime": "UTC Date Time",
}

# System total sensor names
SYSTEM_SENSOR_NAMES = {
    "ac_total": "AC Power Total",
    "dc_total": "DC Power Total", 
    "dc_total_inverter": "DC Power Inverter Total", 
    "yieldtoday_total": "Yield Total System Today",
    "yieldtotal_total": "Yield Total System",
}

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
