#!/usr/bin/env python3
"""Nightly backup of the eczema database.

Run from cron. The previous crontab entry shelled out to the sqlite3 CLI, which
is not installed on this Pi, and pointed at /home/felix/eczema-app (the repo
actually lives under ~/Documents). Both failures were silent, so there were no
backups at all. This uses the stdlib sqlite3 backup API instead: no extra
packages, and it is safe to run against the live WAL database while uvicorn has
it open.
"""

import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "eczema.db"
BACKUP_DIR = Path.home() / "backups"
RETENTION_DAYS = 7


def log(message):
    print(f"{datetime.now().isoformat(timespec='seconds')} {message}", flush=True)


def prune(now):
    cutoff = now - timedelta(days=RETENTION_DAYS)
    for old in sorted(BACKUP_DIR.glob("eczema-*.db")):
        try:
            stamp = datetime.strptime(old.stem.removeprefix("eczema-"), "%Y%m%d")
        except ValueError:
            continue  # not one of ours; leave it alone
        if stamp < cutoff:
            old.unlink()
            log(f"pruned {old.name}")


def main():
    if not DB_PATH.exists():
        log(f"FAILED: no database at {DB_PATH}")
        return 1

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    dest = BACKUP_DIR / f"eczema-{now:%Y%m%d}.db"

    # Write to a temp file first so an interrupted run cannot leave a truncated
    # backup sitting at the real name, looking like a good one.
    tmp = dest.with_suffix(".db.partial")
    try:
        source = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        try:
            target = sqlite3.connect(tmp)
            try:
                source.backup(target)
            finally:
                target.close()
        finally:
            source.close()
        tmp.replace(dest)
    except Exception as exc:
        log(f"FAILED: {exc}")
        tmp.unlink(missing_ok=True)
        return 1

    entries = sqlite3.connect(dest).execute("SELECT count(*) FROM log_entries").fetchone()[0]
    log(f"wrote {dest.name} ({dest.stat().st_size:,} bytes, {entries} entries)")

    prune(now)
    return 0


if __name__ == "__main__":
    sys.exit(main())
