import json
import os
import uuid
from enum import Enum
from pathlib import Path
from threading import Thread
from typing import Optional

import httpx
from dotenv import load_dotenv

from fastapi import BackgroundTasks, FastAPI, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config import CONFIG_DIR, DATA_DIR, DB_PATH, IMAGES_DIR, STATIC_DIR

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
    barcode_ingredients: Optional[str] = None


class LogEntryUpdate(BaseModel):
    timestamp: Optional[str] = None
    raw_input: Optional[str] = None
    severity: Optional[int] = None
    medication_name: Optional[str] = None
    medication_dose: Optional[str] = None
    notes: Optional[str] = None


class AliasCreate(BaseModel):
    variant: str
    canonical: str


class CompositionCreate(BaseModel):
    parent: str
    children: list[str]
    source: str = "manual"


class PushSubscribeRequest(BaseModel):
    endpoint: str
    keys: dict


class EnvironmentReading(BaseModel):
    timestamp: str
    temperature: float
    humidity: float


class EnvironmentSyncRequest(BaseModel):
    readings: list[EnvironmentReading]
    source: str = "govee_h5075"


class AirQualityReading(BaseModel):
    timestamp: str
    site_id: int
    site_name: str
    parameter: str = "PM2.5"
    value: Optional[float] = None
    unit: str = "µg/m³"
    category: Optional[str] = None


class AirQualitySyncRequest(BaseModel):
    readings: list[AirQualityReading]
    source: str = "nsw_dpie"


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
    if entry.type != EntryType.meal:
        db.update_log_entry(entry_id, parse_status=None)
    elif entry.barcode_ingredients:
        # Barcode gave us exact ingredients — store directly, skip Claude parsing
        ingredients = [i.strip() for i in entry.barcode_ingredients.split(",") if i.strip()]
        parsed = json.dumps({"confirmed": ingredients, "likely": [], "source": "barcode"})
        db.update_parse_result(entry_id, status="parsed", ingredients=parsed)
    else:
        # Text-only meal entries skip parsing — only photos and barcodes get parsed
        db.update_log_entry(entry_id, parse_status=None)
    return {"id": entry_id}


@app.get("/api/logs")
def list_logs(
    type: Optional[str] = Query(None),
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    db: Database = Depends(get_db),
):
    entries = db.list_log_entries(entry_type=type, from_date=from_date, to_date=to_date)
    for entry in entries:
        images = db.list_images(entry["id"])
        if images:
            entry["images"] = [
                f"/api/images/{Path(img['image_path']).name}" for img in images
            ]
    return entries


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


@app.get("/api/admin/aliases")
def get_aliases(db: Database = Depends(get_db)):
    return db.list_aliases()


@app.delete("/api/admin/aliases/{variant}")
def delete_alias(variant: str, db: Database = Depends(get_db)):
    db.delete_alias(variant)
    return {"ok": True}


@app.post("/api/admin/compositions", status_code=201)
def add_composition(comp: CompositionCreate, db: Database = Depends(get_db)):
    db.add_composition(comp.parent, comp.children, comp.source)
    return {"ok": True}


@app.get("/api/admin/compositions")
def get_compositions(db: Database = Depends(get_db)):
    return db.list_compositions()


@app.delete("/api/admin/compositions/{parent}")
def delete_composition(parent: str, db: Database = Depends(get_db)):
    db.delete_composition(parent)
    return {"ok": True}


@app.post("/api/push/test")
def push_test(db: Database = Depends(get_db)):
    from notifications import send_test_notification
    send_test_notification(db)
    return {"ok": True}


@app.post("/api/push/subscribe", status_code=201)
def push_subscribe(req: PushSubscribeRequest, db: Database = Depends(get_db)):
    db.add_push_subscription(
        endpoint=req.endpoint,
        keys_json=json.dumps(req.keys),
    )
    return {"ok": True}


@app.post("/api/environment", status_code=201)
def post_environment(req: EnvironmentSyncRequest, db: Database = Depends(get_db)):
    readings = [r.model_dump() for r in req.readings]
    inserted = db.insert_environment_readings(readings, source=req.source)
    return {"inserted": inserted, "total": len(readings)}


@app.get("/api/environment")
def get_environment(
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    db: Database = Depends(get_db),
):
    return db.list_environment_readings(from_date=from_date, to_date=to_date)


@app.post("/api/air-quality", status_code=201)
def post_air_quality(req: AirQualitySyncRequest, db: Database = Depends(get_db)):
    readings = [r.model_dump() for r in req.readings]
    inserted = db.insert_air_quality_readings(readings, source=req.source)
    return {"inserted": inserted, "total": len(readings)}


@app.get("/api/air-quality")
def get_air_quality(
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    site_id: Optional[int] = Query(None),
    db: Database = Depends(get_db),
):
    return db.list_air_quality_readings(
        from_date=from_date, to_date=to_date, site_id=site_id
    )


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


