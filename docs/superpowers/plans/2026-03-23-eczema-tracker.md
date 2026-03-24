# Eczema Trigger Tracker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a self-hosted PWA for logging meals, flares, medications, and notes, then correlating ingredients with eczema flares over time.

**Architecture:** FastAPI backend serving a built React frontend from `backend/static/`. SQLite database in `data/`. Claude API for ingredient parsing and analysis summaries. Web Push for meal reminders.

**Tech Stack:** Python 3.11+, FastAPI, SQLite, React 18, TypeScript, Vite, Claude API (anthropic SDK), pandas, scipy, pywebpush, APScheduler

**Spec:** `docs/superpowers/specs/2026-03-23-eczema-tracker-design.md`

---

## Task 1: Project Scaffolding

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/config.py`
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/tsconfig.node.json`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/public/manifest.json`
- Create: `Makefile`
- Modify: `.gitignore`

- [ ] **Step 1: Create backend requirements.txt**

```
fastapi==0.115.*
uvicorn[standard]==0.34.*
anthropic==0.52.*
pandas==2.2.*
scipy==1.15.*
pywebpush==2.0.*
apscheduler==3.10.*
python-multipart==0.0.*
httpx==0.28.*
pytest==8.3.*
pytest-asyncio==0.25.*
```

- [ ] **Step 2: Create backend/config.py**

```python
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
IMAGES_DIR = DATA_DIR / "images"
DB_PATH = DATA_DIR / "eczema.db"
STATIC_DIR = Path(__file__).resolve().parent / "static"

# Claude API
CLAUDE_MODEL = "claude-haiku-4-5-20251001"

# Notification schedule (AEST = UTC+10/+11 DST)
NOTIFICATION_TIMES_AEST = {
    "breakfast": "07:30",
    "lunch": "12:00",
    "dinner": "18:30",
}
NOTIFICATION_SKIP_WINDOW_HOURS = 2

# Analysis
FLARE_WINDOW_HOURS = (6, 48)  # meals 6-48h before flare
MEDICATION_CONFOUND_HOURS = 12
MIN_FLARE_APPEARANCES = 2
LOW_FLARE_WARNING_THRESHOLD = 10
```

- [ ] **Step 3: Create frontend scaffolding**

Initialize with Vite React-TS template:

```bash
cd frontend && npm create vite@latest . -- --template react-ts
```

Then update `vite.config.ts`:

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
  build: {
    outDir: '../backend/static',
    emptyOutDir: true,
  },
})
```

Update `frontend/public/manifest.json`:

```json
{
  "name": "Eczema Trigger Tracker",
  "short_name": "EczemaLog",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#ffffff",
  "theme_color": "#4a90d9",
  "icons": [
    {
      "src": "/icon-192.png",
      "sizes": "192x192",
      "type": "image/png"
    },
    {
      "src": "/icon-512.png",
      "sizes": "512x512",
      "type": "image/png"
    }
  ]
}
```

- [ ] **Step 4: Create Makefile**

```makefile
.PHONY: dev dev-backend dev-frontend build backup

dev-backend:
	cd backend && uvicorn main:app --reload --host 0.0.0.0 --port 8000

dev-frontend:
	cd frontend && npm run dev

dev:
	$(MAKE) dev-backend & $(MAKE) dev-frontend & wait

build:
	cd frontend && npm run build

test-backend:
	cd backend && python -m pytest tests/ -v

test-frontend:
	cd frontend && npm test

test: test-backend test-frontend

backup:
	mkdir -p data/backups
	sqlite3 data/eczema.db ".backup data/backups/eczema-$$(date +%Y%m%d-%H%M%S).db"
```

- [ ] **Step 5: Update .gitignore**

Append to existing `.gitignore`:

```
data/
.superpowers/
__pycache__/
*.pyc
.pytest_cache/
backend/static/
node_modules/
frontend/dist/
.env
*.egg-info/
```

- [ ] **Step 6: Create data directories**

```bash
mkdir -p data/images
```

- [ ] **Step 7: Install dependencies and verify**

```bash
cd backend && pip install -r requirements.txt
cd frontend && npm install
```

Run: `cd frontend && npx vite --version` — should print version.
Run: `cd backend && python -c "import fastapi; print(fastapi.__version__)"` — should print version.

- [ ] **Step 8: Commit**

```bash
git add backend/requirements.txt backend/config.py frontend/ Makefile .gitignore
git commit -m "feat: project scaffolding with FastAPI backend and React frontend"
```

---

## Task 2: SQLite Schema + Database Module

**Files:**
- Create: `backend/db.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/test_db.py`

- [ ] **Step 1: Write failing tests for database initialization and CRUD**

Create `backend/tests/__init__.py` (empty file).

Create `backend/tests/test_db.py`:

```python
import pytest
import os
import tempfile
from pathlib import Path


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "test.db"


@pytest.fixture
def db(db_path):
    from db import Database
    database = Database(db_path)
    database.init()
    return database


class TestDatabaseInit:
    def test_creates_tables(self, db, db_path):
        assert db_path.exists()
        tables = db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        table_names = {row["name"] for row in tables}
        assert "log_entries" in table_names
        assert "ingredient_aliases" in table_names
        assert "entry_images" in table_names
        assert "push_subscriptions" in table_names


class TestLogEntries:
    def test_insert_meal_entry(self, db):
        entry_id = db.insert_log_entry(
            timestamp="2026-03-23T08:30:00Z",
            entry_type="meal",
            raw_input="rice and chicken",
        )
        assert entry_id == 1
        entry = db.get_log_entry(entry_id)
        assert entry["type"] == "meal"
        assert entry["raw_input"] == "rice and chicken"
        assert entry["parse_status"] == "pending"

    def test_insert_flare_entry(self, db):
        entry_id = db.insert_log_entry(
            timestamp="2026-03-23T10:00:00Z",
            entry_type="flare",
            severity=7,
            notes="itchy arms",
        )
        entry = db.get_log_entry(entry_id)
        assert entry["type"] == "flare"
        assert entry["severity"] == 7
        assert entry["notes"] == "itchy arms"

    def test_insert_medication_entry(self, db):
        entry_id = db.insert_log_entry(
            timestamp="2026-03-23T09:00:00Z",
            entry_type="medication",
            medication_name="cetirizine",
            medication_dose="10mg",
        )
        entry = db.get_log_entry(entry_id)
        assert entry["medication_name"] == "cetirizine"
        assert entry["medication_dose"] == "10mg"

    def test_insert_note_entry(self, db):
        entry_id = db.insert_log_entry(
            timestamp="2026-03-23T11:00:00Z",
            entry_type="note",
            notes="ate out at Thai restaurant",
        )
        entry = db.get_log_entry(entry_id)
        assert entry["type"] == "note"
        assert entry["notes"] == "ate out at Thai restaurant"

    def test_list_entries_with_type_filter(self, db):
        db.insert_log_entry(timestamp="2026-03-23T08:00:00Z", entry_type="meal", raw_input="toast")
        db.insert_log_entry(timestamp="2026-03-23T09:00:00Z", entry_type="flare", severity=3)
        db.insert_log_entry(timestamp="2026-03-23T10:00:00Z", entry_type="meal", raw_input="rice")

        meals = db.list_log_entries(entry_type="meal")
        assert len(meals) == 2

        flares = db.list_log_entries(entry_type="flare")
        assert len(flares) == 1

    def test_list_entries_with_date_filter(self, db):
        db.insert_log_entry(timestamp="2026-03-22T08:00:00Z", entry_type="meal", raw_input="toast")
        db.insert_log_entry(timestamp="2026-03-23T08:00:00Z", entry_type="meal", raw_input="rice")
        db.insert_log_entry(timestamp="2026-03-24T08:00:00Z", entry_type="meal", raw_input="pasta")

        entries = db.list_log_entries(from_date="2026-03-23T00:00:00Z", to_date="2026-03-23T23:59:59Z")
        assert len(entries) == 1
        assert entries[0]["raw_input"] == "rice"

    def test_update_log_entry(self, db):
        entry_id = db.insert_log_entry(
            timestamp="2026-03-23T08:00:00Z", entry_type="meal", raw_input="toast"
        )
        db.update_log_entry(entry_id, raw_input="toast with butter")
        entry = db.get_log_entry(entry_id)
        assert entry["raw_input"] == "toast with butter"

    def test_delete_log_entry(self, db):
        entry_id = db.insert_log_entry(
            timestamp="2026-03-23T08:00:00Z", entry_type="meal", raw_input="toast"
        )
        db.delete_log_entry(entry_id)
        entry = db.get_log_entry(entry_id)
        assert entry is None

    def test_update_parse_status(self, db):
        entry_id = db.insert_log_entry(
            timestamp="2026-03-23T08:00:00Z", entry_type="meal", raw_input="rice"
        )
        db.update_parse_result(entry_id, status="parsed", ingredients='{"confirmed":["rice"],"likely":[],"source":"text"}')
        entry = db.get_log_entry(entry_id)
        assert entry["parse_status"] == "parsed"
        assert "rice" in entry["parsed_ingredients"]


class TestIngredientAliases:
    def test_add_and_resolve_alias(self, db):
        db.add_alias("tamari", "soy sauce")
        assert db.resolve_alias("tamari") == "soy sauce"
        assert db.resolve_alias("rice") == "rice"  # no alias, returns input

    def test_list_aliases(self, db):
        db.add_alias("tamari", "soy sauce")
        db.add_alias("capsicum", "bell pepper")
        aliases = db.list_aliases()
        assert len(aliases) == 2


class TestEntryImages:
    def test_add_and_list_images(self, db):
        entry_id = db.insert_log_entry(
            timestamp="2026-03-23T08:00:00Z", entry_type="meal", raw_input="rice"
        )
        db.add_image(entry_id, "2026/03/23/abc123.jpg", "2026-03-23T08:00:00Z")
        images = db.list_images(entry_id)
        assert len(images) == 1
        assert images[0]["image_path"] == "2026/03/23/abc123.jpg"


class TestPushSubscriptions:
    def test_add_subscription(self, db):
        db.add_push_subscription(
            endpoint="https://push.example.com/sub1",
            keys_json='{"p256dh":"key1","auth":"auth1"}',
        )
        subs = db.list_push_subscriptions()
        assert len(subs) == 1
        assert subs[0]["endpoint"] == "https://push.example.com/sub1"

    def test_duplicate_endpoint_updates(self, db):
        db.add_push_subscription("https://push.example.com/sub1", '{"p256dh":"key1","auth":"auth1"}')
        db.add_push_subscription("https://push.example.com/sub1", '{"p256dh":"key2","auth":"auth2"}')
        subs = db.list_push_subscriptions()
        assert len(subs) == 1
        assert "key2" in subs[0]["keys_json"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_db.py -v
```

