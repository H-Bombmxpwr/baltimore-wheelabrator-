"""
Core analysis: combine wind data with air quality measurements to assess
Wheelabrator vs I-95 impact on surrounding neighborhoods.

Key analyses:
1. Wind rose — what directions does wind come from in Baltimore?
2. Directional AQ — when wind blows FROM Wheelabrator toward a monitor, is AQ worse?
3. I-95 control — compare monitors near I-95 but NOT downwind of Wheelabrator
4. Temporal trends — have emissions/AQ changed over time?
"""

import math
import numpy as np
import pandas as pd

from src.config import WHEELABRATOR, I95_WAYPOINTS, NEIGHBORHOODS


def bearing_from(lat1, lon1, lat2, lon2):
    """Bearing in degrees from point 1 to point 2."""
    dlon = math.radians(lon2 - lon1)
    lat1r, lat2r = math.radians(lat1), math.radians(lat2)
    x = math.sin(dlon) * math.cos(lat2r)
    y = math.cos(lat1r) * math.sin(lat2r) - math.sin(lat1r) * math.cos(lat2r) * math.cos(dlon)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def angle_diff(a, b):
    """Smallest angular difference between two bearings."""
    d = abs(a - b) % 360
    return min(d, 360 - d)


def classify_wind_for_monitor(wind_df, monitor_lat, monitor_lon, tolerance_deg=45):
    """
    For each wind observation, classify whether the wind is blowing
    FROM Wheelabrator TOWARD the monitor.

    Wind direction in meteorology = direction wind comes FROM.
    If Wheelabrator is at bearing B from the monitor, then wind FROM direction B
    means the wind is blowing from Wheelabrator toward the monitor.

    Returns wind_df with added column 'downwind_of_wheelabrator' (bool).
    """
    # Bearing from monitor TO Wheelabrator
    bearing_to_wb = bearing_from(monitor_lat, monitor_lon, WHEELABRATOR["lat"], WHEELABRATOR["lon"])

    # Wind blows from Wheelabrator toward monitor when wind_dir ≈ bearing_to_wb
    df = wind_df.copy()
    df["downwind_of_wheelabrator"] = df["wind_dir"].apply(
        lambda wd: angle_diff(wd, bearing_to_wb) <= tolerance_deg
    )
    df["bearing_to_wheelabrator"] = bearing_to_wb
    return df


