"""
Database abstraction layer.
- Development: SQLite
- Production: PostgreSQL (Azure Database for PostgreSQL)
"""
import logging
import sqlite3
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from app.config import (
    DATABASE_URL,
    IS_PRODUCTION,
    POSTGRES_DB,
    POSTGRES_HOST,
    POSTGRES_PASSWORD,
    POSTGRES_PORT,
    POSTGRES_USER,
    SQLITE_PATH,
)

logger = logging.getLogger(__name__)

# ─── DATABASE TYPE DETECTION ───────────────────────────────────────────────────

def _get_postgres_dsn() -> str | None:
    """Build PostgreSQL DSN from environment variables."""
    if DATABASE_URL:
        return DATABASE_URL
    if POSTGRES_HOST and POSTGRES_USER and POSTGRES_PASSWORD:
        return f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
    return None


USE_POSTGRES = bool(_get_postgres_dsn())

if USE_POSTGRES:
    logger.info("Using PostgreSQL database")
else:
    logger.info(f"Using SQLite database: {SQLITE_PATH}")
    Path(SQLITE_PATH).parent.mkdir(parents=True, exist_ok=True)


# ─── CONNECTION POOLING (PostgreSQL) ───────────────────────────────────────────

_pg_pool = None

def _get_pg_pool():
    """Get or create PostgreSQL connection pool."""
    global _pg_pool
    if _pg_pool is None and USE_POSTGRES:
        try:
            from psycopg2 import pool
            dsn = _get_postgres_dsn()
            _pg_pool = pool.ThreadedConnectionPool(
                minconn=2,
                maxconn=20,
                dsn=dsn
            )
            logger.info("PostgreSQL connection pool created")
        except ImportError:
            logger.error("psycopg2 not installed. Run: pip install psycopg2-binary")
            raise
        except Exception as e:
            logger.error(f"Failed to create PostgreSQL pool: {e}")
            raise
    return _pg_pool


# ─── ROW FACTORY FOR POSTGRES ──────────────────────────────────────────────────

class DictRow(dict):
    """Dict-like row that also supports index access like sqlite3.Row."""
    def __init__(self, cursor, row):
        columns = [desc[0] for desc in cursor.description]
        super().__init__(zip(columns, row, strict=False))
        self._columns = columns
        self._row = row

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._row[key]
        return super().__getitem__(key)

    def keys(self):
        return self._columns


# ─── UNIFIED DATABASE CONTEXT MANAGER ──────────────────────────────────────────

@contextmanager
def get_db() -> Generator[Any, None, None]:
    """
    Get database connection. Yields a connection with dict-like row access.
    Works with both SQLite and PostgreSQL.
    """
    if USE_POSTGRES:
        pool = _get_pg_pool()
        conn = pool.getconn()
        try:
            # Enable dict-like row access
            import psycopg2.extras
            conn.cursor_factory = psycopg2.extras.RealDictCursor
            yield PostgresConnectionWrapper(conn)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            pool.putconn(conn)
    else:
        conn = sqlite3.connect(SQLITE_PATH)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()


class PostgresConnectionWrapper:
    """
    Wrapper to make psycopg2 connection API compatible with SQLite usage patterns.
    """
    def __init__(self, conn):
        self._conn = conn

    def execute(self, sql: str, params=None):
        """Execute a query with SQLite-style ? placeholders converted to %s."""
        cursor = self._conn.cursor()
        sql = _convert_placeholders(sql)
        cursor.execute(sql, params or ())
        return cursor

    def executescript(self, script: str):
        """Execute multiple statements (PostgreSQL compatible)."""
        cursor = self._conn.cursor()
        # Split by semicolons and execute each statement
        for stmt in script.split(';'):
            stmt = stmt.strip()
            if stmt:
                stmt = _convert_sql_to_postgres(stmt)
                try:
                    cursor.execute(stmt)
                except Exception as e:
                    logger.warning(f"Statement failed (may be expected): {e}")
        return cursor

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def cursor(self):
        return self._conn.cursor()


def _convert_placeholders(sql: str) -> str:
    """Convert SQLite ? placeholders to PostgreSQL %s placeholders."""
    return sql.replace('?', '%s')


def _convert_sql_to_postgres(sql: str) -> str:
    """Convert SQLite-specific SQL to PostgreSQL-compatible SQL."""
    sql = _convert_placeholders(sql)

    # Handle datetime('now') -> NOW()
    sql = sql.replace("datetime('now')", "NOW()")

    # Handle INTEGER PRIMARY KEY AUTOINCREMENT -> SERIAL PRIMARY KEY
    sql = sql.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")

    # Handle IF NOT EXISTS for index creation
    # PostgreSQL uses CREATE INDEX IF NOT EXISTS differently

    return sql


# ─── DATABASE INITIALIZATION ───────────────────────────────────────────────────

def init_db():
    """Initialize database schema."""
    if USE_POSTGRES:
        _init_postgres_db()
    else:
        _init_sqlite_db()