Expected: ImportError — `db` module does not exist.

- [ ] **Step 3: Implement db.py**

Create `backend/db.py`:

```python
import sqlite3
from pathlib import Path
from typing import Optional


class Database:
    def __init__(self, db_path: Path):
        self.db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        conn = self._connect()
        try:
            cursor = conn.execute(sql, params)
            conn.commit()
            return cursor
        finally:
            conn.close()

    def init(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = self._connect()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS log_entries (
                    id INTEGER PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    type TEXT NOT NULL,
                    raw_input TEXT,
                    parsed_ingredients TEXT,
                    parse_status TEXT DEFAULT 'pending',
                    severity INTEGER,
                    medication_name TEXT,
                    medication_dose TEXT,
                    notes TEXT,
                    synced INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS ingredient_aliases (
                    id INTEGER PRIMARY KEY,
                    variant TEXT UNIQUE,
                    canonical TEXT
                );

                CREATE TABLE IF NOT EXISTS entry_images (
                    id INTEGER PRIMARY KEY,
                    log_entry_id INTEGER REFERENCES log_entries(id),
                    image_path TEXT,
                    timestamp TEXT
                );

                CREATE TABLE IF NOT EXISTS push_subscriptions (
                    id INTEGER PRIMARY KEY,
                    endpoint TEXT UNIQUE NOT NULL,
                    keys_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
            """)
        finally:
            conn.close()

    def insert_log_entry(
        self,
        timestamp: str,
        entry_type: str,
        raw_input: Optional[str] = None,
        severity: Optional[int] = None,
        medication_name: Optional[str] = None,
        medication_dose: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> int:
        conn = self._connect()
        try:
            cursor = conn.execute(
                """INSERT INTO log_entries (timestamp, type, raw_input, severity,
                   medication_name, medication_dose, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (timestamp, entry_type, raw_input, severity, medication_name, medication_dose, notes),
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def get_log_entry(self, entry_id: int) -> Optional[dict]:
        conn = self._connect()
        try:
            row = conn.execute("SELECT * FROM log_entries WHERE id = ?", (entry_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_log_entries(
        self,
        entry_type: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
    ) -> list[dict]:
        conditions = []
        params = []
        if entry_type:
            conditions.append("type = ?")
            params.append(entry_type)
        if from_date:
            conditions.append("timestamp >= ?")
            params.append(from_date)
        if to_date:
            conditions.append("timestamp <= ?")
            params.append(to_date)
        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        conn = self._connect()
        try:
            rows = conn.execute(
                f"SELECT * FROM log_entries{where} ORDER BY timestamp DESC", tuple(params)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def update_log_entry(self, entry_id: int, **fields) -> None:
        if not fields:
            return
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        conn = self._connect()
        try:
            conn.execute(
                f"UPDATE log_entries SET {set_clause} WHERE id = ?",
                (*fields.values(), entry_id),
            )
            conn.commit()
        finally:
            conn.close()

    def delete_log_entry(self, entry_id: int) -> None:
        conn = self._connect()
        try:
            conn.execute("DELETE FROM entry_images WHERE log_entry_id = ?", (entry_id,))
            conn.execute("DELETE FROM log_entries WHERE id = ?", (entry_id,))
            conn.commit()
        finally:
            conn.close()

    def update_parse_result(self, entry_id: int, status: str, ingredients: Optional[str] = None) -> None:
        self.update_log_entry(entry_id, parse_status=status, parsed_ingredients=ingredients)

    # Ingredient aliases
    def add_alias(self, variant: str, canonical: str) -> None:
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO ingredient_aliases (variant, canonical) VALUES (?, ?) "
                "ON CONFLICT(variant) DO UPDATE SET canonical = excluded.canonical",
                (variant, canonical),
            )
            conn.commit()
        finally:
            conn.close()

    def resolve_alias(self, ingredient: str) -> str:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT canonical FROM ingredient_aliases WHERE variant = ?", (ingredient,)
            ).fetchone()
            return row["canonical"] if row else ingredient
        finally:
            conn.close()

    def list_aliases(self) -> list[dict]:
        conn = self._connect()
        try:
            rows = conn.execute("SELECT * FROM ingredient_aliases ORDER BY variant").fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # Entry images
    def add_image(self, log_entry_id: int, image_path: str, timestamp: str) -> int:
        conn = self._connect()
        try:
            cursor = conn.execute(
                "INSERT INTO entry_images (log_entry_id, image_path, timestamp) VALUES (?, ?, ?)",
                (log_entry_id, image_path, timestamp),
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def list_images(self, log_entry_id: int) -> list[dict]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM entry_images WHERE log_entry_id = ? ORDER BY timestamp",
                (log_entry_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # Push subscriptions
    def add_push_subscription(self, endpoint: str, keys_json: str) -> None:
        from datetime import datetime, timezone
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO push_subscriptions (endpoint, keys_json, created_at) VALUES (?, ?, ?) "
                "ON CONFLICT(endpoint) DO UPDATE SET keys_json = excluded.keys_json",
                (endpoint, keys_json, datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()
        finally:
            conn.close()

    def list_push_subscriptions(self) -> list[dict]:
        conn = self._connect()
        try:
            rows = conn.execute("SELECT * FROM push_subscriptions").fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && python -m pytest tests/test_db.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/db.py backend/tests/
git commit -m "feat: SQLite database module with full CRUD operations"
```

---

## Task 3: FastAPI Core + Log Endpoints

**Files:**
- Create: `backend/main.py`
- Create: `backend/tests/test_main.py`

- [ ] **Step 1: Write failing tests for API endpoints**

Create `backend/tests/test_main.py`:

```python
import pytest
from fastapi.testclient import TestClient
import tempfile
from pathlib import Path


@pytest.fixture
def client(tmp_path):
    import config
    config.DB_PATH = tmp_path / "test.db"
    config.DATA_DIR = tmp_path
    config.IMAGES_DIR = tmp_path / "images"

    from main import app, get_db
    from db import Database

    db = Database(config.DB_PATH)
    db.init()

    def override_get_db():
        return db

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestPostLog:
    def test_create_meal_entry(self, client):
        resp = client.post("/api/log", json={
            "timestamp": "2026-03-23T08:30:00Z",
            "type": "meal",
            "raw_input": "rice and chicken",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert "id" in data
        assert data["id"] == 1

    def test_create_flare_entry(self, client):
        resp = client.post("/api/log", json={
            "timestamp": "2026-03-23T10:00:00Z",
            "type": "flare",
            "severity": 7,
            "notes": "itchy arms",
        })
        assert resp.status_code == 201

    def test_create_medication_entry(self, client):
        resp = client.post("/api/log", json={
            "timestamp": "2026-03-23T09:00:00Z",
            "type": "medication",
            "medication_name": "cetirizine",
            "medication_dose": "10mg",
        })
        assert resp.status_code == 201

    def test_create_note_entry(self, client):
        resp = client.post("/api/log", json={
            "timestamp": "2026-03-23T11:00:00Z",
            "type": "note",
            "notes": "ate out at Thai restaurant",
        })
        assert resp.status_code == 201

    def test_invalid_type_rejected(self, client):
        resp = client.post("/api/log", json={
            "timestamp": "2026-03-23T08:00:00Z",
            "type": "invalid",
        })
        assert resp.status_code == 422


class TestGetLogs:
    def test_list_all_entries(self, client):
        client.post("/api/log", json={"timestamp": "2026-03-23T08:00:00Z", "type": "meal", "raw_input": "toast"})
        client.post("/api/log", json={"timestamp": "2026-03-23T09:00:00Z", "type": "flare", "severity": 3})
        resp = client.get("/api/logs")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_filter_by_type(self, client):
        client.post("/api/log", json={"timestamp": "2026-03-23T08:00:00Z", "type": "meal", "raw_input": "toast"})
        client.post("/api/log", json={"timestamp": "2026-03-23T09:00:00Z", "type": "flare", "severity": 3})
        resp = client.get("/api/logs?type=meal")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_filter_by_date_range(self, client):
        client.post("/api/log", json={"timestamp": "2026-03-22T08:00:00Z", "type": "meal", "raw_input": "toast"})
        client.post("/api/log", json={"timestamp": "2026-03-23T08:00:00Z", "type": "meal", "raw_input": "rice"})
        resp = client.get("/api/logs?from=2026-03-23T00:00:00Z&to=2026-03-23T23:59:59Z")
        assert len(resp.json()) == 1


class TestUpdateDeleteLog:
    def test_update_entry(self, client):
        resp = client.post("/api/log", json={
            "timestamp": "2026-03-23T08:00:00Z", "type": "meal", "raw_input": "toast"
        })
        entry_id = resp.json()["id"]
        resp = client.put(f"/api/log/{entry_id}", json={"raw_input": "toast with butter"})
        assert resp.status_code == 200

    def test_delete_entry(self, client):
        resp = client.post("/api/log", json={
            "timestamp": "2026-03-23T08:00:00Z", "type": "meal", "raw_input": "toast"
        })
        entry_id = resp.json()["id"]
        resp = client.delete(f"/api/log/{entry_id}")
        assert resp.status_code == 200
        resp = client.get("/api/logs")
        assert len(resp.json()) == 0

    def test_update_nonexistent_returns_404(self, client):
        resp = client.put("/api/log/999", json={"raw_input": "nope"})
        assert resp.status_code == 404

    def test_delete_nonexistent_returns_404(self, client):
        resp = client.delete("/api/log/999")
        assert resp.status_code == 404


class TestAdminEndpoints:
    def test_list_ingredients(self, client):
        resp = client.get("/api/admin/ingredients")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_add_alias(self, client):
        resp = client.post("/api/admin/aliases", json={
            "variant": "tamari",
            "canonical": "soy sauce",
        })
        assert resp.status_code == 201


class TestPushSubscription:
    def test_subscribe(self, client):
        resp = client.post("/api/push/subscribe", json={
            "endpoint": "https://push.example.com/sub1",
            "keys": {"p256dh": "key1", "auth": "auth1"},
        })
        assert resp.status_code == 201
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_main.py -v
```

