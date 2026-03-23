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
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=NOTIFICATION_SKIP_WINDOW_HOURS)).isoformat()
    recent_meals = db.list_log_entries(entry_type="meal", from_date=cutoff)
    return len(recent_meals) == 0


def send_meal_reminder(db, message: str) -> None:
    if not should_send_notification(db):
        logger.info("Skipping notification — recent meal logged")
        return

    subscriptions = db.list_push_subscriptions()
    for sub in subscriptions:
        keys = json.loads(sub["keys_json"])
        try:
            webpush(
                subscription_info={"endpoint": sub["endpoint"], "keys": keys},
                data=json.dumps({"title": "Eczema Tracker", "body": message}),
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims=VAPID_CLAIMS,
            )
        except WebPushException as e:
            logger.error(f"Push failed for {sub['endpoint']}: {e}")
        except Exception as e:
            logger.error(f"Unexpected push error: {e}")


def setup_scheduler(db) -> None:
    from apscheduler.schedulers.background import BackgroundScheduler
    from config import NOTIFICATION_TIMES_AEST

    scheduler = BackgroundScheduler()
    aest_offset = 10  # UTC+10 (ignoring DST for simplicity)

    for meal, time_str in NOTIFICATION_TIMES_AEST.items():
        hour, minute = map(int, time_str.split(":"))
        utc_hour = (hour - aest_offset) % 24
        scheduler.add_job(
            send_meal_reminder, "cron",
            hour=utc_hour, minute=minute,
            args=[db, f"Time to log {meal}"],
            id=f"reminder_{meal}",
        )

    scheduler.start()
    return scheduler
