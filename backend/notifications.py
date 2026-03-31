import json
import logging
import os
from datetime import datetime, timedelta, timezone

from pywebpush import webpush, WebPushException

from config import AEST_OFFSET_HOURS, NOTIFICATION_SKIP_WINDOW_HOURS

logger = logging.getLogger(__name__)

VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY", "")
VAPID_CLAIMS = {"sub": "mailto:admin@localhost"}

AEST_TZ = timezone(timedelta(hours=AEST_OFFSET_HOURS))


def send_push(db, title: str, body: str, url: str = "/") -> None:
    subscriptions = db.list_push_subscriptions()
    for sub in subscriptions:
        keys = json.loads(sub["keys_json"])
        try:
            webpush(
                subscription_info={"endpoint": sub["endpoint"], "keys": keys},
                data=json.dumps({"title": title, "body": body, "url": url}),
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims=VAPID_CLAIMS,
            )
        except WebPushException as e:
            logger.error(f"Push failed for {sub['endpoint']}: {e}")
        except Exception as e:
            logger.error(f"Unexpected push error: {e}")


def should_send_notification(db) -> bool:
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=NOTIFICATION_SKIP_WINDOW_HOURS)).isoformat()
    recent_meals = db.list_log_entries(entry_type="meal", from_date=cutoff)
    return len(recent_meals) == 0


def send_meal_reminder(db, message: str) -> None:
    if not should_send_notification(db):
        logger.info("Skipping notification — recent meal logged")
        return
    send_push(db, "Eczema Tracker", message)


def send_meal_nudge(db, meal: str, reminder_time_aest: str) -> None:
    now_utc = datetime.now(timezone.utc)
    today_aest = now_utc.astimezone(AEST_TZ).date()
    hour, minute = map(int, reminder_time_aest.split(":"))
    cutoff_aest = datetime(today_aest.year, today_aest.month, today_aest.day,
                           hour, minute, tzinfo=AEST_TZ)
    cutoff_utc = cutoff_aest.astimezone(timezone.utc).isoformat()

    recent_meals = db.list_log_entries(entry_type="meal", from_date=cutoff_utc)
    if len(recent_meals) > 0:
        logger.info(f"Skipping {meal} nudge — meal already logged")
        return
    send_push(db, "Eczema Tracker", f"Haven't logged {meal} yet \u2014 don't forget!")


def send_bedtime_reminder(db) -> None:
    send_push(db, "Eczema Tracker", "Bedtime \u2014 time for your evening check-in")


def send_weekly_task_reminder(db, preset: str, message: str) -> None:
    now_aest = datetime.now(timezone.utc).astimezone(AEST_TZ)
    days_since_saturday = (now_aest.weekday() - 5) % 7  # Saturday = 5
    last_saturday = now_aest.date() - timedelta(days=days_since_saturday)
    cutoff_aest = datetime(last_saturday.year, last_saturday.month, last_saturday.day,
                           tzinfo=AEST_TZ)
    cutoff_utc = cutoff_aest.astimezone(timezone.utc).isoformat()

    entries = db.list_log_entries(entry_type="note", from_date=cutoff_utc)
    for entry in entries:
        if (entry.get("notes") or "").strip().lower() == preset.strip().lower():
            logger.info(f"Skipping '{preset}' reminder — already acknowledged")
            return
    send_push(db, "Eczema Tracker", message, url="/?action=event")


def send_test_notification(db) -> None:
    send_push(db, "Eczema Tracker", "This is a test notification. It works!")


def setup_scheduler(db):
    from apscheduler.schedulers.background import BackgroundScheduler
    from config import (
        NOTIFICATION_TIMES_AEST, NUDGE_TIMES_AEST,
        BEDTIME_TIME_AEST, WEEKLY_TASKS, WEEKLY_TASK_TIME_AEST,
    )

    scheduler = BackgroundScheduler()

    def to_utc(aest_time_str):
        hour, minute = map(int, aest_time_str.split(":"))
        return (hour - AEST_OFFSET_HOURS) % 24, minute

    # Meal reminders
    for meal, time_str in NOTIFICATION_TIMES_AEST.items():
        utc_hour, minute = to_utc(time_str)
        scheduler.add_job(
            send_meal_reminder, "cron",
            hour=utc_hour, minute=minute,
            args=[db, f"Time to log {meal}"],
            id=f"reminder_{meal}",
        )

    # Meal nudges (1h after each meal reminder)
    for meal, (nudge_time, reminder_time) in NUDGE_TIMES_AEST.items():
        utc_hour, minute = to_utc(nudge_time)
        scheduler.add_job(
            send_meal_nudge, "cron",
            hour=utc_hour, minute=minute,
            args=[db, meal, reminder_time],
            id=f"nudge_{meal}",
        )

    # Bedtime reminder
    utc_hour, minute = to_utc(BEDTIME_TIME_AEST)
    scheduler.add_job(
        send_bedtime_reminder, "cron",
        hour=utc_hour, minute=minute,
        args=[db],
        id="bedtime_reminder",
    )

    # Weekly tasks — run daily, function checks acknowledgment since last Saturday
    for task in WEEKLY_TASKS:
        task_id = task["preset"].lower().replace(" ", "_")
        utc_hour, minute = to_utc(WEEKLY_TASK_TIME_AEST)
        scheduler.add_job(
            send_weekly_task_reminder, "cron",
            hour=utc_hour, minute=minute,
            args=[db, task["preset"], task["message"]],
            id=f"weekly_{task_id}",
        )

    scheduler.start()
    return scheduler
