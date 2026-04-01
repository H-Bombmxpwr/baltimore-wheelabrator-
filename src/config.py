"""
Core configuration for Baltimore air quality analysis.

Key locations, monitor sites, and geographic references for analyzing
Wheelabrator Baltimore / WIN Waste emissions vs I-95 corridor pollution.
"""

# --- Facility ---
WHEELABRATOR = {
    "name": "Wheelabrator Baltimore (WIN Waste)",
    "lat": 39.27003765823886,
    "lon": -76.62914374046485,
    "address": "1801 Annapolis Rd, Baltimore, MD 21230",
    "stack_height_m": 76,  # approximate main stack height
}

# --- I-95 corridor through Baltimore (sampled waypoints) ---
I95_WAYPOINTS = [
    (39.2000, -76.5490),  # south of city
    (39.2200, -76.5560),
    (39.2400, -76.5700),
    (39.2600, -76.5850),  # near Wheelabrator
    (39.2800, -76.6000),
    (39.3000, -76.6100),
    (39.3200, -76.6130),
    (39.3400, -76.6120),  # north of downtown
]

# --- Baltimore AQS monitors (Maryland FIPS: 24, Baltimore City: 510, Baltimore County: 005) ---
# These are known monitors; we'll also discover more via the AQS API
AQS_STATE = "24"         # Maryland
AQS_COUNTY_CITY = "510"  # Baltimore City
AQS_COUNTY_CO = "005"    # Baltimore County

# Key pollutant parameter codes
POLLUTANTS = {
    "PM2.5":  "88101",
    "PM10":   "81102",
    "SO2":    "42401",
    "NO2":    "42602",
    "Ozone":  "44201",
    "CO":     "42101",
}

# --- Weather station ---
WIND_STATION = "BWI"  # Baltimore-Washington International (Iowa Mesonet ID)
WIND_STATION_LAT = 39.1754
WIND_STATION_LON = -76.6684

# --- Analysis parameters ---
# Radius (km) around Wheelabrator to consider "nearby"
ANALYSIS_RADIUS_KM = 10

# Bearing sectors (degrees, clockwise from north)
# When wind blows FROM this direction, Wheelabrator emissions go TOWARD neighborhoods in the opposite direction
SECTORS = {
    "N":  (337.5, 22.5),
    "NE": (22.5, 67.5),
    "E":  (67.5, 112.5),
    "SE": (112.5, 157.5),
    "S":  (157.5, 202.5),
    "SW": (202.5, 247.5),
    "W":  (247.5, 292.5),
    "NW": (292.5, 337.5),
}

# --- Neighborhoods of interest ---
# Neighborhoods near the facility and their approximate centroids
NEIGHBORHOODS = {
    # --- Near both Wheelabrator AND I-95 ---
    "Westport":           {"lat": 39.2631, "lon": -76.6324, "near_i95": True,  "near_wheelabrator": True},
    "Cherry Hill":        {"lat": 39.2507, "lon": -76.6269, "near_i95": True,  "near_wheelabrator": True},
    "Brooklyn":           {"lat": 39.2361, "lon": -76.6039, "near_i95": True,  "near_wheelabrator": True},
    "Curtis Bay":         {"lat": 39.2241, "lon": -76.5883, "near_i95": True,  "near_wheelabrator": True},
    "South Baltimore":    {"lat": 39.2690, "lon": -76.5950, "near_i95": True,  "near_wheelabrator": True},
    "Federal Hill":       {"lat": 39.2780, "lon": -76.6130, "near_i95": True,  "near_wheelabrator": True},

    # --- I-95 corridor only (south of Baltimore) ---
    "Elkridge":           {"lat": 39.2127, "lon": -76.7136, "near_i95": True,  "near_wheelabrator": False},
    "Savage":             {"lat": 39.1380, "lon": -76.8230, "near_i95": True,  "near_wheelabrator": False},
    "Laurel":             {"lat": 39.0993, "lon": -76.8483, "near_i95": True,  "near_wheelabrator": False},

    # --- I-95 corridor only (north of Baltimore) ---
    "Rossville":          {"lat": 39.3380, "lon": -76.4790, "near_i95": True,  "near_wheelabrator": False},
    "White Marsh":        {"lat": 39.3830, "lon": -76.4310, "near_i95": True,  "near_wheelabrator": False},
    "Aberdeen":           {"lat": 39.5096, "lon": -76.1641, "near_i95": True,  "near_wheelabrator": False},

    # --- Control (neither) ---
    "Canton":             {"lat": 39.2830, "lon": -76.5730, "near_i95": False, "near_wheelabrator": False},
    "Fells Point":        {"lat": 39.2820, "lon": -76.5920, "near_i95": False, "near_wheelabrator": False},
    "Dundalk":            {"lat": 39.2500, "lon": -76.5200, "near_i95": False, "near_wheelabrator": False},
    "Hampden":            {"lat": 39.3310, "lon": -76.6360, "near_i95": False, "near_wheelabrator": False},
}

# Date range for analysis
DEFAULT_START_YEAR = 2019
DEFAULT_END_YEAR = 2024

# --- Data paths ---
DATA_DIR = "data"
OUTPUT_DIR = "output"
