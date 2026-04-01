"""
Fetch Toxics Release Inventory (TRI) data for Wheelabrator Baltimore / WIN Waste.
Uses EPA Envirofacts REST API — no API key required.
"""

import os
import pandas as pd
import requests

from src.config import DATA_DIR

ENVIROFACTS_BASE = "https://enviro.epa.gov/enviro/efservice"


def search_tri_facility(name_contains="WHEELABRATOR", city="BALTIMORE", state="MD"):
    """Search for TRI facilities matching the given criteria."""
    url = (
        f"{ENVIROFACTS_BASE}/tri_facility"
        f"/FACILITY_NAME/CONTAINING/{name_contains}"
        f"/CITY_NAME/{city}"
        f"/STATE_ABBR/{state}"
        f"/JSON"
    )
    print(f"Searching TRI facilities: {name_contains} in {city}, {state}")
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    if not data:
        # Try WIN WASTE as alternate name
        url = (
            f"{ENVIROFACTS_BASE}/tri_facility"
            f"/FACILITY_NAME/CONTAINING/WIN%20WASTE"
            f"/CITY_NAME/{city}"
            f"/STATE_ABBR/{state}"
            f"/JSON"
        )
        print(f"Trying alternate name: WIN WASTE")
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()

    if data:
        df = pd.DataFrame(data)
        print(f"Found {len(df)} facility records")
        if "FACILITY_NAME" in df.columns:
            print(f"  Facilities: {df['FACILITY_NAME'].unique()}")
        if "TRI_FACILITY_ID" in df.columns:
            print(f"  TRI IDs: {df['TRI_FACILITY_ID'].unique()}")
        return df
    else:
        print("No facilities found")
        return pd.DataFrame()


def fetch_tri_releases(facility_id=None, facility_name="WHEELABRATOR", state="MD"):
    """
    Fetch TRI release quantities. If facility_id is known, use it directly.
    Otherwise search by name.
    """
    if facility_id:
        url = f"{ENVIROFACTS_BASE}/tri_release_qty/TRI_FACILITY_ID/{facility_id}/JSON"
    else:
        # Use the reporting form table which has both facility info and release data
        url = (
            f"{ENVIROFACTS_BASE}/tri_release_qty"
            f"/JSON/rows/0:9999"
        )
        # Envirofacts doesn't easily join tables in URL, so we'll get facility IDs first
        fac_df = search_tri_facility(name_contains=facility_name, state=state)
        if fac_df.empty:
            return pd.DataFrame()

        tri_ids = fac_df["TRI_FACILITY_ID"].unique()
        all_releases = []
        for tid in tri_ids:
            print(f"  Fetching releases for facility {tid}...")
            url = f"{ENVIROFACTS_BASE}/tri_release_qty/TRI_FACILITY_ID/{tid}/JSON"
            resp = requests.get(url, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            if data:
                df = pd.DataFrame(data)
                df["TRI_FACILITY_ID"] = tid
                all_releases.append(df)
                print(f"    Got {len(df)} release records")

        if all_releases:
            return pd.concat(all_releases, ignore_index=True)
        return pd.DataFrame()

    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    return pd.DataFrame(data) if data else pd.DataFrame()


def fetch_tri_chemicals(facility_id=None, facility_name="WHEELABRATOR", state="MD"):
    """Fetch chemical-level reporting for the facility."""
    fac_df = search_tri_facility(name_contains=facility_name, state=state)
    if fac_df.empty:
        return pd.DataFrame()

    tri_ids = fac_df["TRI_FACILITY_ID"].unique()
    all_chems = []
    for tid in tri_ids:
        print(f"  Fetching chemical reports for {tid}...")
        url = f"{ENVIROFACTS_BASE}/tri_reporting_form/TRI_FACILITY_ID/{tid}/JSON"
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        if data:
            df = pd.DataFrame(data)
            all_chems.append(df)
            print(f"    Got {len(df)} chemical records")

    if all_chems:
        return pd.concat(all_chems, ignore_index=True)
    return pd.DataFrame()


def save_tri_data(fac_df, releases_df, chems_df):
    os.makedirs(DATA_DIR, exist_ok=True)

    if not fac_df.empty:
        path = os.path.join(DATA_DIR, "tri_facilities.csv")
        fac_df.to_csv(path, index=False)
        print(f"Saved facilities to {path}")

    if not releases_df.empty:
        path = os.path.join(DATA_DIR, "tri_releases.csv")
        releases_df.to_csv(path, index=False)
        print(f"Saved releases to {path}")

    if not chems_df.empty:
        path = os.path.join(DATA_DIR, "tri_chemicals.csv")
        chems_df.to_csv(path, index=False)
        print(f"Saved chemicals to {path}")


if __name__ == "__main__":
    print("=== TRI Data Acquisition ===\n")

    print("1. Searching for facility...")
    fac_df = search_tri_facility()

    print("\n2. Fetching release quantities...")
    releases_df = fetch_tri_releases()

    print("\n3. Fetching chemical reports...")
    chems_df = fetch_tri_chemicals()

    print("\n4. Saving data...")
    save_tri_data(fac_df, releases_df, chems_df)

    if not releases_df.empty:
        print(f"\n=== Release Summary ===")
        print(f"Total release records: {len(releases_df)}")
        print(f"Columns: {list(releases_df.columns)}")
