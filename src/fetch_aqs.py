"""
Fetch air quality monitoring data from EPA AQS API.
Requires a free API key — register at https://aqs.epa.gov/data/api/signup?email=YOUR_EMAIL

Also discovers nearby monitors and classifies them relative to Wheelabrator and I-95.
"""

import os
import math
import pandas as pd
import requests
from dotenv import load_dotenv

from src.config import (
    AQS_STATE, AQS_COUNTY_CITY, AQS_COUNTY_CO,
    POLLUTANTS, DATA_DIR, WHEELABRATOR,
    DEFAULT_START_YEAR, DEFAULT_END_YEAR,
)

load_dotenv()

AQS_BASE = "https://aqs.epa.gov/data/api"


def _aqs_params():
    email = os.getenv("AQS_EMAIL")
    key = os.getenv("AQS_KEY")
    if not email or not key:
        raise RuntimeError(
            "AQS_EMAIL and AQS_KEY must be set in .env\n"
            "Register free at: https://aqs.epa.gov/data/api/signup?email=YOUR_EMAIL"
        )
    return {"email": email, "key": key}


def _aqs_get(endpoint, params):
    url = f"{AQS_BASE}/{endpoint}"
    auth = _aqs_params()
    params.update(auth)
    resp = requests.get(url, params=params, timeout=60)
    resp.raise_for_status()
    result = resp.json()
    if result.get("Header", [{}])[0].get("status") == "Failed":
        raise RuntimeError(f"AQS API error: {result['Header']}")
    return result.get("Data", [])


def haversine_km(lat1, lon1, lat2, lon2):
    """Distance in km between two lat/lon points."""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))


def bearing_from(lat1, lon1, lat2, lon2):
    """Bearing in degrees from point 1 to point 2."""
    dlon = math.radians(lon2 - lon1)
    lat1r, lat2r = math.radians(lat1), math.radians(lat2)
    x = math.sin(dlon) * math.cos(lat2r)
    y = math.cos(lat1r) * math.sin(lat2r) - math.sin(lat1r) * math.cos(lat2r) * math.cos(dlon)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def discover_monitors(county=AQS_COUNTY_CITY):
    """Find all AQS monitors in Baltimore City."""
    monitors = []
    for pollutant_name, param_code in POLLUTANTS.items():
        print(f"  Discovering {pollutant_name} monitors...")
        data = _aqs_get("monitors/byCounty", {
            "param": param_code,
            "bdate": "20190101",
            "edate": "20241231",
            "state": AQS_STATE,
            "county": county,
        })
        for m in data:
            m["pollutant"] = pollutant_name
        monitors.extend(data)

    if not monitors:
        return pd.DataFrame()

    df = pd.DataFrame(monitors)

    # Add distance and bearing from Wheelabrator
    if "latitude" in df.columns and "longitude" in df.columns:
        df["dist_from_wheelabrator_km"] = df.apply(
            lambda r: haversine_km(WHEELABRATOR["lat"], WHEELABRATOR["lon"], r["latitude"], r["longitude"]), axis=1
        )
        df["bearing_from_wheelabrator"] = df.apply(
            lambda r: bearing_from(WHEELABRATOR["lat"], WHEELABRATOR["lon"], r["latitude"], r["longitude"]), axis=1
        )

    return df


def fetch_daily_data(param_code, county=AQS_COUNTY_CITY,
                     start_year=DEFAULT_START_YEAR, end_year=DEFAULT_END_YEAR):
    """Fetch daily air quality data for a pollutant in a county, one year at a time."""
    all_data = []

    for year in range(start_year, end_year + 1):
        print(f"    {year}...", end=" ")
        data = _aqs_get("dailyData/byCounty", {
            "param": param_code,
            "bdate": f"{year}0101",
            "edate": f"{year}1231",
            "state": AQS_STATE,
            "county": county,
        })
        if data:
            all_data.extend(data)
            print(f"{len(data)} records")
        else:
            print("no data")

    if not all_data:
        return pd.DataFrame()

    df = pd.DataFrame(all_data)
    if "date_local" in df.columns:
        df["date_local"] = pd.to_datetime(df["date_local"])
    return df


def fetch_all_pollutants(county=AQS_COUNTY_CITY):
    """Fetch daily data for all configured pollutants."""
    results = {}
    for name, code in POLLUTANTS.items():
        print(f"\n  Fetching {name} (param {code})...")
        df = fetch_daily_data(code, county)
        if not df.empty:
            df["pollutant"] = name
            results[name] = df
            print(f"  Total {name} records: {len(df)}")
    return results


def save_aqs_data(monitors_df, pollutant_dfs):
    os.makedirs(DATA_DIR, exist_ok=True)

    if not monitors_df.empty:
        path = os.path.join(DATA_DIR, "aqs_monitors.csv")
        monitors_df.to_csv(path, index=False)
        print(f"Saved monitors to {path}")

    for name, df in pollutant_dfs.items():
        path = os.path.join(DATA_DIR, f"aqs_{name.lower().replace('.', '')}.csv")
        df.to_csv(path, index=False)
        print(f"Saved {name} data ({len(df)} rows) to {path}")


def load_aqs_data(pollutant="PM2.5"):
    fname = f"aqs_{pollutant.lower().replace('.', '')}.csv"
    path = os.path.join(DATA_DIR, fname)
    return pd.read_csv(path, parse_dates=["date_local"])


if __name__ == "__main__":
    print("=== EPA AQS Data Acquisition ===\n")

    print("1. Discovering monitors in Baltimore City...")
    monitors = discover_monitors(AQS_COUNTY_CITY)

    print("\n   Also checking Baltimore County...")
    monitors_co = discover_monitors(AQS_COUNTY_CO)
    monitors = pd.concat([monitors, monitors_co], ignore_index=True)

    print(f"\n   Found {len(monitors)} monitor records total")

    print("\n2. Fetching daily data for Baltimore City...")
    city_data = fetch_all_pollutants(AQS_COUNTY_CITY)

    print("\n3. Fetching daily data for Baltimore County...")
    county_data = fetch_all_pollutants(AQS_COUNTY_CO)

    # Merge city and county data
    merged = {}
    all_keys = set(list(city_data.keys()) + list(county_data.keys()))
    for key in all_keys:
        frames = []
        if key in city_data:
            frames.append(city_data[key])
        if key in county_data:
            frames.append(county_data[key])
        merged[key] = pd.concat(frames, ignore_index=True)

    print("\n4. Saving data...")
    save_aqs_data(monitors, merged)
