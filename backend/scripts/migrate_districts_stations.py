"""
Migration script to update districts and police stations from Excel.
Adds 'code' column if missing and upserts data.
Usage: cd backend && python3 -m scripts.migrate_districts_stations
"""
import logging
import sys
import uuid
from pathlib import Path

import pandas as pd

# Add backend to sys.path to allow importing app.*
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import USE_POSTGRES, audit_log_insert, get_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

EXCEL_PATH = Path(__file__).resolve().parent.parent.parent / "District PS master.xlsx"

def ensure_columns(conn):
    """Ensure 'code' column exists in districts and police_stations."""
    logger.info("Checking for 'code' columns...")

    # Districts
    if USE_POSTGRES:
        # For Postgres, we check information_schema
        check_sql = "SELECT column_name FROM information_schema.columns WHERE table_name = 'districts' AND column_name = 'code'"
        res = conn.execute(check_sql).fetchone()
        if not res:
            logger.info("Adding 'code' column to districts (PostgreSQL)")
            conn.execute("ALTER TABLE districts ADD COLUMN code VARCHAR(50)")
    else:
        # For SQLite
        res = conn.execute("PRAGMA table_info(districts)").fetchall()
        columns = [r["name"] for r in res]
        if "code" not in columns:
            logger.info("Adding 'code' column to districts (SQLite)")
            conn.execute("ALTER TABLE districts ADD COLUMN code TEXT")

    # Police Stations
    if USE_POSTGRES:
        check_sql = "SELECT column_name FROM information_schema.columns WHERE table_name = 'police_stations' AND column_name = 'code'"
        res = conn.execute(check_sql).fetchone()
        if not res:
            logger.info("Adding 'code' column to police_stations (PostgreSQL)")
            conn.execute("ALTER TABLE police_stations ADD COLUMN code VARCHAR(50)")
    else:
        res = conn.execute("PRAGMA table_info(police_stations)").fetchall()
        columns = [r["name"] for r in res]
        if "code" not in columns:
            logger.info("Adding 'code' column to police_stations (SQLite)")
            conn.execute("ALTER TABLE police_stations ADD COLUMN code TEXT")

def migrate():
    if not EXCEL_PATH.exists():
        logger.error(f"Excel file not found at {EXCEL_PATH}")
        return

    logger.info(f"Reading Excel from {EXCEL_PATH}")
    df = pd.read_excel(EXCEL_PATH)

    # Handle potential column name variations/misspellings
    # Expected: ['Sr. No.', 'District Code', 'District Name', 'Police Staion Code', 'Police Station Name']
    col_map = {
        "District Code": "district_code",
        "District Name": "district_name",
        "Police Staion Code": "station_code",
        "Police Station Name": "station_name"
    }
    # Check if they exist, if not try to find similar ones
    actual_cols = df.columns.tolist()
    final_cols = {}
    for k, v in col_map.items():
        if k in actual_cols:
            final_cols[v] = k
        else:
            # Try exact match without trailing/leading spaces
            found = False
            for ac in actual_cols:
                if ac.strip() == k:
                    final_cols[v] = ac
                    found = True
                    break
            if not found:
                logger.error(f"Missing required column: {k}")
                return

    with get_db() as conn:
        ensure_columns(conn)

        added_districts = 0
        updated_districts = 0
        added_stations = 0
        updated_stations = 0

        # Cache for districts to avoid repeated lookups
        district_cache = {} # name -> id

        for index, row in df.iterrows():
            d_name = str(row[final_cols["district_name"]]).strip()
            d_code = str(row[final_cols["district_code"]]).strip()
            s_name = str(row[final_cols["station_name"]]).strip()
            s_code = str(row[final_cols["station_code"]]).strip()

            if index % 50 == 0:
                logger.info(f"Processing row {index}/{len(df)}...")

            # 1. Handle District
            if d_name not in district_cache:
                existing_d = conn.execute("SELECT id, code FROM districts WHERE name = ?", (d_name,)).fetchone()
                if existing_d:
                    d_id = existing_d["id"]
                    if str(existing_d["code"]) != d_code:
                        logger.info(f"Updating district code: {d_name} ({d_code})")
                        conn.execute("UPDATE districts SET code = ? WHERE id = ?", (d_code, d_id))
                        updated_districts += 1
                else:
                    d_id = str(uuid.uuid4())
                    logger.info(f"Adding new district: {d_name} ({d_code})")
                    conn.execute("INSERT INTO districts (id, name, code, is_active) VALUES (?, ?, ?, TRUE)", (d_id, d_name, d_code))
                    added_districts += 1
                    audit_log_insert(conn, "district.migrate", "district", d_id)
                district_cache[d_name] = d_id

            d_id = district_cache[d_name]

            # 2. Handle Station
            existing_s = conn.execute("SELECT id, code FROM police_stations WHERE district_id = ? AND name = ?", (d_id, s_name)).fetchone()
            if existing_s:
                s_id = existing_s["id"]
                if str(existing_s["code"]) != s_code:
                    logger.info(f"Updating station code: {s_name} in {d_name} ({s_code})")
                    conn.execute("UPDATE police_stations SET code = ? WHERE id = ?", (s_code, s_id))
                    updated_stations += 1
            else:
                s_id = str(uuid.uuid4())
                logger.info(f"Adding new station: {s_name} in {d_name} ({s_code})")
                conn.execute("INSERT INTO police_stations (id, district_id, name, code, is_active) VALUES (?, ?, ?, ?, TRUE)", (s_id, d_id, s_name, s_code))
                added_stations += 1
                audit_log_insert(conn, "station.migrate", "police_station", s_id)

    logger.info("Migration complete:")
    logger.info(f"Districts: {added_districts} added, {updated_districts} updated")
    logger.info(f"Stations: {added_stations} added, {updated_stations} updated")

if __name__ == "__main__":
    migrate()