Expected: ImportError — `main` module does not exist.

- [ ] **Step 3: Implement main.py**

Create `backend/main.py`:

```python
import json
from enum import Enum
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config import DB_PATH, STATIC_DIR
from db import Database

app = FastAPI()

# Global database instance
_db: Optional[Database] = None


def get_db() -> Database:
    global _db
    if _db is None:
        _db = Database(DB_PATH)
        _db.init()
    return _db


# --- Models ---

class EntryType(str, Enum):
    meal = "meal"
    flare = "flare"
    medication = "medication"
    note = "note"


class LogEntryCreate(BaseModel):
    timestamp: str
    type: EntryType
    raw_input: Optional[str] = None
    severity: Optional[int] = None
    medication_name: Optional[str] = None
    medication_dose: Optional[str] = None
    notes: Optional[str] = None


class LogEntryUpdate(BaseModel):
    raw_input: Optional[str] = None
    severity: Optional[int] = None
    medication_name: Optional[str] = None
    medication_dose: Optional[str] = None
    notes: Optional[str] = None


class AliasCreate(BaseModel):
    variant: str
    canonical: str


class PushSubscribeRequest(BaseModel):
    endpoint: str
    keys: dict


# --- Endpoints ---

@app.post("/api/log", status_code=201)
def create_log_entry(entry: LogEntryCreate, db: Database = Depends(get_db)):
    entry_id = db.insert_log_entry(
        timestamp=entry.timestamp,
        entry_type=entry.type.value,
        raw_input=entry.raw_input,
        severity=entry.severity,
        medication_name=entry.medication_name,
        medication_dose=entry.medication_dose,
        notes=entry.notes,
    )
    # TODO: Task 4 will add background parsing for meal entries here
    return {"id": entry_id}


@app.get("/api/logs")
def list_logs(
    type: Optional[str] = Query(None),
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    db: Database = Depends(get_db),
):
    return db.list_log_entries(entry_type=type, from_date=from_date, to_date=to_date)


@app.put("/api/log/{entry_id}")
def update_log_entry(entry_id: int, update: LogEntryUpdate, db: Database = Depends(get_db)):
    existing = db.get_log_entry(entry_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Entry not found")
    fields = {k: v for k, v in update.model_dump().items() if v is not None}
    if fields:
        db.update_log_entry(entry_id, **fields)
    return {"ok": True}


@app.delete("/api/log/{entry_id}")
def delete_log_entry(entry_id: int, db: Database = Depends(get_db)):
    existing = db.get_log_entry(entry_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Entry not found")
    db.delete_log_entry(entry_id)
    return {"ok": True}


@app.get("/api/admin/ingredients")
def list_ingredients(db: Database = Depends(get_db)):
    """Return all unique ingredients sorted by frequency."""
    entries = db.list_log_entries(entry_type="meal")
    freq: dict[str, int] = {}
    for entry in entries:
        if entry.get("parsed_ingredients"):
            data = json.loads(entry["parsed_ingredients"])
            for ing in data.get("confirmed", []) + data.get("likely", []):
                canonical = db.resolve_alias(ing.lower())
                freq[canonical] = freq.get(canonical, 0) + 1
    return sorted(
        [{"ingredient": k, "count": v} for k, v in freq.items()],
        key=lambda x: x["count"],
        reverse=True,
    )


@app.post("/api/admin/aliases", status_code=201)
def add_alias(alias: AliasCreate, db: Database = Depends(get_db)):
    db.add_alias(alias.variant, alias.canonical)
    return {"ok": True}


@app.post("/api/push/subscribe", status_code=201)
def push_subscribe(req: PushSubscribeRequest, db: Database = Depends(get_db)):
    db.add_push_subscription(
        endpoint=req.endpoint,
        keys_json=json.dumps(req.keys),
    )
    return {"ok": True}


# Serve static files (built frontend) — must be last
if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && python -m pytest tests/test_main.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/main.py backend/tests/test_main.py
git commit -m "feat: FastAPI endpoints for log CRUD, admin, and push subscriptions"
```

---

## Task 4: Claude API Ingredient Parsing

**Files:**
- Create: `backend/prompts.py`
- Create: `backend/parsing.py`
- Create: `backend/tests/test_parsing.py`

- [ ] **Step 1: Create prompts.py**

```python
TEXT_PARSING_PROMPT = """Extract the food ingredients from this meal description. Return a JSON object with:
- "confirmed": ingredients explicitly mentioned
- "likely": ingredients that are commonly part of the described dishes but not explicitly stated
- "source": "text"

Be specific about individual ingredients. For example, "stir fry with rice" should list rice, oil, and whatever protein/vegetables are mentioned or likely.

Return ONLY valid JSON, no other text.

Meal description: {meal_text}"""

IMAGE_PARSING_PROMPT = """Look at this meal photo and identify the food ingredients. Return a JSON object with:
- "confirmed": ingredients you can clearly identify
- "likely": ingredients that are probably present but not clearly visible
- "source": "image"

Return ONLY valid JSON, no other text."""

ANALYSIS_SUMMARY_PROMPT = """You are helping someone track eczema triggers by analysing correlations between food ingredients and flare-ups.

Here are the statistical results:

{stats_table}

Key metrics:
- lift: how much more frequently an ingredient appears before flares vs. normal meals (>1.0 = more common before flares)
- flare_appearances: number of distinct flare events this ingredient preceded
- confounded_flares: flare events where medication was also taken (±12h), which may mask the true trigger

{warnings}

Write a clear, cautious summary in plain English. Highlight the top suspects but emphasise:
1. Correlation does not prove causation
2. More data improves confidence
3. Consider elimination diets for top suspects, one at a time
4. Consult a dermatologist or allergist for proper testing

Keep it under 200 words."""
```

- [ ] **Step 2: Write failing tests for parsing**

Create `backend/tests/test_parsing.py`:

```python
import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock


class TestParseIngredients:
    def test_parse_text_success(self):
        from parsing import parse_ingredients_from_text

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"confirmed":["rice","chicken"],"likely":["soy sauce"],"source":"text"}')]

        with patch("parsing.get_client") as mock_client:
            mock_client.return_value.messages.create.return_value = mock_response
            result = parse_ingredients_from_text("rice and chicken stir fry")

        assert result["confirmed"] == ["rice", "chicken"]
        assert result["likely"] == ["soy sauce"]
        assert result["source"] == "text"

    def test_parse_text_returns_none_on_api_error(self):
        from parsing import parse_ingredients_from_text

        with patch("parsing.get_client") as mock_client:
            mock_client.return_value.messages.create.side_effect = Exception("API error")
            result = parse_ingredients_from_text("rice")

        assert result is None

    def test_parse_text_returns_none_on_invalid_json(self):
        from parsing import parse_ingredients_from_text

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="not json")]

        with patch("parsing.get_client") as mock_client:
            mock_client.return_value.messages.create.return_value = mock_response
            result = parse_ingredients_from_text("rice")

        assert result is None


class TestBackgroundParsing:
    def test_process_pending_entry(self):
        """Test that process_pending_entry updates the database."""
        from parsing import process_pending_entry
        from unittest.mock import MagicMock

        mock_db = MagicMock()
        mock_db.get_log_entry.return_value = {
            "id": 1, "type": "meal", "raw_input": "rice and chicken",
            "parse_status": "pending",
        }

        parsed = {"confirmed": ["rice", "chicken"], "likely": [], "source": "text"}

        with patch("parsing.parse_ingredients_from_text", return_value=parsed):
            process_pending_entry(mock_db, 1)

        mock_db.update_parse_result.assert_called_once_with(
            1, status="parsed", ingredients=json.dumps(parsed)
        )

    def test_process_pending_entry_marks_failed(self):
        from parsing import process_pending_entry
        from unittest.mock import MagicMock

        mock_db = MagicMock()
        mock_db.get_log_entry.return_value = {
            "id": 1, "type": "meal", "raw_input": "rice",
            "parse_status": "pending",
        }

        with patch("parsing.parse_ingredients_from_text", return_value=None):
            process_pending_entry(mock_db, 1)

        mock_db.update_parse_result.assert_called_once_with(1, status="failed", ingredients=None)
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_parsing.py -v
```

Expected: ImportError — `parsing` module does not exist.

- [ ] **Step 4: Implement parsing.py**

```python
import json
import logging
from typing import Optional

import anthropic

from config import CLAUDE_MODEL
from prompts import TEXT_PARSING_PROMPT

logger = logging.getLogger(__name__)

_client: Optional[anthropic.Anthropic] = None


def get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()  # uses ANTHROPIC_API_KEY env var
    return _client


def parse_ingredients_from_text(meal_text: str) -> Optional[dict]:
    """Call Claude to extract ingredients from meal text. Returns parsed dict or None on failure."""
    try:
        response = get_client().messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": TEXT_PARSING_PROMPT.format(meal_text=meal_text),
            }],
        )
        raw = response.content[0].text.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        return json.loads(raw)
    except (json.JSONDecodeError, Exception) as e:
        logger.error(f"Failed to parse ingredients: {e}")
        return None


def process_pending_entry(db, entry_id: int) -> None:
    """Parse a pending meal entry and update the database."""
    entry = db.get_log_entry(entry_id)
    if not entry or entry["parse_status"] != "pending":
        return

    result = parse_ingredients_from_text(entry["raw_input"])
    if result:
        db.update_parse_result(entry_id, status="parsed", ingredients=json.dumps(result))
    else:
        db.update_parse_result(entry_id, status="failed", ingredients=None)
```

