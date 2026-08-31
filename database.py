"""
WesternFX IB Management Tool — Database Layer (v2: Monthly Snapshots)
=======================================================================
SQLite schema creation and helper functions.
"""
import os
import sqlite3
from datetime import datetime
from contextlib import contextmanager

from config import DATABASE_PATH, DEFAULT_API_URLS


# ── Ensure data directory exists ──────────────────────────
os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)


# ── SQL Schema (v2 — monthly snapshots) ──────────────────
SCHEMA = """
-- Settings: editable API URLs and preferences
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- Monthly snapshots: raw API 3 data imported per month
CREATE TABLE IF NOT EXISTS monthly_snapshots (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    month_label   TEXT NOT NULL,
    snapshot_date TEXT NOT NULL,
    raw_json      TEXT NOT NULL
);

-- Client records: flattened data per snapshot for fast querying
CREATE TABLE IF NOT EXISTS client_records (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id      INTEGER NOT NULL,
    account          TEXT    NOT NULL,
    fullName         TEXT,
    email            TEXT,
    equity           REAL,
    balance          REAL,
    pnl              REAL,
    deposit          REAL,
    commission       REAL,
    commissionTotal  REAL,
    status           TEXT,
    referred_by      TEXT,
    FOREIGN KEY (snapshot_id) REFERENCES monthly_snapshots(id)
);

-- Client history: lifetime tracking per unique account
CREATE TABLE IF NOT EXISTS client_history (
    account                  TEXT PRIMARY KEY,
    first_seen_snapshot_id   INTEGER,
    last_seen_snapshot_id    INTEGER,
    first_seen_date          TEXT,
    last_active_date         TEXT,
    total_snapshots          INTEGER DEFAULT 0
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_client_records_snapshot ON client_records(snapshot_id);
CREATE INDEX IF NOT EXISTS idx_client_records_account  ON client_records(account);
CREATE INDEX IF NOT EXISTS idx_client_records_status   ON client_records(status);
CREATE INDEX IF NOT EXISTS idx_monthly_snapshots_label ON monthly_snapshots(month_label);
"""


# ── Connection Helper ───────────────────────────────────
@contextmanager
def get_db():
    """Yield a SQLite connection with row factory."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Create tables and seed default settings."""
    with get_db() as conn:
        conn.executescript(SCHEMA)
        # Seed default API URLs if not present
        for key, url in DEFAULT_API_URLS.items():
            conn.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                (key + "_url", url),
            )
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
            ("initialized", datetime.utcnow().isoformat()),
        )
        # Seed Dropbox token if provided in environment
        dropbox_token = os.environ.get("DROPBOX_ACCESS_TOKEN")
        if dropbox_token:
            conn.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                ("dropbox_token", dropbox_token),
            )


# ── Settings Helpers ────────────────────────────────────
def get_setting(key, default=None):
    with get_db() as conn:
        row = conn.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else default


def set_setting(key, value):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?)"
            " ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )


def get_all_settings():
    with get_db() as conn:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
        return {r["key"]: r["value"] for r in rows}


# ── Snapshot Helpers ────────────────────────────────────
def create_snapshot(month_label, raw_json):
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO monthly_snapshots (month_label, snapshot_date, raw_json)"
            " VALUES (?, ?, ?)",
            (month_label, datetime.utcnow().isoformat(), raw_json),
        )
        return cursor.lastrowid


def get_latest_snapshot():
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM monthly_snapshots ORDER BY snapshot_date DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None


def get_snapshot_by_id(snapshot_id):
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM monthly_snapshots WHERE id = ?", (snapshot_id,)
        ).fetchone()
        return dict(row) if row else None


def get_all_snapshots():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM monthly_snapshots ORDER BY snapshot_date DESC"
        ).fetchall()
        return [dict(r) for r in rows]


