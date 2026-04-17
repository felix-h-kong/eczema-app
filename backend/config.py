from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"
DATA_DIR = BASE_DIR / "data"
IMAGES_DIR = DATA_DIR / "images"
DB_PATH = DATA_DIR / "eczema.db"
STATIC_DIR = Path(__file__).resolve().parent / "static"

# Claude API
CLAUDE_MODEL = "claude-haiku-4-5-20251001"

# Notification schedule (Australia/Sydney handles AEST/AEDT automatically)
AEST_TIMEZONE = "Australia/Sydney"

NOTIFICATION_TIMES_AEST = {
    "breakfast": "07:30",
    "lunch": "12:00",
    "dinner": "18:30",
}
NOTIFICATION_SKIP_WINDOW_HOURS = 2

# Nudge reminders: (nudge_time, meal_reminder_time) — fires 1h after meal reminder
NUDGE_TIMES_AEST = {
    "breakfast": ("08:30", "07:30"),
    "lunch": ("13:00", "12:00"),
    "dinner": ("19:30", "18:30"),
}

# Bedtime reminder
BEDTIME_TIME_AEST = "22:30"

# Weekly recurring tasks (acknowledged by logging a matching event)
WEEKLY_TASKS = [
    {"preset": "Cut nails", "message": "Weekly reminder: time to cut your nails"},
    {"preset": "Changed sheets", "message": "Weekly reminder: time to change the sheets"},
]
WEEKLY_TASK_TIME_AEST = "09:00"

# Analysis
FLARE_WINDOW_HOURS = (6, 48)  # meals 6-48h before flare

# Flare detection — tunable via config/analysis.txt
def _load_analysis_config():
    defaults = {"flare_rise_threshold": 3, "flare_rolling_window": 3}
    path = CONFIG_DIR / "analysis.txt"
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                k = k.strip().lower()
                if k in defaults:
                    defaults[k] = int(v.strip())
    return defaults

def get_flare_config():
    """Read flare detection config fresh from disk each time."""
    cfg = _load_analysis_config()
    return cfg["flare_rise_threshold"], cfg["flare_rolling_window"]
# Air quality monitoring (NSW DPIE)
AIR_QUALITY_API_BASE = "https://data.airquality.nsw.gov.au/api/Data"
AIR_QUALITY_STATIONS = {
    70: "Lindfield",
    113: "Macquarie Park",
    155: "Rouse Hill",
    1001: "Cook and Phillip",
    1007: "Ultimo-UTS",
    15: "Alexandria",
}
AIR_QUALITY_PARAMETERS = ["PM2.5"]
AIR_QUALITY_DEFAULT_HOURS_BACK = 25   # 1h overlap for hourly cron
AIR_QUALITY_MAX_HOURS_BACK = 168      # max backfill = 7 days

MEDICATION_CONFOUND_HOURS = 12
MIN_FLARE_APPEARANCES = 2
LOW_FLARE_WARNING_THRESHOLD = 10
