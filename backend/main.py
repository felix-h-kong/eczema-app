import json
import os
import uuid
from enum import Enum
from pathlib import Path
from threading import Thread
from typing import Optional

import httpx
from dotenv import load_dotenv

from fastapi import BackgroundTasks, FastAPI, Depends, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config import DB_PATH, STATIC_DIR

load_dotenv(Path(__file__).resolve().parent / ".env")
from db import Database

app = FastAPI()

_db: Optional[Database] = None
_analysis_jobs: dict[str, dict] = {}


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
def create_log_entry(entry: LogEntryCreate, background_tasks: BackgroundTasks, db: Database = Depends(get_db)):
    entry_id = db.insert_log_entry(
        timestamp=entry.timestamp,
        entry_type=entry.type.value,
        raw_input=entry.raw_input,
        severity=entry.severity,
        medication_name=entry.medication_name,
        medication_dose=entry.medication_dose,
        notes=entry.notes,
    )
    if entry.type == EntryType.meal and entry.raw_input:
        from parsing import process_pending_entry
        background_tasks.add_task(process_pending_entry, db, entry_id)
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
            # Sanitize non-finite floats so the result is JSON-serializable
            import math
            for row in result.get("stats", []):
                if isinstance(row.get("lift"), float) and not math.isfinite(row["lift"]):
                    row["lift"] = None
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
    """Get Claude summary. Falls back on error."""
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
                "content": ANALYSIS_SUMMARY_PROMPT.format(stats_table=stats_table, warnings=warnings),
            }],
        )
        return response.content[0].text
    except Exception as e:
        return f"(Summary unavailable: {e})"


@app.on_event("startup")
def startup():
    db = get_db()
    from notifications import setup_scheduler
    setup_scheduler(db)


@app.get("/api/push/vapid-key")
def get_vapid_key():
    key = os.environ.get("VAPID_PUBLIC_KEY", "")
    if not key:
        raise HTTPException(status_code=500, detail="VAPID public key not configured")
    return {"public_key": key}


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


# Serve static files (built frontend) — must be last
if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