# ── Client Record Helpers ───────────────────────────────
def save_client_records(snapshot_id, clients, referrer_mapping=None):
    """Insert multiple client records for a snapshot.
    referrer_mapping: dict {account: referred_by} to tag each record."""
    with get_db() as conn:
        for c in clients:
            acct = str(c.get("account", ""))
            referred_by = ""
            if referrer_mapping and acct in referrer_mapping:
                referred_by = referrer_mapping[acct]
            conn.execute(
                """INSERT INTO client_records
                (snapshot_id, account, fullName, email, equity, balance,
                 pnl, deposit, commission, commissionTotal, status, referred_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    snapshot_id,
                    acct,
                    c.get("fullName", ""),
                    c.get("email", ""),
                    _to_float(c.get("equity")),
                    _to_float(c.get("balance")),
                    _to_float(c.get("pnl")),
                    _to_float(c.get("deposit")),
                    _to_float(c.get("commission")),
                    _to_float(c.get("commissionTotal")),
                    c.get("status", ""),
                    referred_by,
                ),
            )


def get_clients_by_snapshot(snapshot_id, referrer=None):
    """Return clients for a snapshot, optionally filtered by referrer."""
    with get_db() as conn:
        if referrer:
            rows = conn.execute(
                "SELECT * FROM client_records WHERE snapshot_id = ? AND referred_by = ?",
                (snapshot_id, referrer),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM client_records WHERE snapshot_id = ?",
                (snapshot_id,),
            ).fetchall()
        return [dict(r) for r in rows]


def get_clients_by_snapshot_with_referrers(snapshot_id):
    """Return all clients with their referrer values (for backfill)."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, account, referred_by FROM client_records WHERE snapshot_id = ?",
            (snapshot_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def update_client_referred_by(record_id, referred_by):
    """Update the referred_by field for a single client record."""
    with get_db() as conn:
        conn.execute(
            "UPDATE client_records SET referred_by = ? WHERE id = ?",
            (referred_by, record_id),
        )


def get_referrers_for_snapshot(snapshot_id):
    """Return distinct referrer values for a snapshot."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT DISTINCT referred_by FROM client_records WHERE snapshot_id = ? AND referred_by IS NOT NULL AND referred_by != ''",
            (snapshot_id,),
        ).fetchall()
        return [r["referred_by"] for r in rows if r["referred_by"]]


def get_client_monthly_history(account):
    """Get all monthly records for a single account, ordered by date."""
    with get_db() as conn:
        rows = conn.execute(
            """SELECT cr.*, ms.month_label, ms.snapshot_date
               FROM client_records cr
               JOIN monthly_snapshots ms ON cr.snapshot_id = ms.id
               WHERE cr.account = ?
               ORDER BY ms.snapshot_date ASC""",
            (account,),
        ).fetchall()
        return [dict(r) for r in rows]


def delete_snapshot(snapshot_id):
    """Delete a snapshot and all related records, then rebuild affected client histories."""
    with get_db() as conn:
        # Get accounts affected by this snapshot
        rows = conn.execute(
            "SELECT DISTINCT account FROM client_records WHERE snapshot_id = ?",
            (snapshot_id,)
        ).fetchall()
        accounts = [r[0] for r in rows]

        # Delete client records for this snapshot
        conn.execute("DELETE FROM client_records WHERE snapshot_id = ?", (snapshot_id,))

        # Delete the snapshot itself
        conn.execute("DELETE FROM monthly_snapshots WHERE id = ?", (snapshot_id,))

        # Rebuild client_history for affected accounts
        for account in accounts:
            remaining = conn.execute(
                """SELECT cr.snapshot_id, ms.snapshot_date
                   FROM client_records cr
                   JOIN monthly_snapshots ms ON cr.snapshot_id = ms.id
                   WHERE cr.account = ?
                   ORDER BY ms.snapshot_date ASC""",
                (account,)
            ).fetchall()

            if not remaining:
                conn.execute("DELETE FROM client_history WHERE account = ?", (account,))
            else:
                first = remaining[0]
                last = remaining[-1]
                conn.execute(
                    """INSERT INTO client_history
                       (account, first_seen_snapshot_id, last_seen_snapshot_id,
                        first_seen_date, last_active_date, total_snapshots)
                       VALUES (?, ?, ?, ?, ?, ?)
                       ON CONFLICT(account) DO UPDATE SET
                         first_seen_snapshot_id = excluded.first_seen_snapshot_id,
                         last_seen_snapshot_id = excluded.last_seen_snapshot_id,
                         first_seen_date = excluded.first_seen_date,
                         last_active_date = excluded.last_active_date,
                         total_snapshots = excluded.total_snapshots""",
                    (account, first[0], last[0], first[1], last[1], len(remaining))
                )

        return True


# ── Client History Helpers ──────────────────────────────
def upsert_client_history(account, first_seen_snapshot_id, first_seen_date):
    with get_db() as conn:
        conn.execute(
            """INSERT INTO client_history
               (account, first_seen_snapshot_id, last_seen_snapshot_id,
                first_seen_date, last_active_date, total_snapshots)
               VALUES (?, ?, ?, ?, ?, 1)
               ON CONFLICT(account) DO UPDATE SET
                 last_seen_snapshot_id = excluded.last_seen_snapshot_id,
                 last_active_date = excluded.last_active_date,
                 total_snapshots = total_snapshots + 1""",
            (account, first_seen_snapshot_id, first_seen_snapshot_id,
             first_seen_date, first_seen_date),
        )


def update_client_last_seen(account, snapshot_id, active_date):
    with get_db() as conn:
        conn.execute(
            """UPDATE client_history
               SET last_seen_snapshot_id = ?,
                   last_active_date = ?,
                   total_snapshots = total_snapshots + 1
               WHERE account = ?""",
            (snapshot_id, active_date, account),
        )


def get_client_history(account):
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM client_history WHERE account = ?", (account,)
        ).fetchone()
        return dict(row) if row else None


def get_all_client_histories():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM client_history").fetchall()
        return [dict(r) for r in rows]


# ── Utilities ───────────────────────────────────────────
def _to_float(value):
    """Safely convert API value to float."""
    if value is None or value == "" or value == "N/A":
        return 0.0
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0
