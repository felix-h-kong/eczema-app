from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"
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
FLARE_SEVERITY_THRESHOLD = 7  # skin check-ins with severity >= this count as flares
MEDICATION_CONFOUND_HOURS = 12
MIN_FLARE_APPEARANCES = 2
LOW_FLARE_WARNING_THRESHOLD = 10
