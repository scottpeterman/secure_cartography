"""
SecureCartography NG - Database Schema.

SQLite schema for credential storage.

Design:
- Single credentials table with type discriminator
- Encrypted JSON blob for type-specific secrets
- Separate credential_sets table for grouping
- Tags as JSON array (SQLite 3.38+ has JSON functions)
- Full audit trail with timestamps

The schema supports multiple credential types in one table using
the 'credential_type' discriminator. Type-specific fields are stored
in 'secrets_encrypted' as a JSON blob after decryption.
"""

import sqlite3
from pathlib import Path
from typing import Optional

# Schema version for migrations
SCHEMA_VERSION = 1

SCHEMA_SQL = """
-- Vault metadata (salt, password hash, schema version)
CREATE TABLE IF NOT EXISTS vault_metadata (
    id INTEGER PRIMARY KEY,
    key TEXT UNIQUE NOT NULL,
    value TEXT
);

-- Main credentials table
CREATE TABLE IF NOT EXISTS credentials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Identity
    name TEXT UNIQUE NOT NULL,
    credential_type TEXT NOT NULL,  -- 'ssh', 'snmp_v2c', 'snmp_v3'
    description TEXT,

    -- Non-sensitive metadata (stored plaintext)
    -- For SSH: username
    -- For SNMPv3: username
    -- For SNMPv2c: NULL (community is secret)
    display_username TEXT,

    -- Port (plaintext, not sensitive)
    port INTEGER,

    -- Encrypted secrets as JSON blob
    -- SSH: {"password": "...", "key_content": "...", "key_passphrase": "..."}
    -- SNMPv2c: {"community": "..."}
    -- SNMPv3: {"auth_protocol": "...", "auth_password": "...", 
    --          "priv_protocol": "...", "priv_password": "..."}
    secrets_encrypted TEXT NOT NULL,

    -- Additional settings as JSON (plaintext)
    -- SSH: {"timeout_seconds": 30}
    -- SNMP: {"timeout_seconds": 5, "retries": 2, "context_name": "..."}
    settings_json TEXT DEFAULT '{}',

    -- Ordering and defaults
    priority INTEGER DEFAULT 100,  -- Lower = higher priority
    is_default INTEGER DEFAULT 0,

    -- Tags as JSON array
    tags_json TEXT DEFAULT '[]',

    -- Test tracking
    last_test_success INTEGER,  -- Boolean
    last_test_at TEXT,
    last_test_error TEXT,

    -- Usage tracking
    last_used_at TEXT,
    use_count INTEGER DEFAULT 0,

    -- Timestamps
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Credential sets (groups of credentials for device assignment)
CREATE TABLE IF NOT EXISTS credential_sets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    name TEXT UNIQUE NOT NULL,
    description TEXT,

    -- Credential references as JSON arrays (ordered by priority)
    ssh_credential_ids_json TEXT DEFAULT '[]',
    snmp_credential_ids_json TEXT DEFAULT '[]',

    -- Tags
    tags_json TEXT DEFAULT '[]',
    is_default INTEGER DEFAULT 0,

    -- Timestamps
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Device credential mappings (which credentials work for which devices)
CREATE TABLE IF NOT EXISTS device_credentials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Device identifier (could be name, IP, or external ID)
    device_identifier TEXT NOT NULL,
    device_identifier_type TEXT NOT NULL,  -- 'name', 'ip', 'netbox_id', etc.

    -- Working credential
    credential_id INTEGER NOT NULL,

    -- When discovered
    discovered_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_verified_at TEXT,

    -- Unique per device+type combination
    UNIQUE (device_identifier, device_identifier_type, credential_id),
    FOREIGN KEY (credential_id) REFERENCES credentials(id) ON DELETE CASCADE
);

-- Credential test history
CREATE TABLE IF NOT EXISTS credential_test_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    credential_id INTEGER NOT NULL,

    target_host TEXT NOT NULL,
    target_port INTEGER NOT NULL,

    success INTEGER NOT NULL,  -- Boolean
    status TEXT NOT NULL,  -- 'success', 'auth_failure', 'timeout', etc.
    error_message TEXT,

    -- Additional info
    duration_ms REAL,
    prompt_detected TEXT,  -- SSH
    system_description TEXT,  -- SNMP sysDescr

    tested_at TEXT NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY (credential_id) REFERENCES credentials(id) ON DELETE CASCADE
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_credentials_type ON credentials(credential_type);
CREATE INDEX IF NOT EXISTS idx_credentials_default ON credentials(is_default);
CREATE INDEX IF NOT EXISTS idx_credentials_priority ON credentials(priority);
CREATE INDEX IF NOT EXISTS idx_credentials_name ON credentials(name);

CREATE INDEX IF NOT EXISTS idx_credential_sets_default ON credential_sets(is_default);
CREATE INDEX IF NOT EXISTS idx_credential_sets_name ON credential_sets(name);

CREATE INDEX IF NOT EXISTS idx_device_credentials_device 
    ON device_credentials(device_identifier, device_identifier_type);
CREATE INDEX IF NOT EXISTS idx_device_credentials_credential 
    ON device_credentials(credential_id);

CREATE INDEX IF NOT EXISTS idx_test_history_credential 
    ON credential_test_history(credential_id);
CREATE INDEX IF NOT EXISTS idx_test_history_host 
    ON credential_test_history(target_host);
CREATE INDEX IF NOT EXISTS idx_test_history_time 
    ON credential_test_history(tested_at);

-- Triggers for updated_at
CREATE TRIGGER IF NOT EXISTS trg_credentials_updated
AFTER UPDATE ON credentials
BEGIN
    UPDATE credentials SET updated_at = datetime('now') WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_credential_sets_updated
AFTER UPDATE ON credential_sets
BEGIN
    UPDATE credential_sets SET updated_at = datetime('now') WHERE id = NEW.id;
END;
"""

