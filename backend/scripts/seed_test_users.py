"""
Seed test users for Playwright E2E tests.
Creates admin and regular users matching tests/fixtures/test-users.json
Usage: python -m scripts.seed_test_users
"""
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.auth import hash_password
from app.database import get_db, init_db

TEST_USERS = [
    {
        "username": "admin",
        "password": "changeme",
        "name": "Administrator",
        "role": "admin",
    },
    {
        "username": "adminUser",
        "password": "adminPass123",
        "name": "Admin Test User",
        "role": "admin",
    },
    {
        "username": "regularUser",
        "password": "userPass123",
        "name": "Regular Test User",
        "role": "investigator",
    },
    {
        "username": "userA",
        "password": "userAPassword",
        "name": "User A",
        "role": "investigator",
    },
    {
        "username": "userB",
        "password": "userBPassword",
        "name": "User B",
        "role": "investigator",
    },
]


def main():
    init_db()
    with get_db() as conn:
        for user in TEST_USERS:
            existing = conn.execute(
                "SELECT id FROM users WHERE username = ?", (user["username"],)
            ).fetchone()
            if existing:
                print(f"User '{user['username']}' already exists. Skipping.")
            else:
                user_id = str(uuid.uuid4())
                password_hash = hash_password(user["password"])
                conn.execute(
                    """INSERT INTO users (id, username, password_hash, name, role, is_active)
                       VALUES (?, ?, ?, ?, ?, 1)""",
                    (user_id, user["username"], password_hash, user["name"], user["role"]),
                )
                print(f"Created user: username={user['username']}, password={user['password']}, role={user['role']}")

        print("\nTest users seeded successfully!")
        print("You can now run Playwright tests with: npx playwright test")


if __name__ == "__main__":
    main()