def _init_sqlite_db():
    """Initialize SQLite database."""
    with get_db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS submissions (
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            attributes_ai TEXT,
            attributes_manual TEXT,
            face_condition TEXT,
            status TEXT DEFAULT 'captured'
        );
        CREATE TABLE IF NOT EXISTS images (
            id TEXT PRIMARY KEY,
            submission_id TEXT NOT NULL REFERENCES submissions(id) ON DELETE CASCADE,
            image_type TEXT NOT NULL,
            path TEXT NOT NULL,
            face_condition TEXT,
            embedding_confidence REAL,
            quality_score REAL,
            qdrant_point_id TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS reference_persons (
            id TEXT PRIMARY KEY,
            label TEXT NOT NULL,
            photo_path TEXT,
            attributes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS matches (
            id TEXT PRIMARY KEY,
            submission_id TEXT NOT NULL,
            reference_person_id TEXT NOT NULL,
            overall_score REAL NOT NULL,
            face_score REAL,
            rank INTEGER NOT NULL,
            status TEXT DEFAULT 'pending_review',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS feedback (
            id TEXT PRIMARY KEY,
            match_id TEXT NOT NULL REFERENCES matches(id),
            reviewer_id TEXT,
            verdict TEXT NOT NULL,
            face_assessment TEXT,
            action_taken TEXT NOT NULL,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            action TEXT NOT NULL,
            resource_type TEXT,
            resource_id TEXT,
            ip_address TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            name TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'investigator',
            district TEXT,
            station TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS districts (
            id TEXT PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS police_stations (
            id TEXT PRIMARY KEY,
            district_id TEXT NOT NULL,
            name TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(district_id, name)
        );
        CREATE TABLE IF NOT EXISTS criminals (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            fir TEXT,
            district TEXT,
            station TEXT,
            arrest_date TEXT,
            notes TEXT,
            photo_paths TEXT,
            created_by TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_police_stations_district ON police_stations(district_id);
        CREATE INDEX IF NOT EXISTS idx_images_submission ON images(submission_id);
        CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log(created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
        """)

        _ensure_column(conn, "users", "district_id", "TEXT")
        _ensure_column(conn, "users", "station_id", "TEXT")
        _ensure_column(conn, "images", "quality_score", "REAL")
        _backfill_district_station_mapping(conn)


def _init_postgres_db():
    """Initialize PostgreSQL database with proper types."""
    with get_db() as conn:
        cursor = conn.cursor()

        # Create tables with PostgreSQL-compatible syntax
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS submissions (
            id VARCHAR(36) PRIMARY KEY,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            attributes_ai TEXT,
            attributes_manual TEXT,
            face_condition VARCHAR(50),
            status VARCHAR(50) DEFAULT 'captured'
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS images (
            id VARCHAR(36) PRIMARY KEY,
            submission_id VARCHAR(36) NOT NULL REFERENCES submissions(id) ON DELETE CASCADE,
            image_type VARCHAR(50) NOT NULL,
            path TEXT NOT NULL,
            face_condition VARCHAR(50),
            embedding_confidence REAL,
            quality_score REAL,
            qdrant_point_id VARCHAR(36),
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS reference_persons (
            id VARCHAR(36) PRIMARY KEY,
            label TEXT NOT NULL,
            photo_path TEXT,
            attributes TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS matches (
            id VARCHAR(36) PRIMARY KEY,
            submission_id VARCHAR(36) NOT NULL,
            reference_person_id VARCHAR(36) NOT NULL,
            overall_score REAL NOT NULL,
            face_score REAL,
            rank INTEGER NOT NULL,
            status VARCHAR(50) DEFAULT 'pending_review',
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id VARCHAR(36) PRIMARY KEY,
            match_id VARCHAR(36) NOT NULL REFERENCES matches(id),
            reviewer_id VARCHAR(36),
            verdict VARCHAR(50) NOT NULL,
            face_assessment VARCHAR(50),
            action_taken VARCHAR(100) NOT NULL,
            notes TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id SERIAL PRIMARY KEY,
            user_id VARCHAR(36),
            action VARCHAR(100) NOT NULL,
            resource_type VARCHAR(50),
            resource_id VARCHAR(36),
            ip_address VARCHAR(45),
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id VARCHAR(36) PRIMARY KEY,
            username VARCHAR(100) UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            name VARCHAR(200) NOT NULL,
            role VARCHAR(50) NOT NULL DEFAULT 'investigator',
            district VARCHAR(200),
            station VARCHAR(200),
            district_id VARCHAR(36),
            station_id VARCHAR(36),
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS districts (
            id VARCHAR(36) PRIMARY KEY,
            name VARCHAR(200) UNIQUE NOT NULL,
            code VARCHAR(50),
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS police_stations (
            id VARCHAR(36) PRIMARY KEY,
            district_id VARCHAR(36) NOT NULL,
            name VARCHAR(200) NOT NULL,
            code VARCHAR(50),
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            UNIQUE(district_id, name)
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS criminals (
            id VARCHAR(36) PRIMARY KEY,
            name VARCHAR(200) NOT NULL,
            fir VARCHAR(100),
            district VARCHAR(200),
            station VARCHAR(200),
            arrest_date DATE,
            notes TEXT,
            photo_paths TEXT,
            created_by VARCHAR(36),
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
        """)

        # Create indexes (PostgreSQL syntax)
        _create_index_if_not_exists(cursor, "idx_police_stations_district", "police_stations", "district_id")
        _create_index_if_not_exists(cursor, "idx_images_submission", "images", "submission_id")
        _create_index_if_not_exists(cursor, "idx_audit_created", "audit_log", "created_at DESC")
        _create_index_if_not_exists(cursor, "idx_users_username", "users", "username")
        _create_index_if_not_exists(cursor, "idx_criminals_name", "criminals", "name")
        _create_index_if_not_exists(cursor, "idx_criminals_fir", "criminals", "fir")

        conn.commit()
        logger.info("PostgreSQL database initialized")


def _create_index_if_not_exists(cursor, index_name: str, table: str, columns: str):
    """Create index if it doesn't exist (PostgreSQL)."""
    try:
        cursor.execute(f"CREATE INDEX IF NOT EXISTS {index_name} ON {table}({columns})")
    except Exception as e:
        logger.debug(f"Index {index_name} may already exist: {e}")


# ─── HELPER FUNCTIONS ──────────────────────────────────────────────────────────

def _ensure_column(conn, table: str, column: str, column_type: str) -> None:
    """Ensure a column exists in a table (SQLite only)."""
    if USE_POSTGRES:
        return  # PostgreSQL tables created with all columns

    existing = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column in existing:
        return
    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")


def _backfill_district_station_mapping(conn) -> None:
    """
    Best-effort backfill of normalized mapping from legacy users.district/users.station.
    - Creates districts and police_stations rows based on existing free-text values.
    - Sets users.district_id/users.station_id where possible.
    """
    if USE_POSTGRES:
        return  # PostgreSQL tables created with all columns

    cols = {r["name"] for r in conn.execute("PRAGMA table_info(users)").fetchall()}
    if "district_id" not in cols or "station_id" not in cols:
        return

    rows = conn.execute(
        """
        SELECT id, district, station
        FROM users
        WHERE (district_id IS NULL OR station_id IS NULL)
          AND (district IS NOT NULL OR station IS NOT NULL)
        """
    ).fetchall()
    if not rows:
        return

    district_cache: dict[str, str] = {}
    station_cache: dict[tuple[str, str], str] = {}

    for r in rows:
        user_id = r["id"]
        district_name = (r["district"] or "").strip()
        station_name = (r["station"] or "").strip()

        district_id = None
        station_id = None

        if district_name:
            if district_name in district_cache:
                district_id = district_cache[district_name]
            else:
                existing = conn.execute("SELECT id FROM districts WHERE name = ?", (district_name,)).fetchone()
                if existing:
                    district_id = existing["id"]
                else:
                    district_id = str(uuid.uuid4())
                    conn.execute("INSERT INTO districts (id, name, is_active) VALUES (?, ?, 1)", (district_id, district_name))
                district_cache[district_name] = district_id

        if district_id and station_name:
            key = (district_id, station_name)
            if key in station_cache:
                station_id = station_cache[key]
            else:
                existing = conn.execute(
                    "SELECT id FROM police_stations WHERE district_id = ? AND name = ?",
                    (district_id, station_name),
                ).fetchone()
                if existing:
                    station_id = existing["id"]
                else:
                    station_id = str(uuid.uuid4())
                    conn.execute(
                        "INSERT INTO police_stations (id, district_id, name, is_active) VALUES (?, ?, ?, 1)",
                        (station_id, district_id, station_name),
                    )
                station_cache[key] = station_id

        if district_id or station_id:
            conn.execute(
                "UPDATE users SET district_id = COALESCE(district_id, ?), station_id = COALESCE(station_id, ?) WHERE id = ?",
                (district_id, station_id, user_id),
            )


def audit_log_insert(conn, action: str, resource_type: str = None, resource_id: str = None, user_id: str = None, ip_address: str = None):
    """Insert an entry into the audit log."""
    if USE_POSTGRES:
        conn.execute(
            "INSERT INTO audit_log (action, resource_type, resource_id, user_id, ip_address) VALUES (%s, %s, %s, %s, %s)",
            (action, resource_type, resource_id, user_id, ip_address or "internal"),
        )
    else:
        conn.execute(
            "INSERT INTO audit_log (action, resource_type, resource_id, user_id, ip_address) VALUES (?, ?, ?, ?, ?)",
            (action, resource_type, resource_id, user_id, ip_address or "internal"),
        )


# ─── CONVENIENCE FUNCTIONS ─────────────────────────────────────────────────────

def get_db_info() -> dict:
    """Get information about the current database configuration."""
    return {
        "type": "postgresql" if USE_POSTGRES else "sqlite",
        "is_production": IS_PRODUCTION,
        "connection": _get_postgres_dsn()[:50] + "..." if USE_POSTGRES and _get_postgres_dsn() else SQLITE_PATH,
    }