def nearest_point_on_segment(lat, lon, a, b):
    """Closest point on segment a-b (each as (lat, lon)) to (lat, lon), planar approximation."""
    ay, ax = a[0], a[1]
    by, bx = b[0], b[1]
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return a
    t = ((lon - ax) * dx + (lat - ay) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    return (ay + t * dy, ax + t * dx)


def nearest_point_on_polyline(lat, lon, waypoints):
    """Closest point on a polyline to (lat, lon). Returns (lat, lon)."""
    best = waypoints[0]
    best_d = float("inf")
    for i in range(len(waypoints) - 1):
        pt = nearest_point_on_segment(lat, lon, waypoints[i], waypoints[i + 1])
        d = (lat - pt[0]) ** 2 + (lon - pt[1]) ** 2
        if d < best_d:
            best_d = d
            best = pt
    return best


def classify_wind_for_i95(wind_df, monitor_lat, monitor_lon, tolerance_deg=45):
    """
    Classify each wind observation as 'downwind of I-95' by treating the
    highway as a line source: bearing is computed from the monitor to the
    closest point on the I-95 polyline, not the nearest vertex. That avoids
    biasing the bearing toward whichever waypoint happened to be sampled.
    """
    nearest = nearest_point_on_polyline(monitor_lat, monitor_lon, I95_WAYPOINTS)
    bearing_to_i95 = bearing_from(monitor_lat, monitor_lon, nearest[0], nearest[1])

    df = wind_df.copy()
    df["downwind_of_i95"] = df["wind_dir"].apply(
        lambda wd: angle_diff(wd, bearing_to_i95) <= tolerance_deg
    )
    df["bearing_to_i95"] = bearing_to_i95
    return df


def merge_aqi_wind(aqi_df, wind_df):
    """
    Merge daily AQI data with wind data.
    Aggregates hourly wind to daily: dominant wind direction, mean speed,
    and % of hours downwind of Wheelabrator/I-95.
    """
    # Daily wind aggregation
    wind_daily = wind_df.copy()
    wind_daily["date"] = wind_daily["timestamp"].dt.date

    agg = wind_daily.groupby("date").agg(
        mean_wind_speed_ms=("wind_speed_ms", "mean"),
        mean_wind_dir=("wind_dir", lambda x: circular_mean(x)),
        pct_downwind_wheelabrator=("downwind_of_wheelabrator", "mean"),
        pct_downwind_i95=("downwind_of_i95", "mean"),
        n_wind_obs=("wind_dir", "count"),
    ).reset_index()

    agg["date"] = pd.to_datetime(agg["date"])

    # Merge with AQI
    merged = aqi_df.merge(agg, left_on="date_local", right_on="date", how="inner")
    return merged


def circular_mean(angles):
    """Compute circular mean of angles in degrees."""
    rads = np.radians(angles.values.astype(float))
    sin_mean = np.nanmean(np.sin(rads))
    cos_mean = np.nanmean(np.cos(rads))
    return np.degrees(np.arctan2(sin_mean, cos_mean)) % 360


def directional_analysis(merged_df, value_col="arithmetic_mean"):
    """
    Compare pollutant values on days when the monitor is downwind of Wheelabrator
    vs days when it's not, controlling for I-95 proximity.

    Returns a summary dict.
    """
    df = merged_df.dropna(subset=[value_col])

    # Threshold: >50% of hours downwind = "downwind day"
    downwind_wb = df[df["pct_downwind_wheelabrator"] > 0.5]
    not_downwind_wb = df[df["pct_downwind_wheelabrator"] <= 0.5]

    downwind_i95 = df[df["pct_downwind_i95"] > 0.5]
    not_downwind_i95 = df[df["pct_downwind_i95"] <= 0.5]

    # Four-way split: downwind of both, only WB, only I-95, neither
    both = df[(df["pct_downwind_wheelabrator"] > 0.5) & (df["pct_downwind_i95"] > 0.5)]
    only_wb = df[(df["pct_downwind_wheelabrator"] > 0.5) & (df["pct_downwind_i95"] <= 0.5)]
    only_i95 = df[(df["pct_downwind_wheelabrator"] <= 0.5) & (df["pct_downwind_i95"] > 0.5)]
    neither = df[(df["pct_downwind_wheelabrator"] <= 0.5) & (df["pct_downwind_i95"] <= 0.5)]

    def stats(subset, label):
        if len(subset) == 0:
            return {"label": label, "n_days": 0, "mean": None, "median": None, "p90": None}
        vals = subset[value_col]
        return {
            "label": label,
            "n_days": len(subset),
            "mean": round(vals.mean(), 2),
            "median": round(vals.median(), 2),
            "p90": round(vals.quantile(0.90), 2),
        }

    return {
        "downwind_wheelabrator": stats(downwind_wb, "Downwind of Wheelabrator"),
        "not_downwind_wheelabrator": stats(not_downwind_wb, "Not downwind of Wheelabrator"),
        "downwind_i95": stats(downwind_i95, "Downwind of I-95"),
        "not_downwind_i95": stats(not_downwind_i95, "Not downwind of I-95"),
        "both": stats(both, "Downwind of both"),
        "only_wheelabrator": stats(only_wb, "Only downwind of Wheelabrator"),
        "only_i95": stats(only_i95, "Only downwind of I-95"),
        "neither": stats(neither, "Neither"),
    }


def seasonal_directional_analysis(merged_df, value_col="arithmetic_mean"):
    """Break directional analysis down by season."""
    df = merged_df.copy()
    df["month"] = df["date_local"].dt.month
    df["season"] = df["month"].map({
        12: "Winter", 1: "Winter", 2: "Winter",
        3: "Spring", 4: "Spring", 5: "Spring",
        6: "Summer", 7: "Summer", 8: "Summer",
        9: "Fall", 10: "Fall", 11: "Fall",
    })

    results = {}
    for season in ["Winter", "Spring", "Summer", "Fall"]:
        subset = df[df["season"] == season]
        results[season] = directional_analysis(subset, value_col)
    return results
