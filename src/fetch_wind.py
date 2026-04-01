"""
Fetch historical wind data from Iowa Environmental Mesonet (IEM).
No API key required. Data comes from BWI airport ASOS station.
"""

import os
import pandas as pd
import requests
from datetime import datetime

from src.config import WIND_STATION, DATA_DIR, DEFAULT_START_YEAR, DEFAULT_END_YEAR

IEM_URL = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"


def fetch_wind_data(station=WIND_STATION, start_year=DEFAULT_START_YEAR, end_year=DEFAULT_END_YEAR):
    """
    Fetch hourly wind direction and speed from IEM for the given station and year range.
    Returns a DataFrame with columns: timestamp, wind_dir, wind_speed_kt, wind_gust_kt
    """
    all_data = []

    for year in range(start_year, end_year + 1):
        print(f"  Fetching wind data for {year}...")
        params = {
            "station": station,
            "data": "drct,sknt,gust_sknt",
            "year1": year, "month1": 1, "day1": 1,
            "year2": year, "month2": 12, "day2": 31,
            "tz": "UTC",
            "format": "onlycomma",
            "latlon": "no",
            "elev": "no",
            "missing": "empty",
            "trace": "empty",
            "direct": "no",
            "report_type": "3",  # METAR/routine
        }

        resp = requests.get(IEM_URL, params=params, timeout=120)
        resp.raise_for_status()

        # IEM returns CSV with a header line
        lines = resp.text.strip().split("\n")
        if len(lines) < 2:
            print(f"    No data for {year}")
            continue

        from io import StringIO
        df = pd.read_csv(StringIO(resp.text))
        all_data.append(df)
        print(f"    Got {len(df)} records for {year}")

    if not all_data:
        raise RuntimeError("No wind data retrieved")

    combined = pd.concat(all_data, ignore_index=True)

    # Normalize column names
    combined.columns = [c.strip().lower() for c in combined.columns]

    # Rename to consistent names
    rename_map = {}
    for col in combined.columns:
        if "valid" in col:
            rename_map[col] = "timestamp"
        elif col == "drct":
            rename_map[col] = "wind_dir"
        elif col == "sknt":
            rename_map[col] = "wind_speed_kt"
        elif "gust" in col:
            rename_map[col] = "wind_gust_kt"
    combined.rename(columns=rename_map, inplace=True)

    # Parse and clean
    combined["timestamp"] = pd.to_datetime(combined["timestamp"], errors="coerce")
    combined["wind_dir"] = pd.to_numeric(combined["wind_dir"], errors="coerce")
    combined["wind_speed_kt"] = pd.to_numeric(combined["wind_speed_kt"], errors="coerce")
    if "wind_gust_kt" in combined.columns:
        combined["wind_gust_kt"] = pd.to_numeric(combined["wind_gust_kt"], errors="coerce")

    # Drop rows with no wind direction (calm or missing)
    combined = combined.dropna(subset=["timestamp", "wind_dir"])
    combined = combined[combined["wind_dir"] > 0]  # 0 = variable/calm

    # Convert knots to m/s for modeling
    combined["wind_speed_ms"] = combined["wind_speed_kt"] * 0.514444

    combined = combined.sort_values("timestamp").reset_index(drop=True)
    return combined


def save_wind_data(df, filename="wind_bwi.csv"):
    os.makedirs(DATA_DIR, exist_ok=True)
    path = os.path.join(DATA_DIR, filename)
    df.to_csv(path, index=False)
    print(f"Saved {len(df)} wind records to {path}")
    return path


def load_wind_data(filename="wind_bwi.csv"):
    path = os.path.join(DATA_DIR, filename)
    df = pd.read_csv(path, parse_dates=["timestamp"])
    return df


if __name__ == "__main__":
    print("Fetching BWI wind data...")
    df = fetch_wind_data()
    save_wind_data(df)
    print(f"\nSummary:")
    print(f"  Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
    print(f"  Total records: {len(df)}")
    print(f"  Mean wind speed: {df['wind_speed_kt'].mean():.1f} kt ({df['wind_speed_ms'].mean():.1f} m/s)")
    print(f"\n  Wind direction distribution:")
    bins = [0, 45, 90, 135, 180, 225, 270, 315, 360]
    labels = ["N/NE", "E/NE", "E/SE", "S/SE", "S/SW", "W/SW", "W/NW", "N/NW"]
    df["sector"] = pd.cut(df["wind_dir"], bins=bins, labels=labels, include_lowest=True)
    print(df["sector"].value_counts().sort_index().to_string())
