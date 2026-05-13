"""
System Data Reset Utility
Clears all case data, images, and face embeddings while preserving
authentication and static infrastructure (users, districts, police stations).

Usage:
    python scripts/reset_system_data.py [--production]
"""
import argparse
import os
import shutil
import sys

# Add backend to path to allow imports from app.*
sys.path.append(os.path.join(os.getcwd(), "backend"))

def main():
    parser = argparse.ArgumentParser(description="Reset UBIS system data.")
    parser.add_argument("--production", action="store_true", help="Force production environment targets")
    args = parser.parse_args()

    if args.production:
        os.environ["ENVIRONMENT"] = "production"
        print("!!! TARGETING PRODUCTION ENVIRONMENT !!!")

    try:
        from app.config import (
            AZURE_STORAGE_CONTAINER_REFERENCES,
            AZURE_STORAGE_CONTAINER_UPLOADS,
            QDRANT_COLLECTION,
            REFERENCE_PHOTOS_PATH,
            SUBMISSIONS_STORAGE_PATH,
            USE_AZURE_BLOB,
        )
        from app.database import USE_POSTGRES, get_db
        from app.services import qdrant_client
    except ImportError as e:
        print(f"Error: Could not import app modules. Ensure you are running from the project root: {e}")
        sys.exit(1)

    print(f"Environment: {os.getenv('ENVIRONMENT', 'development')}")
    print(f"Database: {'PostgreSQL' if USE_POSTGRES else 'SQLite'}")
    print(f"Storage: {'Azure Blob' if USE_AZURE_BLOB else 'Local'}")

    confirm = input("This will PERMANENTLY DELETE all cases and reference photos. Continue? (y/N): ")
    if confirm.lower() != 'y':
        print("Aborted.")
        sys.exit(0)

    # 1. Wipe Database
    print("\n[1/4] Wiping database tables...")
    tables = ["feedback", "matches", "images", "submissions", "reference_persons", "audit_log", "criminals"]
    with get_db() as conn:
        for table in tables:
            try:
                print(f"  Clearing {table}...")
                if USE_POSTGRES:
                    conn.execute(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE")
                else:
                    conn.execute(f"DELETE FROM {table}")
                    conn.execute(f"DELETE FROM sqlite_sequence WHERE name='{table}'")
            except Exception as e:
                print(f"  Warning: Failed to clear {table}: {e}")

    # 2. Reset Qdrant
    print("\n[2/4] Resetting Qdrant collections...")
    client = qdrant_client.get_client()
    if client:
        try:
            client.delete_collection(QDRANT_COLLECTION)
            qdrant_client.ensure_collection()
            print(f"  Collection '{QDRANT_COLLECTION}' reset successfully.")
        except Exception as e:
            print(f"  Error resetting Qdrant: {e}")
    else:
        print("  Qdrant client not available or not configured.")

    # 3. Clear Local Files
    print("\n[3/4] Clearing local media storage...")
    for path in [SUBMISSIONS_STORAGE_PATH, REFERENCE_PHOTOS_PATH]:
        if path.exists():
            print(f"  Clearing {path}...")
            for item in path.iterdir():
                if item.name == ".gitkeep":
                    continue
                try:
                    if item.is_file():
                        item.unlink()
                    elif item.is_dir():
                        shutil.rmtree(item)
                except Exception as e:
                    print(f"    Failed to delete {item}: {e}")

    # 4. Clear Azure Blobs (if configured)
    if USE_AZURE_BLOB:
        print("\n[4/4] Attempting to clear Azure Blob Storage...")
        print("  Please use Azure CLI for bulk deletion to ensure safety:")
        print(f"  az storage blob delete-batch --account-name <account> --source {AZURE_STORAGE_CONTAINER_UPLOADS}")
        print(f"  az storage blob delete-batch --account-name <account> --source {AZURE_STORAGE_CONTAINER_REFERENCES}")
    else:
        print("\n[4/4] Azure Blob Storage not in use. Skipping.")

    print("\nSystem reset complete.")

if __name__ == "__main__":
    main()
