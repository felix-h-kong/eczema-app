import sqlite3
from pathlib import Path


class Database:
    def __init__(self, db_path):
        self.db_path = Path(db_path)

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def execute(self, sql, params=()):
        conn = self._connect()
        cursor = conn.execute(sql, params)
        conn.commit()
        # Wrap in a proxy so fetchall/fetchone work after connection is open
        rows = cursor.fetchall()
        conn.close()

        class _CursorProxy:
            def __init__(self, rows):
                self._rows = rows

            def fetchall(self):
                return self._rows

            def fetchone(self):
                return self._rows[0] if self._rows else None

        return _CursorProxy(rows)

    def init(self):
        conn = self._connect()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS log_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    type TEXT NOT NULL,
                    raw_input TEXT,
                    severity INTEGER,
                    notes TEXT,
                    medication_name TEXT,
                    medication_dose TEXT,
                    parse_status TEXT NOT NULL DEFAULT 'pending',
                    parsed_ingredients TEXT,
                    synced INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS ingredient_aliases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    variant TEXT NOT NULL UNIQUE,
                    canonical TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS entry_images (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    log_entry_id INTEGER NOT NULL REFERENCES log_entries(id) ON DELETE CASCADE,
                    image_path TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS push_subscriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    endpoint TEXT NOT NULL UNIQUE,
                    keys_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                );
            """)
            conn.commit()
        finally:
            conn.close()

    def insert_log_entry(self, timestamp, entry_type, raw_input=None, severity=None,
                          medication_name=None, medication_dose=None, notes=None):
        conn = self._connect()
        try:
            cursor = conn.execute(
                """INSERT INTO log_entries
                   (timestamp, type, raw_input, severity, medication_name, medication_dose, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (timestamp, entry_type, raw_input, severity, medication_name, medication_dose, notes)
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def get_log_entry(self, entry_id):
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM log_entries WHERE id = ?", (entry_id,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_log_entries(self, entry_type=None, from_date=None, to_date=None):
        sql = "SELECT * FROM log_entries WHERE 1=1"
        params = []
        if entry_type is not None:
            sql += " AND type = ?"
            params.append(entry_type)
        if from_date is not None:
            sql += " AND timestamp >= ?"
            params.append(from_date)
        if to_date is not None:
            sql += " AND timestamp <= ?"
            params.append(to_date)
        sql += " ORDER BY timestamp DESC"

        conn = self._connect()
        try:
            rows = conn.execute(sql, params).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def update_log_entry(self, entry_id, **fields):
        if not fields:
            return
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        set_clause += ", updated_at = datetime('now')"
        params = list(fields.values()) + [entry_id]
        conn = self._connect()
        try:
            conn.execute(
                f"UPDATE log_entries SET {set_clause} WHERE id = ?", params
            )
            conn.commit()
        finally:
            conn.close()

    def delete_log_entry(self, entry_id):
        conn = self._connect()
        try:
            conn.execute("DELETE FROM entry_images WHERE log_entry_id = ?", (entry_id,))
            conn.execute("DELETE FROM log_entries WHERE id = ?", (entry_id,))
            conn.commit()
        finally:
            conn.close()

    def update_parse_result(self, entry_id, status, ingredients):
        self.update_log_entry(entry_id, parse_status=status, parsed_ingredients=ingredients)

    def add_alias(self, variant, canonical):
        conn = self._connect()
        try:
            conn.execute(
                """INSERT INTO ingredient_aliases (variant, canonical)
                   VALUES (?, ?)
                   ON CONFLICT(variant) DO UPDATE SET canonical = excluded.canonical""",
                (variant, canonical)
            )
            conn.commit()
        finally:
            conn.close()

    def resolve_alias(self, ingredient):
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT canonical FROM ingredient_aliases WHERE variant = ?", (ingredient,)
            ).fetchone()
            return row["canonical"] if row else ingredient
        finally:
            conn.close()

    def list_aliases(self):
        conn = self._connect()
        try:
            rows = conn.execute("SELECT * FROM ingredient_aliases").fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def add_image(self, log_entry_id, image_path, timestamp):
        conn = self._connect()
        try:
            cursor = conn.execute(
                "INSERT INTO entry_images (log_entry_id, image_path, timestamp) VALUES (?, ?, ?)",
                (log_entry_id, image_path, timestamp)
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def list_images(self, log_entry_id):
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM entry_images WHERE log_entry_id = ?", (log_entry_id,)
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def add_push_subscription(self, endpoint, keys_json):
        conn = self._connect()
        try:
            conn.execute(
                """INSERT INTO push_subscriptions (endpoint, keys_json)
                   VALUES (?, ?)
                   ON CONFLICT(endpoint) DO UPDATE SET
                       keys_json = excluded.keys_json,
                       updated_at = datetime('now')""",
                (endpoint, keys_json)
            )
            conn.commit()
        finally:
            conn.close()

    def list_push_subscriptions(self):
        conn = self._connect()
        try:
            rows = conn.execute("SELECT * FROM push_subscriptions").fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()