- [ ] **Step 5: Wire background parsing into main.py**

Add to `main.py` — in the `create_log_entry` function, after inserting the entry:

```python
from fastapi import BackgroundTasks

# Update create_log_entry signature to include background_tasks: BackgroundTasks
# After insert, if type is meal:
if entry.type == EntryType.meal and entry.raw_input:
    from parsing import process_pending_entry
    background_tasks.add_task(process_pending_entry, db, entry_id)
```

- [ ] **Step 6: Run all tests**

```bash
cd backend && python -m pytest tests/ -v
```

Expected: All tests PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/prompts.py backend/parsing.py backend/tests/test_parsing.py backend/main.py
git commit -m "feat: Claude API ingredient parsing with background processing"
```

---

## Task 5: Frontend PWA — Scaffolding + API Client

**Files:**
- Create: `frontend/src/api.ts`
- Modify: `frontend/src/App.tsx`
- Create: `frontend/src/pages/MealLog.tsx`
- Create: `frontend/src/pages/FlareLog.tsx`
- Create: `frontend/src/pages/MedsLog.tsx`
- Create: `frontend/src/pages/NoteLog.tsx`
- Create: `frontend/src/pages/Analysis.tsx`
- Create: `frontend/src/components/TabBar.tsx`
- Create: `frontend/src/components/Toast.tsx`

- [ ] **Step 1: Create API client**

Create `frontend/src/api.ts`:

```typescript
const API_BASE = '/api';

export interface LogEntry {
  id: number;
  timestamp: string;
  type: 'meal' | 'flare' | 'medication' | 'note';
  raw_input?: string;
  parsed_ingredients?: string;
  parse_status?: string;
  severity?: number;
  medication_name?: string;
  medication_dose?: string;
  notes?: string;
}

export interface CreateLogEntry {
  timestamp: string;
  type: 'meal' | 'flare' | 'medication' | 'note';
  raw_input?: string;
  severity?: number;
  medication_name?: string;
  medication_dose?: string;
  notes?: string;
}

export interface AnalysisResult {
  stats: Array<{
    ingredient: string;
    lift: number;
    flare_freq: number;
    baseline_freq: number;
    flare_appearances: number;
    confounded: number;
  }>;
  summary: string;
  warning?: string;
}

export async function createLogEntry(entry: CreateLogEntry): Promise<{ id: number }> {
  const resp = await fetch(`${API_BASE}/log`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(entry),
  });
  if (!resp.ok) throw new Error(`Failed to create entry: ${resp.status}`);
  return resp.json();
}

export async function getLogEntries(params?: {
  type?: string;
  from?: string;
  to?: string;
}): Promise<LogEntry[]> {
  const query = new URLSearchParams();
  if (params?.type) query.set('type', params.type);
  if (params?.from) query.set('from', params.from);
  if (params?.to) query.set('to', params.to);
  const resp = await fetch(`${API_BASE}/logs?${query}`);
  if (!resp.ok) throw new Error(`Failed to fetch entries: ${resp.status}`);
  return resp.json();
}

