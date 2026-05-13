import os
import sys
import uuid

import bcrypt

# Add the backend dir to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import get_db


def seed_admin():
    print("Seeding admin user...")
    admin_id = str(uuid.uuid4())
    username = "admin"
    password = "password"  # default password

    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    with get_db() as conn:
        # Check if admin already exists
        row = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        if row:
            print("Admin user already exists.")
            return

        conn.execute(
            """
            INSERT INTO users (id, username, password_hash, name, role, is_active)
            VALUES (?, ?, ?, ?, ?, 1)
            """,
            (admin_id, username, password_hash, "System Administrator", "admin")
        )
        print("Successfully seeded admin user: username='admin', password='password'")

if __name__ == "__main__":
    seed_admin()