@app.post("/api/log/{entry_id}/image", status_code=201)
async def upload_image(
    entry_id: int,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Database = Depends(get_db),
):
    existing = db.get_log_entry(entry_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Entry not found")
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    ext = Path(file.filename or "image.jpg").suffix or ".jpg"
    filename = f"{entry_id}_{uuid.uuid4().hex[:8]}{ext}"
    filepath = IMAGES_DIR / filename
    content = await file.read()
    filepath.write_bytes(content)
    timestamp = existing["timestamp"]
    image_id = db.add_image(entry_id, str(filepath), timestamp)
    # If it's a meal entry, parse ingredients from image
    if existing["type"] == "meal":
        from parsing import process_image_entry
        background_tasks.add_task(process_image_entry, db, entry_id, str(filepath))
    return {"id": image_id, "path": f"/api/images/{filename}"}


@app.get("/api/images/{filename}")
def serve_image(filename: str):
    filepath = IMAGES_DIR / filename
    if not filepath.exists() or not filepath.resolve().parent == IMAGES_DIR.resolve():
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(filepath)


def _lookup_open_food_facts(upc: str) -> dict | None:
    """Try Open Food Facts. Returns {"ingredients": ..., "name": ...} or None.

    Prefers English ingredients (ingredients_text_en) when present, falling back
    to the product's primary-language ingredients_text. OFF wraps allergens in
    underscores (e.g. "_Soja_" = italicized in their UI); we strip those.
    """
    try:
        resp = httpx.get(
            f"https://world.openfoodfacts.org/api/v0/product/{upc}.json",
            timeout=5,
        )
        data = resp.json()
        if data.get("status") != 1:
            return None
        product = data.get("product", {})
        ingredients = product.get("ingredients_text_en") or product.get("ingredients_text", "")
        ingredients = ingredients.replace("_", "")
        name = product.get("product_name_en") or product.get("product_name", "")
        if not ingredients:
            return None
        return {"ingredients": ingredients, "name": name}
    except Exception:
        return None


def _lookup_upc_itemdb(upc: str) -> dict | None:
    """Try UPC Item DB (free, 100 lookups/day). Returns {"ingredients": ..., "name": ...} or None."""
    try:
        resp = httpx.get(
            f"https://api.upcitemdb.com/prod/trial/lookup?upc={upc}",
            timeout=5,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        items = data.get("items", [])
        if not items:
            return None
        item = items[0]
        name = item.get("title", "")
        # UPC Item DB doesn't always have ingredients — use description as fallback
        description = item.get("description", "")
        if not name:
            return None
        return {"ingredients": description, "name": name}
    except Exception:
        return None


def _cache_barcode_composition(db: Database, name: str, ingredients_text: str) -> None:
    """Store barcode-returned ingredients as a composition keyed by product name."""
    if not name or not ingredients_text:
        return
    children = [t.strip() for t in ingredients_text.split(",") if t.strip()]
    if not children:
        return
    db.add_composition(name, children, source="barcode")


@app.post("/api/barcode/{upc}")
def barcode_lookup(upc: str, db: Database = Depends(get_db)):
    # Try Open Food Facts first (best for ingredients), then UPC Item DB (better product coverage)
    result = _lookup_open_food_facts(upc)
    if result:
        _cache_barcode_composition(db, result.get("name", ""), result.get("ingredients", ""))
        return result

    result = _lookup_upc_itemdb(upc)
    if result and result["ingredients"]:
        _cache_barcode_composition(db, result.get("name", ""), result.get("ingredients", ""))
        return result
    if result and result["name"]:
        # Found the product but no ingredients — return name so user can add ingredients manually
        raise HTTPException(
            status_code=404,
            detail=f"Found '{result['name']}' but no ingredients listed. Try entering them manually.",
        )

    raise HTTPException(
        status_code=404,
        detail=f"Product not found for barcode {upc}. Try entering ingredients manually.",
    )


@app.post("/api/log/{entry_id}/reparse")
async def reparse_entry(
    entry_id: int,
    background_tasks: BackgroundTasks,
    db: Database = Depends(get_db),
):
    entry = db.get_log_entry(entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    if entry["type"] != "meal":
        raise HTTPException(status_code=400, detail="Only food entries can be parsed")
    images = db.list_images(entry_id)
    # Re-parse text if present
    if entry.get("raw_input"):
        from parsing import process_pending_entry
        db.update_log_entry(entry_id, parse_status="pending")
        background_tasks.add_task(process_pending_entry, db, entry_id)
    # Re-parse images
    for img in images:
        from parsing import process_image_entry
        background_tasks.add_task(process_image_entry, db, entry_id, img["image_path"])
    return {"status": "queued", "images": len(images), "has_text": bool(entry.get("raw_input"))}


@app.post("/api/reparse-failed")
async def reparse_all_failed(
    background_tasks: BackgroundTasks,
    db: Database = Depends(get_db),
):
    entries = db.execute(
        "SELECT id FROM log_entries WHERE type = 'meal' AND parse_status IN ('failed', 'pending')"
    ).fetchall()
    count = 0
    for row in entries:
        entry_id = row["id"]
        entry = db.get_log_entry(entry_id)
        images = db.list_images(entry_id)
        if entry.get("raw_input"):
            from parsing import process_pending_entry
            db.update_log_entry(entry_id, parse_status="pending")
            background_tasks.add_task(process_pending_entry, db, entry_id)
        for img in images:
            from parsing import process_image_entry
            background_tasks.add_task(process_image_entry, db, entry_id, img["image_path"])
        count += 1
    return {"status": "queued", "entries": count}


@app.get("/api/event-presets")
def get_event_presets():
    presets_file = CONFIG_DIR / "event_presets.txt"
    if not presets_file.exists():
        return []
    return [line.strip() for line in presets_file.read_text().splitlines() if line.strip()]


@app.get("/api/medicine-presets")
def get_medicine_presets():
    presets_file = CONFIG_DIR / "medicine_presets.txt"
    if not presets_file.exists():
        return []
    return [line.strip() for line in presets_file.read_text().splitlines() if line.strip()]


# Serve static files (built frontend) — must be last
if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
