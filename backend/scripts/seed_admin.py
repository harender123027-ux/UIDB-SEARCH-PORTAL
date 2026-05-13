"""
Create default admin user if none exists.
Also seeds districts and police stations for Haryana.
Usage: python -m scripts.seed_admin

If the environment variable INITIAL_ADMIN_PASSWORD is set when this script
runs, that value is used as the initial admin password.  Otherwise the
fallback "changeme" is used (and the operator MUST change it on first login).
This lets `scripts/onprem/install.sh` provision a strong random password
without baking secrets into the codebase.
"""
import os
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.auth import hash_password
from app.database import get_db, init_db

# Haryana districts and their police stations
HARYANA_GEO_DATA = {
    "Ambala": ["Ambala City", "Ambala Cantt", "Barara", "Naraingarh", "Shahzadpur"],
    "Faridabad": ["Faridabad Central", "Ballabhgarh", "NIT Faridabad", "Sector 17", "Old Faridabad"],
    "Gurugram": ["Gurugram City", "DLF Phase 1", "Sohna", "Manesar", "Palam Vihar", "Cyber City"],
    "Hisar": ["Hisar City", "Hansi", "Barwala", "Uklana", "Narnaund"],
    "Karnal": ["Karnal City", "Gharaunda", "Nilokheri", "Assandh", "Indri"],
    "Panchkula": ["Panchkula City", "Kalka", "Pinjore", "Raipur Rani", "Morni"],
    "Panipat": ["Panipat City", "Samalkha", "Israna", "Madlauda", "Bapoli"],
    "Rohtak": ["Rohtak City", "Meham", "Kalanaur", "Lakhan Majra", "Asthal Bohar"],
    "Sonipat": ["Sonipat City", "Ganaur", "Gohana", "Kharkhoda", "Mundlana"],
    "Yamunanagar": ["Yamunanagar City", "Jagadhri", "Radaur", "Bilaspur", "Chhachhrauli"],
    "Jhajjar": ["Jhajjar City", "Bahadurgarh", "Beri", "Machhrauli", "Dighal"],
    "Rewari": ["Rewari City", "Dharuhera", "Bawal", "Kosli", "Jatusana"],
    "Bhiwani": ["Bhiwani City", "Charkhi Dadri", "Loharu", "Siwani", "Tosham"],
    "Jind": ["Jind City", "Safidon", "Julana", "Narwana", "Uchana"],
    "Kaithal": ["Kaithal City", "Cheeka", "Pundri", "Kalayat", "Guhla"],
}


def seed_districts_and_stations(conn):
    """Seed districts and police stations if not present."""
    existing_districts = conn.execute("SELECT name FROM districts").fetchall()
    existing_names = {r["name"] for r in existing_districts}

    added_districts = 0
    added_stations = 0

    for district_name, stations in HARYANA_GEO_DATA.items():
        if district_name in existing_names:
            # Get existing district id
            row = conn.execute("SELECT id FROM districts WHERE name = ?", (district_name,)).fetchone()
            district_id = row["id"]
        else:
            # Create district
            district_id = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO districts (id, name, is_active) VALUES (?, ?, TRUE)",
                (district_id, district_name),
            )
            added_districts += 1

        # Add stations for this district
        existing_stations = conn.execute(
            "SELECT name FROM police_stations WHERE district_id = ?", (district_id,)
        ).fetchall()
        existing_station_names = {r["name"] for r in existing_stations}

        for station_name in stations:
            if station_name not in existing_station_names:
                station_id = str(uuid.uuid4())
                conn.execute(
                    "INSERT INTO police_stations (id, district_id, name, is_active) VALUES (?, ?, ?, TRUE)",
                    (station_id, district_id, station_name),
                )
                added_stations += 1

    return added_districts, added_stations


def main():
    init_db()
    with get_db() as conn:
        # Seed admin user
        existing = conn.execute("SELECT id FROM users WHERE username = ?", ("admin",)).fetchone()
        if existing:
            print("Admin user already exists. Skipping.")
        else:
            user_id = str(uuid.uuid4())
            initial_pw = os.environ.get("INITIAL_ADMIN_PASSWORD") or "changeme"
            password_hash = hash_password(initial_pw)
            conn.execute(
                """INSERT INTO users (id, username, password_hash, name, role, is_active)
                   VALUES (?, ?, ?, ?, ?, TRUE)""",
                (user_id, "admin", password_hash, "Administrator", "admin"),
            )
            if initial_pw == "changeme":
                print("Created admin user: username=admin, password=changeme")
                print("WARNING: change the password immediately after first login.")
            else:
                print("Created admin user: username=admin (password from INITIAL_ADMIN_PASSWORD env)")
                print("Store this password securely — it will not be printed again.")

        # Seed districts and stations
        added_districts, added_stations = seed_districts_and_stations(conn)
        if added_districts or added_stations:
            print(f"Seeded {added_districts} districts and {added_stations} police stations.")
        else:
            print("Districts and police stations already seeded. Skipping.")


if __name__ == "__main__":
    main()
