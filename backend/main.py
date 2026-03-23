import json
from enum import Enum
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config import DB_PATH, STATIC_DIR
from db import Database

app = FastAPI()

_db: Optional[Database] = None


def get_db() -> Database:
    global _db
    if _db is None:
        _db = Database(DB_PATH)
        _db.init()
    return _db


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
