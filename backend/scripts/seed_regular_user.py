import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.auth import hash_password
from app.database import get_db


def main():
    with get_db() as conn:
        existing = conn.execute("SELECT id FROM users WHERE username = ?", ("regularUser",)).fetchone()
        if existing:
            print("Regular user already exists.")
        else:
            user_id = str(uuid.uuid4())
            password_hash = hash_password("userPass123")
            conn.execute(
                """INSERT INTO users (id, username, password_hash, name, role, is_active)
                   VALUES (?, ?, ?, ?, ?, TRUE)""",
                (user_id, "regularUser", password_hash, "Regular User", "user"),
            )
            print("Created regular user: username=regularUser, password=userPass123")

if __name__ == "__main__":
    main()