# Views for common queries
VIEWS_SQL = """
-- View: Credential summary (without secrets)
CREATE VIEW IF NOT EXISTS v_credential_summary AS
SELECT 
    c.id,
    c.name,
    c.credential_type,
    c.description,
    c.display_username,
    c.port,
    c.priority,
    c.is_default,
    c.tags_json,
    c.last_test_success,
    c.last_test_at,
    c.last_used_at,
    c.use_count,
    c.created_at,
    c.updated_at,
    -- Derived fields
    CASE 
        WHEN c.credential_type = 'ssh' THEN 
            json_extract(c.settings_json, '$.timeout_seconds')
        ELSE 
            json_extract(c.settings_json, '$.timeout_seconds')
    END as timeout_seconds,
    (SELECT COUNT(*) FROM device_credentials dc WHERE dc.credential_id = c.id) as device_count
FROM credentials c;

-- View: Credential test statistics
CREATE VIEW IF NOT EXISTS v_credential_test_stats AS
SELECT 
    c.id,
    c.name,
    c.credential_type,
    COUNT(h.id) as total_tests,
    SUM(CASE WHEN h.success THEN 1 ELSE 0 END) as success_count,
    SUM(CASE WHEN NOT h.success THEN 1 ELSE 0 END) as failure_count,
    AVG(h.duration_ms) as avg_duration_ms,
    MAX(h.tested_at) as last_test_at
FROM credentials c
LEFT JOIN credential_test_history h ON c.id = h.credential_id
GROUP BY c.id;

-- View: Device credential coverage
CREATE VIEW IF NOT EXISTS v_device_credential_coverage AS
SELECT 
    dc.device_identifier,
    dc.device_identifier_type,
    COUNT(DISTINCT CASE WHEN c.credential_type = 'ssh' THEN c.id END) as ssh_credentials,
    COUNT(DISTINCT CASE WHEN c.credential_type IN ('snmp_v2c', 'snmp_v3') THEN c.id END) as snmp_credentials,
    MAX(dc.last_verified_at) as last_verified
FROM device_credentials dc
JOIN credentials c ON dc.credential_id = c.id
GROUP BY dc.device_identifier, dc.device_identifier_type;
"""


def init_schema(conn: sqlite3.Connection) -> None:
    """Initialize database schema."""
    conn.executescript(SCHEMA_SQL)
    conn.executescript(VIEWS_SQL)

    # Set schema version
    conn.execute(
        "INSERT OR REPLACE INTO vault_metadata (id, key, value) VALUES (1, 'schema_version', ?)",
        (str(SCHEMA_VERSION),)
    )
    conn.commit()


def get_schema_version(conn: sqlite3.Connection) -> Optional[int]:
    """Get current schema version."""
    try:
        cursor = conn.execute(
            "SELECT value FROM vault_metadata WHERE key = 'schema_version'"
        )
        row = cursor.fetchone()
        return int(row[0]) if row else None
    except sqlite3.OperationalError:
        return None


def migrate_schema(conn: sqlite3.Connection, current_version: int) -> None:
    """Run schema migrations if needed."""
    # Future migrations would go here
    # if current_version < 2:
    #     _migrate_v1_to_v2(conn)
    pass


class DatabaseManager:
    """
    Manages database connections and schema.

    Usage:
        db = DatabaseManager(Path("~/.scng/vault.db"))
        with db.connection() as conn:
            cursor = conn.execute("SELECT * FROM credentials")
    """

    def __init__(self, db_path: Path):
        self.db_path = db_path.expanduser()
        self._ensure_directory()

    def _ensure_directory(self) -> None:
        """Ensure database directory exists."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def connection(self) -> sqlite3.Connection:
        """
        Get database connection.

        Returns connection with row_factory set to sqlite3.Row.
        Caller should use as context manager or close explicitly.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def initialize(self) -> None:
        """Initialize database schema if needed."""
        conn = self.connection()
        try:
            version = get_schema_version(conn)

            if version is None:
                # New database
                init_schema(conn)
            elif version < SCHEMA_VERSION:
                # Need migration
                migrate_schema(conn, version)
        finally:
            conn.close()

    def is_initialized(self) -> bool:
        """Check if database has been initialized."""
        if not self.db_path.exists():
            return False

        conn = self.connection()
        try:
            version = get_schema_version(conn)
            return version is not None
        finally:
            conn.close()

    def get_vault_metadata(self, key: str) -> Optional[str]:
        """Get vault metadata value."""
        conn = self.connection()
        try:
            cursor = conn.execute(
                "SELECT value FROM vault_metadata WHERE key = ?",
                (key,)
            )
            row = cursor.fetchone()
            return row['value'] if row else None
        finally:
            conn.close()

    def set_vault_metadata(self, key: str, value: str) -> None:
        """Set vault metadata value."""
        conn = self.connection()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO vault_metadata (key, value) VALUES (?, ?)",
                (key, value)
            )
            conn.commit()
        finally:
            conn.close()