export async function updateLogEntry(id: number, update: Partial<CreateLogEntry>): Promise<void> {
  const resp = await fetch(`${API_BASE}/log/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(update),
  });
  if (!resp.ok) throw new Error(`Failed to update entry: ${resp.status}`);
}

export async function deleteLogEntry(id: number): Promise<void> {
  const resp = await fetch(`${API_BASE}/log/${id}`, { method: 'DELETE' });
  if (!resp.ok) throw new Error(`Failed to delete entry: ${resp.status}`);
}

export async function startAnalysis(useLikely: boolean = false): Promise<{ job_id: string }> {
  const resp = await fetch(`${API_BASE}/analyse`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ use_likely: useLikely }),
  });
  if (!resp.ok) throw new Error(`Failed to start analysis: ${resp.status}`);
  return resp.json();
}

export async function getAnalysisResult(jobId: string): Promise<AnalysisResult & { status: string }> {
  const resp = await fetch(`${API_BASE}/analyse/${jobId}`);
  if (!resp.ok) throw new Error(`Failed to fetch analysis: ${resp.status}`);
  return resp.json();
}

export async function subscribePush(subscription: PushSubscription): Promise<void> {
  const json = subscription.toJSON();
  const resp = await fetch(`${API_BASE}/push/subscribe`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      endpoint: json.endpoint,
      keys: json.keys,
    }),
  });
  if (!resp.ok) throw new Error(`Failed to subscribe: ${resp.status}`);
}

export async function lookupBarcode(upc: string): Promise<{ ingredients: string }> {
  const resp = await fetch(`${API_BASE}/barcode/${upc}`, { method: 'POST' });
  if (!resp.ok) throw new Error(`Barcode lookup failed: ${resp.status}`);
  return resp.json();
}
```

- [ ] **Step 2: Create Toast component**

Create `frontend/src/components/Toast.tsx`:

```typescript
import { useEffect, useState } from 'react';

interface ToastProps {
  message: string;
  visible: boolean;
  onDone: () => void;
  duration?: number;
}

export function Toast({ message, visible, onDone, duration = 2000 }: ToastProps) {
  useEffect(() => {
    if (visible) {
      const timer = setTimeout(onDone, duration);
      return () => clearTimeout(timer);
    }
  }, [visible, onDone, duration]);

  if (!visible) return null;

  return (
    <div style={{
      position: 'fixed',
      bottom: 80,
      left: '50%',
      transform: 'translateX(-50%)',
      background: '#333',
      color: '#fff',
      padding: '12px 24px',
      borderRadius: 8,
      zIndex: 1000,
      fontSize: 14,
    }}>
      {message}
    </div>
  );
}
```

- [ ] **Step 3: Create TabBar component**

Create `frontend/src/components/TabBar.tsx`:

```typescript
interface Tab {
  key: string;
  label: string;
  icon: string;
}

const TABS: Tab[] = [
  { key: 'meal', label: 'Meal', icon: '\u{1F37D}' },
  { key: 'flare', label: 'Flare', icon: '\u{1F534}' },
  { key: 'meds', label: 'Meds', icon: '\u{1F48A}' },
  { key: 'note', label: 'Note', icon: '\u{1F4DD}' },
  { key: 'analysis', label: 'Analysis', icon: '\u{1F4CA}' },
];

interface TabBarProps {
  active: string;
  onSelect: (key: string) => void;
}

export function TabBar({ active, onSelect }: TabBarProps) {
  return (
    <nav style={{
      position: 'fixed',
      bottom: 0,
      left: 0,
      right: 0,
      display: 'flex',
      justifyContent: 'space-around',
      background: '#fff',
      borderTop: '1px solid #e0e0e0',
      paddingBottom: 'env(safe-area-inset-bottom)',
      zIndex: 100,
    }}>
      {TABS.map(tab => (
        <button
          key={tab.key}
          onClick={() => onSelect(tab.key)}
          style={{
            flex: 1,
            border: 'none',
            background: 'none',
            padding: '8px 0',
            cursor: 'pointer',
            opacity: active === tab.key ? 1 : 0.5,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            fontSize: 12,
          }}
        >
          <span style={{ fontSize: 24 }}>{tab.icon}</span>
          <span>{tab.label}</span>
        </button>
      ))}
    </nav>
  );
}
```

- [ ] **Step 4: Create MealLog page**

Create `frontend/src/pages/MealLog.tsx`:

```typescript
import { useState, useRef } from 'react';
import { createLogEntry } from '../api';
import { Toast } from '../components/Toast';

export function MealLog() {
  const [text, setText] = useState('');
  const [photo, setPhoto] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState(false);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const handleSubmit = async () => {
    if (!text.trim() && !photo) return;
    setSubmitting(true);
    try {
      // TODO: handle photo upload in Task 8 (image logging)
      await createLogEntry({
        timestamp: new Date().toISOString(),
        type: 'meal',
        raw_input: text.trim(),
      });
      setText('');
      setPhoto(null);
      if (fileRef.current) fileRef.current.value = '';
      setToast(true);
      inputRef.current?.focus();
    } catch (e) {
      alert('Failed to save entry');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div style={{ padding: 16, paddingBottom: 80 }}>
      <h2>Log Meal</h2>
      <textarea
        ref={inputRef}
        autoFocus
        value={text}
        onChange={e => setText(e.target.value)}
        placeholder="What did you eat? e.g. rice, chicken stir fry with soy sauce"
        rows={4}
        style={{ width: '100%', fontSize: 16, padding: 12, borderRadius: 8, border: '1px solid #ccc', boxSizing: 'border-box' }}
      />
      <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
        <input
          ref={fileRef}
          type="file"
          accept="image/*"
          capture="environment"
          onChange={e => setPhoto(e.target.files?.[0] || null)}
          style={{ flex: 1 }}
        />
      </div>
      <button
        onClick={handleSubmit}
        disabled={submitting || (!text.trim() && !photo)}
        style={{
          marginTop: 16,
          width: '100%',
          padding: 14,
          fontSize: 16,
          fontWeight: 'bold',
          borderRadius: 8,
          border: 'none',
          background: '#4a90d9',
          color: '#fff',
          cursor: 'pointer',
          opacity: submitting ? 0.6 : 1,
        }}
      >
        {submitting ? 'Saving...' : 'Submit'}
      </button>
      <Toast message="Meal logged!" visible={toast} onDone={() => setToast(false)} />
    </div>
  );
}
```

- [ ] **Step 5: Create FlareLog page**

Create `frontend/src/pages/FlareLog.tsx`:

```typescript
import { useState, useRef } from 'react';
import { createLogEntry } from '../api';
import { Toast } from '../components/Toast';

export function FlareLog() {
  const [severity, setSeverity] = useState(5);
  const [notes, setNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const handleSubmit = async () => {
    setSubmitting(true);
    try {
      await createLogEntry({
        timestamp: new Date().toISOString(),
        type: 'flare',
        severity,
        notes: notes.trim() || undefined,
      });
      setSeverity(5);
      setNotes('');
      if (fileRef.current) fileRef.current.value = '';
      setToast(true);
    } catch (e) {
      alert('Failed to save entry');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div style={{ padding: 16, paddingBottom: 80 }}>
      <h2>Log Flare</h2>
      <label style={{ display: 'block', marginBottom: 8, fontSize: 16 }}>
        Severity: <strong>{severity}</strong> / 10
      </label>
      <input
        type="range"
        min={1}
        max={10}
        value={severity}
        onChange={e => setSeverity(Number(e.target.value))}
        style={{ width: '100%' }}
      />
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: '#888' }}>
        <span>Mild</span><span>Severe</span>
      </div>
      <textarea
        value={notes}
        onChange={e => setNotes(e.target.value)}
        placeholder="Optional notes (e.g. location, appearance)"
        rows={3}
        style={{ width: '100%', fontSize: 16, padding: 12, borderRadius: 8, border: '1px solid #ccc', marginTop: 16, boxSizing: 'border-box' }}
      />
      <input
        ref={fileRef}
        type="file"
        accept="image/*"
        capture="environment"
        multiple
        style={{ marginTop: 12 }}
      />
      <button
        onClick={handleSubmit}
        disabled={submitting}
        style={{
          marginTop: 16, width: '100%', padding: 14, fontSize: 16, fontWeight: 'bold',
          borderRadius: 8, border: 'none', background: '#d94a4a', color: '#fff', cursor: 'pointer',
          opacity: submitting ? 0.6 : 1,
        }}
      >
        {submitting ? 'Saving...' : 'Submit'}
      </button>
      <Toast message="Flare logged!" visible={toast} onDone={() => setToast(false)} />
    </div>
  );
}
```

- [ ] **Step 6: Create MedsLog page**

Create `frontend/src/pages/MedsLog.tsx`:

```typescript
import { useState } from 'react';
import { createLogEntry } from '../api';
import { Toast } from '../components/Toast';

export function MedsLog() {
  const [name, setName] = useState('');
  const [dose, setDose] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState(false);

  const handleSubmit = async () => {
    if (!name.trim()) return;
    setSubmitting(true);
    try {
      await createLogEntry({
        timestamp: new Date().toISOString(),
        type: 'medication',
        medication_name: name.trim(),
        medication_dose: dose.trim() || undefined,
      });
      setName('');
      setDose('');
      setToast(true);
    } catch (e) {
      alert('Failed to save entry');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div style={{ padding: 16, paddingBottom: 80 }}>
      <h2>Log Medication</h2>
      <input
        autoFocus
        value={name}
        onChange={e => setName(e.target.value)}
        placeholder="Drug name"
        style={{ width: '100%', fontSize: 16, padding: 12, borderRadius: 8, border: '1px solid #ccc', boxSizing: 'border-box' }}
      />
      <input
        value={dose}
        onChange={e => setDose(e.target.value)}
        placeholder="Dose (optional)"
        style={{ width: '100%', fontSize: 16, padding: 12, borderRadius: 8, border: '1px solid #ccc', marginTop: 12, boxSizing: 'border-box' }}
      />
      <button
        onClick={handleSubmit}
        disabled={submitting || !name.trim()}
        style={{
          marginTop: 16, width: '100%', padding: 14, fontSize: 16, fontWeight: 'bold',
          borderRadius: 8, border: 'none', background: '#9b59b6', color: '#fff', cursor: 'pointer',
          opacity: submitting ? 0.6 : 1,
        }}
      >
        {submitting ? 'Saving...' : 'Submit'}
      </button>
      <Toast message="Medication logged!" visible={toast} onDone={() => setToast(false)} />
    </div>
  );
}
```

- [ ] **Step 7: Create NoteLog page**

Create `frontend/src/pages/NoteLog.tsx`:

```typescript
import { useState, useRef } from 'react';
import { createLogEntry } from '../api';
import { Toast } from '../components/Toast';

export function NoteLog() {
  const [text, setText] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState(false);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const handleSubmit = async () => {
    if (!text.trim()) return;
    setSubmitting(true);
    try {
      await createLogEntry({
        timestamp: new Date().toISOString(),
        type: 'note',
        notes: text.trim(),
      });
      setText('');
      setToast(true);
      inputRef.current?.focus();
    } catch (e) {
      alert('Failed to save entry');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div style={{ padding: 16, paddingBottom: 80 }}>
      <h2>Log Note</h2>
      <textarea
        ref={inputRef}
        autoFocus
        value={text}
        onChange={e => setText(e.target.value)}
        placeholder="Any context for the tracker (e.g. ate out at Thai restaurant, skin dry but not flaring)"
        rows={5}
        style={{ width: '100%', fontSize: 16, padding: 12, borderRadius: 8, border: '1px solid #ccc', boxSizing: 'border-box' }}
      />
      <button
        onClick={handleSubmit}
        disabled={submitting || !text.trim()}
        style={{
          marginTop: 16, width: '100%', padding: 14, fontSize: 16, fontWeight: 'bold',
          borderRadius: 8, border: 'none', background: '#2ecc71', color: '#fff', cursor: 'pointer',
          opacity: submitting ? 0.6 : 1,
        }}
      >
        {submitting ? 'Saving...' : 'Submit'}
      </button>
      <Toast message="Note logged!" visible={toast} onDone={() => setToast(false)} />
    </div>
  );
}
```

- [ ] **Step 8: Create Analysis page (placeholder)**

Create `frontend/src/pages/Analysis.tsx`:

```typescript
import { useState } from 'react';
import { startAnalysis, getAnalysisResult, AnalysisResult } from '../api';

export function Analysis() {
  const [useLikely, setUseLikely] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState('');

  const runAnalysis = async () => {
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const { job_id } = await startAnalysis(useLikely);
      // Poll for result
      let attempts = 0;
      while (attempts < 30) {
        const res = await getAnalysisResult(job_id);
        if (res.status === 'complete') {
          setResult(res);
          break;
        } else if (res.status === 'failed') {
          setError('Analysis failed. Please try again.');
          break;
        }
        await new Promise(r => setTimeout(r, 1000));
        attempts++;
      }
      if (attempts >= 30) setError('Analysis timed out.');
    } catch (e) {
      setError('Failed to run analysis.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ padding: 16, paddingBottom: 80 }}>
      <h2>Analysis</h2>
      <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
        <input
          type="checkbox"
          checked={useLikely}
          onChange={e => setUseLikely(e.target.checked)}
        />
        Include "likely" ingredients
      </label>
      <button
        onClick={runAnalysis}
        disabled={loading}
        style={{
          width: '100%', padding: 14, fontSize: 16, fontWeight: 'bold',
          borderRadius: 8, border: 'none', background: '#4a90d9', color: '#fff', cursor: 'pointer',
          opacity: loading ? 0.6 : 1,
        }}
      >
        {loading ? 'Analysing...' : 'Run Analysis'}
      </button>

      {error && <p style={{ color: 'red', marginTop: 16 }}>{error}</p>}

      {result?.warning && (
        <div style={{
          background: '#fff3cd', border: '1px solid #ffc107', borderRadius: 8,
          padding: 12, marginTop: 16, fontSize: 14,
        }}>
          {result.warning}
        </div>
      )}

      {result?.stats && result.stats.length > 0 && (
        <div style={{ marginTop: 16, overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
            <thead>
              <tr style={{ borderBottom: '2px solid #333' }}>
                <th style={{ textAlign: 'left', padding: 8 }}>Ingredient</th>
                <th style={{ textAlign: 'right', padding: 8 }}>Lift</th>
                <th style={{ textAlign: 'right', padding: 8 }}>Flare Apps</th>
              </tr>
            </thead>
            <tbody>
              {result.stats.map((row, i) => (
                <tr key={i} style={{ borderBottom: '1px solid #eee' }}>
                  <td style={{ padding: 8 }}>{row.ingredient}</td>
                  <td style={{ padding: 8, textAlign: 'right' }}>{row.lift === Infinity ? '\u221E' : row.lift.toFixed(2)}</td>
                  <td style={{ padding: 8, textAlign: 'right' }}>{row.flare_appearances}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {result?.summary && (
        <div style={{ marginTop: 16, padding: 16, background: '#f5f5f5', borderRadius: 8, lineHeight: 1.6 }}>
          <strong>Summary</strong>
          <p style={{ whiteSpace: 'pre-wrap' }}>{result.summary}</p>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 9: Wire up App.tsx with TabBar and pages**

Replace `frontend/src/App.tsx`:

```typescript
import { useState } from 'react';
import { TabBar } from './components/TabBar';
import { MealLog } from './pages/MealLog';
import { FlareLog } from './pages/FlareLog';
import { MedsLog } from './pages/MedsLog';
import { NoteLog } from './pages/NoteLog';
import { Analysis } from './pages/Analysis';

function App() {
  const [tab, setTab] = useState('meal');

  return (
    <div style={{ minHeight: '100vh', background: '#fafafa' }}>
      {tab === 'meal' && <MealLog />}
      {tab === 'flare' && <FlareLog />}
      {tab === 'meds' && <MedsLog />}
      {tab === 'note' && <NoteLog />}
      {tab === 'analysis' && <Analysis />}
      <TabBar active={tab} onSelect={setTab} />
    </div>
  );
}

export default App;
```

- [ ] **Step 10: Clean up default Vite files**

Remove default `frontend/src/App.css`, `frontend/src/index.css` content (keep files but empty or minimal). Remove logo imports from `main.tsx`. Keep `main.tsx` simple:

```typescript
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
```

Add minimal global styles in `frontend/src/index.css`:

```css
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  -webkit-font-smoothing: antialiased;
}
```

- [ ] **Step 11: Verify frontend builds**

```bash
cd frontend && npm run build
```

Expected: Build succeeds, output in `backend/static/`.

- [ ] **Step 12: Commit**

```bash
git add frontend/src/ frontend/public/
git commit -m "feat: PWA frontend with all logging pages and analysis UI"
```

---

## Task 6: Correlation Algorithm

**Files:**
- Create: `backend/analysis.py`
- Create: `backend/tests/test_analysis.py`

- [ ] **Step 1: Write failing tests for correlation algorithm**

Create `backend/tests/test_analysis.py`:

```python
import pytest
import json
from unittest.mock import MagicMock, patch


def make_db_with_data(entries, aliases=None):
    """Helper to create a mock db with test data."""
    from db import Database
    import tempfile
    from pathlib import Path

    tmp = Path(tempfile.mkdtemp()) / "test.db"
    db = Database(tmp)
    db.init()

    for e in entries:
        entry_id = db.insert_log_entry(
            timestamp=e["timestamp"],
            entry_type=e["type"],
            raw_input=e.get("raw_input"),
            severity=e.get("severity"),
            medication_name=e.get("medication_name"),
            notes=e.get("notes"),
        )
        if "ingredients" in e:
            db.update_parse_result(
                entry_id,
                status="parsed",
                ingredients=json.dumps(e["ingredients"]),
            )

    for alias in (aliases or []):
        db.add_alias(alias["variant"], alias["canonical"])

    return db


class TestCorrelation:
    def test_basic_correlation(self):
        from analysis import compute_correlation

        db = make_db_with_data([
            # Meal with dairy — 12h before flare
            {"timestamp": "2026-03-20T08:00:00Z", "type": "meal", "raw_input": "milk and cereal",
             "ingredients": {"confirmed": ["milk", "cereal"], "likely": [], "source": "text"}},
            # Flare
            {"timestamp": "2026-03-20T20:00:00Z", "type": "flare", "severity": 7},
            # Meal without dairy — no flare follows
            {"timestamp": "2026-03-21T08:00:00Z", "type": "meal", "raw_input": "rice and chicken",
             "ingredients": {"confirmed": ["rice", "chicken"], "likely": [], "source": "text"}},
            # Another meal with dairy — before another flare
            {"timestamp": "2026-03-22T08:00:00Z", "type": "meal", "raw_input": "cheese sandwich",
             "ingredients": {"confirmed": ["cheese", "bread"], "likely": [], "source": "text"}},
            # Flare
            {"timestamp": "2026-03-22T20:00:00Z", "type": "flare", "severity": 6},
        ])

        result = compute_correlation(db, use_likely=False)

        # milk and cheese should not appear (only 1 flare each, need >=2)
        # But cereal appears in 1 flare window, bread in 1 flare window
        # None meet the >=2 threshold with these 2 flares and different ingredients
        # Let's just verify structure
        assert "stats" in result
        assert "flare_count" in result

    def test_ingredient_appearing_in_multiple_flares(self):
        from analysis import compute_correlation

        db = make_db_with_data([
            {"timestamp": "2026-03-20T08:00:00Z", "type": "meal", "raw_input": "milk",
             "ingredients": {"confirmed": ["milk", "cereal"], "likely": [], "source": "text"}},
            {"timestamp": "2026-03-20T20:00:00Z", "type": "flare", "severity": 7},
            {"timestamp": "2026-03-22T08:00:00Z", "type": "meal", "raw_input": "milk",
             "ingredients": {"confirmed": ["milk", "rice"], "likely": [], "source": "text"}},
            {"timestamp": "2026-03-22T20:00:00Z", "type": "flare", "severity": 6},
            # Baseline meal (no flare follows)
            {"timestamp": "2026-03-24T08:00:00Z", "type": "meal", "raw_input": "chicken",
             "ingredients": {"confirmed": ["chicken", "rice"], "likely": [], "source": "text"}},
        ])

        result = compute_correlation(db, use_likely=False)
        stats = result["stats"]
        milk_stat = next((s for s in stats if s["ingredient"] == "milk"), None)
        assert milk_stat is not None
        assert milk_stat["flare_appearances"] >= 2
        assert milk_stat["lift"] > 1.0

    def test_alias_resolution(self):
        from analysis import compute_correlation

        db = make_db_with_data(
            entries=[
                {"timestamp": "2026-03-20T08:00:00Z", "type": "meal", "raw_input": "tamari rice",
                 "ingredients": {"confirmed": ["tamari", "rice"], "likely": [], "source": "text"}},
                {"timestamp": "2026-03-20T20:00:00Z", "type": "flare", "severity": 7},
                {"timestamp": "2026-03-22T08:00:00Z", "type": "meal", "raw_input": "soy sauce noodles",
                 "ingredients": {"confirmed": ["soy sauce", "noodles"], "likely": [], "source": "text"}},
                {"timestamp": "2026-03-22T20:00:00Z", "type": "flare", "severity": 6},
                {"timestamp": "2026-03-24T08:00:00Z", "type": "meal", "raw_input": "plain rice",
                 "ingredients": {"confirmed": ["rice"], "likely": [], "source": "text"}},
            ],
            aliases=[{"variant": "tamari", "canonical": "soy sauce"}],
        )

        result = compute_correlation(db, use_likely=False)
        stats = result["stats"]
        soy_stat = next((s for s in stats if s["ingredient"] == "soy sauce"), None)
        assert soy_stat is not None
        assert soy_stat["flare_appearances"] == 2

    def test_medication_confounding(self):
        from analysis import compute_correlation

        db = make_db_with_data([
            {"timestamp": "2026-03-20T08:00:00Z", "type": "meal", "raw_input": "milk",
             "ingredients": {"confirmed": ["milk"], "likely": [], "source": "text"}},
            {"timestamp": "2026-03-20T14:00:00Z", "type": "medication", "medication_name": "cetirizine"},
            {"timestamp": "2026-03-20T20:00:00Z", "type": "flare", "severity": 7},
            {"timestamp": "2026-03-22T08:00:00Z", "type": "meal", "raw_input": "milk",
             "ingredients": {"confirmed": ["milk"], "likely": [], "source": "text"}},
            {"timestamp": "2026-03-22T20:00:00Z", "type": "flare", "severity": 6},
        ])

        result = compute_correlation(db, use_likely=False)
        stats = result["stats"]
        milk_stat = next((s for s in stats if s["ingredient"] == "milk"), None)
        assert milk_stat is not None
        # First flare should be flagged as confounded
        assert milk_stat["confounded"] >= 1

    def test_low_flare_warning(self):
        from analysis import compute_correlation

        db = make_db_with_data([
            {"timestamp": "2026-03-20T08:00:00Z", "type": "meal", "raw_input": "rice",
             "ingredients": {"confirmed": ["rice"], "likely": [], "source": "text"}},
            {"timestamp": "2026-03-20T20:00:00Z", "type": "flare", "severity": 5},
        ])

        result = compute_correlation(db, use_likely=False)
        assert result["warning"] is not None
        assert "not enough" in result["warning"].lower() or "not be meaningful" in result["warning"].lower()

    def test_use_likely_flag(self):
        from analysis import compute_correlation

        db = make_db_with_data([
            {"timestamp": "2026-03-20T08:00:00Z", "type": "meal", "raw_input": "stir fry",
             "ingredients": {"confirmed": ["rice"], "likely": ["soy sauce"], "source": "text"}},
            {"timestamp": "2026-03-20T20:00:00Z", "type": "flare", "severity": 7},
            {"timestamp": "2026-03-22T08:00:00Z", "type": "meal", "raw_input": "stir fry",
             "ingredients": {"confirmed": ["rice"], "likely": ["soy sauce"], "source": "text"}},
            {"timestamp": "2026-03-22T20:00:00Z", "type": "flare", "severity": 6},
            {"timestamp": "2026-03-24T08:00:00Z", "type": "meal", "raw_input": "plain rice",
             "ingredients": {"confirmed": ["rice"], "likely": [], "source": "text"}},
        ])

        result_without = compute_correlation(db, use_likely=False)
        result_with = compute_correlation(db, use_likely=True)

        # With likely=True, soy sauce should appear in stats
        soy_without = next((s for s in result_without["stats"] if s["ingredient"] == "soy sauce"), None)
        soy_with = next((s for s in result_with["stats"] if s["ingredient"] == "soy sauce"), None)

        assert soy_without is None  # not included when likely=False
        assert soy_with is not None  # included when likely=True
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_analysis.py -v
```

Expected: ImportError — `analysis` module does not exist.

- [ ] **Step 3: Implement analysis.py**

```python
import json
from datetime import datetime, timedelta, timezone
from typing import Optional

from config import (
    FLARE_WINDOW_HOURS,
    MEDICATION_CONFOUND_HOURS,
    MIN_FLARE_APPEARANCES,
    LOW_FLARE_WARNING_THRESHOLD,
)


def _parse_ts(ts: str) -> datetime:
    """Parse ISO 8601 timestamp to datetime."""
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def compute_correlation(db, use_likely: bool = False) -> dict:
    """
    Compute ingredient-flare correlations.

    Returns dict with: stats (list), flare_count (int), warning (str|None)
    """
    all_entries = db.list_log_entries()
    meals = [e for e in all_entries if e["type"] == "meal" and e["parse_status"] == "parsed"]
    flares = [e for e in all_entries if e["type"] == "flare"]
    medications = [e for e in all_entries if e["type"] == "medication"]

    flare_count = len(flares)
    warning = None
    if flare_count < LOW_FLARE_WARNING_THRESHOLD:
        warning = "Not enough data yet — results may not be meaningful. Keep logging!"

    # Extract ingredients from a meal entry
    def get_ingredients(meal: dict) -> list[str]:
        if not meal.get("parsed_ingredients"):
            return []
        data = json.loads(meal["parsed_ingredients"])
        ingredients = [i.lower() for i in data.get("confirmed", [])]
        if use_likely:
            ingredients += [i.lower() for i in data.get("likely", [])]
        # Resolve aliases
        return [db.resolve_alias(i) for i in ingredients]

    min_hours, max_hours = FLARE_WINDOW_HOURS

    # For each flare, find meals in the pre-flare window
    flare_ingredients: dict[int, set[str]] = {}  # flare_index -> set of ingredients
    meals_in_any_flare_window: set[int] = set()  # meal entry IDs in flare windows
    confounded_flares: set[int] = set()

    for fi, flare in enumerate(flares):
        flare_ts = _parse_ts(flare["timestamp"])
        window_start = flare_ts - timedelta(hours=max_hours)
        window_end = flare_ts - timedelta(hours=min_hours)

        # Check medication confounding
        for med in medications:
            med_ts = _parse_ts(med["timestamp"])
            if abs((med_ts - flare_ts).total_seconds()) <= MEDICATION_CONFOUND_HOURS * 3600:
                confounded_flares.add(fi)
                break

        flare_ings: set[str] = set()
        for meal in meals:
            meal_ts = _parse_ts(meal["timestamp"])
            if window_start <= meal_ts <= window_end:
                meals_in_any_flare_window.add(meal["id"])
                flare_ings.update(get_ingredients(meal))
        flare_ingredients[fi] = flare_ings

    # Baseline: meals NOT in any flare window
    baseline_ingredients: list[str] = []
    for meal in meals:
        if meal["id"] not in meals_in_any_flare_window:
            baseline_ingredients.extend(get_ingredients(meal))

    # Flare window ingredients (flat list for frequency)
    flare_ing_list: list[str] = []
    for ings in flare_ingredients.values():
        flare_ing_list.extend(ings)

    # Compute frequencies
    total_flare_ings = len(flare_ing_list) or 1
    total_baseline_ings = len(baseline_ingredients) or 1

    flare_freq: dict[str, float] = {}
    baseline_freq: dict[str, float] = {}

    for ing in flare_ing_list:
        flare_freq[ing] = flare_freq.get(ing, 0) + 1
    for ing in baseline_ingredients:
        baseline_freq[ing] = baseline_freq.get(ing, 0) + 1

    # Normalize
    for k in flare_freq:
        flare_freq[k] /= total_flare_ings
    for k in baseline_freq:
        baseline_freq[k] /= total_baseline_ings

    # Per ingredient stats
    all_ingredients = set(flare_freq.keys())
    stats = []

    for ing in all_ingredients:
        ff = flare_freq.get(ing, 0)
        bf = baseline_freq.get(ing, 0)
        lift = ff / bf if bf > 0 else float("inf")
        flare_apps = sum(1 for fi, ings in flare_ingredients.items() if ing in ings)
        confounded = sum(1 for fi, ings in flare_ingredients.items() if ing in ings and fi in confounded_flares)

        if flare_apps >= MIN_FLARE_APPEARANCES:
            stats.append({
                "ingredient": ing,
                "lift": lift,
                "flare_freq": round(ff, 4),
                "baseline_freq": round(bf, 4),
                "flare_appearances": flare_apps,
                "confounded": confounded,
            })

    stats.sort(key=lambda x: x["lift"], reverse=True)

    return {
        "stats": stats,
        "flare_count": flare_count,
        "warning": warning,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && python -m pytest tests/test_analysis.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/analysis.py backend/tests/test_analysis.py
git commit -m "feat: correlation algorithm for ingredient-flare analysis"
```

---

## Task 7: Analysis Endpoint (Async Job)

**Files:**
- Modify: `backend/main.py`
- Create: `backend/tests/test_analysis_endpoint.py`

- [ ] **Step 1: Write failing tests for analysis endpoints**

Create `backend/tests/test_analysis_endpoint.py`:

```python
import pytest
import json
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


@pytest.fixture
def client_with_data(tmp_path):
    import config
    config.DB_PATH = tmp_path / "test.db"
    config.DATA_DIR = tmp_path
    config.IMAGES_DIR = tmp_path / "images"

    from main import app, get_db
    from db import Database

    db = Database(config.DB_PATH)
    db.init()

    # Seed with enough data for analysis
    for day in range(1, 15):
        ts = f"2026-03-{day:02d}T08:00:00Z"
        entry_id = db.insert_log_entry(timestamp=ts, entry_type="meal", raw_input="rice and chicken")
        db.update_parse_result(entry_id, "parsed",
            json.dumps({"confirmed": ["rice", "chicken"], "likely": ["soy sauce"], "source": "text"}))

    # Add some meals with milk before flares
    for day in [5, 10]:
        ts = f"2026-03-{day:02d}T12:00:00Z"
        entry_id = db.insert_log_entry(timestamp=ts, entry_type="meal", raw_input="milk and cereal")
        db.update_parse_result(entry_id, "parsed",
            json.dumps({"confirmed": ["milk", "cereal"], "likely": [], "source": "text"}))
        flare_ts = f"2026-03-{day:02d}T22:00:00Z"
        db.insert_log_entry(timestamp=flare_ts, entry_type="flare", severity=7)

    def override_get_db():
        return db

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestAnalyseEndpoint:
    def test_start_analysis(self, client_with_data):
        resp = client_with_data.post("/api/analyse", json={"use_likely": False})
        assert resp.status_code == 200
        data = resp.json()
        assert "job_id" in data

    @patch("main._get_analysis_summary", return_value="Test summary: milk appears correlated with flares.")
    def test_get_analysis_result(self, mock_summary, client_with_data):
        # Start analysis (Claude summary is mocked)
        resp = client_with_data.post("/api/analyse", json={"use_likely": False})
        job_id = resp.json()["job_id"]

        # Poll for result
        import time
        for _ in range(10):
            resp = client_with_data.get(f"/api/analyse/{job_id}")
            assert resp.status_code == 200
            data = resp.json()
            if data["status"] == "complete":
                assert "stats" in data
                assert "summary" in data
                assert "milk" in data["summary"].lower()
                return
            time.sleep(0.2)

        # If we get here, check status
        assert data["status"] in ("complete", "running")

    def test_nonexistent_job_returns_404(self, client_with_data):
        resp = client_with_data.get("/api/analyse/nonexistent")
        assert resp.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_analysis_endpoint.py -v
```

Expected: FAIL — `/api/analyse` endpoint does not exist.

- [ ] **Step 3: Add analysis endpoints to main.py**

Add to `backend/main.py`:

```python
import uuid
from threading import Thread

# In-memory job storage
_analysis_jobs: dict[str, dict] = {}


class AnalyseRequest(BaseModel):
    use_likely: bool = False


@app.post("/api/analyse")
def start_analysis(req: AnalyseRequest, db: Database = Depends(get_db)):
    job_id = str(uuid.uuid4())
    _analysis_jobs[job_id] = {"status": "running"}

    def run_analysis():
        try:
            from analysis import compute_correlation
            result = compute_correlation(db, use_likely=req.use_likely)

            # Get Claude summary
            summary = _get_analysis_summary(result)
            result["summary"] = summary
            result["status"] = "complete"
            _analysis_jobs[job_id] = result
        except Exception as e:
            _analysis_jobs[job_id] = {"status": "failed", "error": str(e)}

    Thread(target=run_analysis, daemon=True).start()
    return {"job_id": job_id}


@app.get("/api/analyse/{job_id}")
def get_analysis(job_id: str):
    if job_id not in _analysis_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return _analysis_jobs[job_id]


def _get_analysis_summary(result: dict) -> str:
    """Get Claude summary of analysis results. Falls back to empty string on error."""
    try:
        from parsing import get_client
        from prompts import ANALYSIS_SUMMARY_PROMPT
        from config import CLAUDE_MODEL

        stats_table = json.dumps(result["stats"], indent=2)
        warnings = result.get("warning", "")

        response = get_client().messages.create(
            model=CLAUDE_MODEL,
            max_tokens=512,
            messages=[{
                "role": "user",
                "content": ANALYSIS_SUMMARY_PROMPT.format(
                    stats_table=stats_table, warnings=warnings
                ),
            }],
        )
        return response.content[0].text
    except Exception as e:
        return f"(Summary unavailable: {e})"
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && python -m pytest tests/test_analysis_endpoint.py -v
```

Expected: All tests PASS (summary will use fallback since no API key in tests).

- [ ] **Step 5: Run all backend tests**

```bash
cd backend && python -m pytest tests/ -v
```

Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/main.py backend/tests/test_analysis_endpoint.py
git commit -m "feat: async analysis endpoint with job polling"
```

---

## Task 8: Web Push Notifications

**Files:**
- Create: `backend/notifications.py`
- Create: `backend/tests/test_notifications.py`
- Modify: `backend/main.py` (start scheduler on startup)

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_notifications.py`:

```python
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta


class TestShouldNotify:
    def test_should_notify_when_no_recent_meal(self):
        from notifications import should_send_notification

        mock_db = MagicMock()
        mock_db.list_log_entries.return_value = []

        assert should_send_notification(mock_db) is True

    def test_should_not_notify_when_recent_meal(self):
        from notifications import should_send_notification

        mock_db = MagicMock()
        recent = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        mock_db.list_log_entries.return_value = [
            {"timestamp": recent, "type": "meal"},
        ]

        assert should_send_notification(mock_db) is False


class TestSendNotifications:
    def test_send_to_all_subscribers(self):
        from notifications import send_meal_reminder

        mock_db = MagicMock()
        mock_db.list_log_entries.return_value = []
        mock_db.list_push_subscriptions.return_value = [
            {"endpoint": "https://push.example.com/1", "keys_json": '{"p256dh":"k1","auth":"a1"}'},
            {"endpoint": "https://push.example.com/2", "keys_json": '{"p256dh":"k2","auth":"a2"}'},
        ]

        with patch("notifications.webpush") as mock_push:
            send_meal_reminder(mock_db, "Time to log lunch")
            assert mock_push.call_count == 2
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_notifications.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement notifications.py**

```python
import json
import logging
import os
from datetime import datetime, timedelta, timezone

from pywebpush import webpush, WebPushException

from config import NOTIFICATION_SKIP_WINDOW_HOURS

logger = logging.getLogger(__name__)

VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY", "")
VAPID_CLAIMS = {"sub": "mailto:admin@localhost"}


def should_send_notification(db) -> bool:
    """Check if a meal was logged in the past NOTIFICATION_SKIP_WINDOW_HOURS hours."""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=NOTIFICATION_SKIP_WINDOW_HOURS)).isoformat()
    recent_meals = db.list_log_entries(entry_type="meal", from_date=cutoff)
    return len(recent_meals) == 0


def send_meal_reminder(db, message: str) -> None:
    """Send push notification to all subscribers if no recent meal."""
    if not should_send_notification(db):
        logger.info("Skipping notification — recent meal logged")
        return

    subscriptions = db.list_push_subscriptions()
    for sub in subscriptions:
        keys = json.loads(sub["keys_json"])
        try:
            webpush(
                subscription_info={
                    "endpoint": sub["endpoint"],
                    "keys": keys,
                },
                data=json.dumps({"title": "Eczema Tracker", "body": message}),
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims=VAPID_CLAIMS,
            )
        except WebPushException as e:
            logger.error(f"Push failed for {sub['endpoint']}: {e}")
        except Exception as e:
            logger.error(f"Unexpected push error: {e}")


def setup_scheduler(db) -> None:
    """Set up APScheduler for meal reminder notifications."""
    from apscheduler.schedulers.background import BackgroundScheduler
    from config import NOTIFICATION_TIMES_AEST

    scheduler = BackgroundScheduler()

    # AEST is UTC+10 (ignoring DST for simplicity — can refine later)
    aest_offset = 10

    for meal, time_str in NOTIFICATION_TIMES_AEST.items():
        hour, minute = map(int, time_str.split(":"))
        utc_hour = (hour - aest_offset) % 24

        scheduler.add_job(
            send_meal_reminder,
            "cron",
            hour=utc_hour,
            minute=minute,
            args=[db, f"Time to log {meal}"],
            id=f"reminder_{meal}",
        )

    scheduler.start()
    return scheduler
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && python -m pytest tests/test_notifications.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Wire scheduler into main.py startup**

Add to `main.py`:

```python
@app.on_event("startup")
def startup():
    db = get_db()
    from notifications import setup_scheduler
    setup_scheduler(db)
```

- [ ] **Step 6: Run all tests**

```bash
cd backend && python -m pytest tests/ -v
```

Expected: All tests PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/notifications.py backend/tests/test_notifications.py backend/main.py
git commit -m "feat: Web Push notifications with APScheduler meal reminders"
```

---

## Task 9: Barcode Scanning (Open Food Facts)

**Files:**
- Modify: `backend/main.py`
- Create: `backend/tests/test_barcode.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_barcode.py`:

```python
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock


@pytest.fixture
def client(tmp_path):
    import config
    config.DB_PATH = tmp_path / "test.db"
    config.DATA_DIR = tmp_path
    config.IMAGES_DIR = tmp_path / "images"

    from main import app, get_db
    from db import Database

    db = Database(config.DB_PATH)
    db.init()

    def override_get_db():
        return db

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestBarcodeEndpoint:
    @patch("main.httpx")
    def test_barcode_lookup_success(self, mock_httpx, client):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": 1,
            "product": {
                "ingredients_text": "wheat flour, sugar, palm oil, salt"
            }
        }
        mock_httpx.get.return_value = mock_response

        resp = client.post("/api/barcode/1234567890")
        assert resp.status_code == 200
        assert "wheat flour" in resp.json()["ingredients"]

    @patch("main.httpx")
    def test_barcode_not_found(self, mock_httpx, client):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": 0}
        mock_httpx.get.return_value = mock_response

        resp = client.post("/api/barcode/0000000000")
        assert resp.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_barcode.py -v
```

Expected: FAIL — endpoint does not exist.

- [ ] **Step 3: Add barcode endpoint to main.py**

Add to `backend/main.py`:

```python
import httpx

@app.post("/api/barcode/{upc}")
def barcode_lookup(upc: str):
    resp = httpx.get(f"https://world.openfoodfacts.org/api/v0/product/{upc}.json")
    data = resp.json()
    if data.get("status") != 1:
        raise HTTPException(status_code=404, detail="Product not found")
    ingredients = data.get("product", {}).get("ingredients_text", "")
    if not ingredients:
        raise HTTPException(status_code=404, detail="No ingredients listed for this product")
    return {"ingredients": ingredients}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && python -m pytest tests/test_barcode.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Run all tests**

```bash
cd backend && python -m pytest tests/ -v
```

Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/main.py backend/tests/test_barcode.py
git commit -m "feat: barcode scanning via Open Food Facts API"
```

---

## Task 10: Service Worker (Offline + Push Registration)

**Files:**
- Create: `frontend/public/service-worker.js`
- Modify: `frontend/src/main.tsx` (register SW)

- [ ] **Step 1: Create service worker**

Create `frontend/public/service-worker.js` (plain JS — lives in `public/` so Vite serves it at `/service-worker.js` without build):

```javascript
// Service Worker for Eczema Tracker PWA

const CACHE_NAME = 'eczema-tracker-v1';
const OFFLINE_QUEUE_STORE = 'offline-queue';

// Cache app shell on install
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll([
        '/',
        '/index.html',
      ]);
    })
  );
  self.skipWaiting();
});

// Clean old caches on activate
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// Network-first for API, cache-first for assets
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  if (url.pathname.startsWith('/api/')) {
    // For POST /api/log — queue if offline
    if (event.request.method === 'POST' && url.pathname === '/api/log') {
      event.respondWith(
        fetch(event.request.clone()).catch(async () => {
          const body = await event.request.json();
          await saveToOfflineQueue(body);
          return new Response(JSON.stringify({ id: -1, queued: true }), {
            headers: { 'Content-Type': 'application/json' },
          });
        })
      );
      return;
    }
    // Other API calls: network only
    return;
  }

  // App shell: cache-first
  event.respondWith(
    caches.match(event.request).then((cached) => {
      return cached || fetch(event.request);
    })
  );
});

// Handle push notifications
self.addEventListener('push', (event) => {
  const data = event.data?.json() || { title: 'Eczema Tracker', body: 'Time to log!' };
  event.waitUntil(
    self.registration.showNotification(data.title, {
      body: data.body,
      icon: '/icon-192.png',
    })
  );
});

// Click notification -> open app
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  event.waitUntil(self.clients.openWindow('/'));
});

// IndexedDB helpers for offline queue
function openDB() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open('eczema-offline', 1);
    request.onupgradeneeded = () => {
      request.result.createObjectStore(OFFLINE_QUEUE_STORE, { autoIncrement: true });
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function saveToOfflineQueue(entry) {
  const db = await openDB();
  const tx = db.transaction(OFFLINE_QUEUE_STORE, 'readwrite');
  tx.objectStore(OFFLINE_QUEUE_STORE).add(entry);
  return new Promise((resolve, reject) => {
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

async function replayOfflineQueue() {
  const db = await openDB();
  const tx = db.transaction(OFFLINE_QUEUE_STORE, 'readwrite');
  const store = tx.objectStore(OFFLINE_QUEUE_STORE);
  const entries = await new Promise((resolve, reject) => {
    const request = store.getAll();
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });

  for (const entry of entries) {
    try {
      await fetch('/api/log', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(entry),
      });
    } catch {
      return; // Still offline, stop replaying
    }
  }

  // Clear queue after successful replay
  const clearTx = db.transaction(OFFLINE_QUEUE_STORE, 'readwrite');
  clearTx.objectStore(OFFLINE_QUEUE_STORE).clear();
}

// Replay offline queue when coming back online
self.addEventListener('message', (event) => {
  if (event.data === 'replay-queue') {
    replayOfflineQueue();
  }
});
```

- [ ] **Step 2: Register service worker in main.tsx**

Update `frontend/src/main.tsx`:

```typescript
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)

// Register service worker
if ('serviceWorker' in navigator) {
  window.addEventListener('load', async () => {
    try {
      const registration = await navigator.serviceWorker.register('/service-worker.js');
      console.log('SW registered:', registration.scope);

      // Replay offline queue when coming back online
      window.addEventListener('online', () => {
        navigator.serviceWorker.controller?.postMessage('replay-queue');
      });
    } catch (err) {
      console.error('SW registration failed:', err);
    }
  });
}
```

- [ ] **Step 3: Verify frontend builds**

```bash
cd frontend && npm run build
```

Expected: Build succeeds.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/main.tsx frontend/public/service-worker.js
# Note: service-worker.js is plain JS in public/ — no build step needed
git commit -m "feat: service worker for offline support and push notifications"
```

---

## Task 11: Final Integration + Smoke Test

**Files:**
- Modify: `backend/main.py` (ensure static file serving works)

- [ ] **Step 1: Build frontend**

```bash
cd frontend && npm run build
```

- [ ] **Step 2: Start backend and verify serving**

```bash
cd backend && uvicorn main:app --host 0.0.0.0 --port 8000
```

Open browser to `http://localhost:8000` — should see the app with tab bar.

- [ ] **Step 3: Manual smoke test**

1. Log a meal entry (text field + submit)
2. Log a flare entry (severity slider + submit)
3. Log a medication entry
4. Log a note
5. Verify entries appear via `GET /api/logs` (browser or curl)
6. Verify toast appears and fields clear after submit

- [ ] **Step 4: Run all backend tests**

```bash
cd backend && python -m pytest tests/ -v
```

Expected: All tests PASS.

- [ ] **Step 5: Run frontend type check**

```bash
cd frontend && npx tsc --noEmit
```

Expected: No type errors.

- [ ] **Step 6: Commit any final fixes**

```bash
git add -A
git commit -m "feat: integration fixes and final smoke test"
```
