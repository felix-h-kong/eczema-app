#!/usr/bin/env python3
"""Generate the all-time severity timeline chart.

Usage:
    python scripts/build_severity_timeline.py
    python scripts/build_severity_timeline.py --out docs/reports/severity-timeline.png
"""
import argparse
import sys
from collections import defaultdict
from datetime import date, datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from db import Database
from config import DB_PATH

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.dates import DateFormatter, DayLocator
import matplotlib.dates as mdates

SYDNEY_OFFSET = 10  # hours — good enough for chart labels (no DST complexity needed)

PHASES = [
    {
        "label": "Phase 1: Urea irritant in use",
        "start": date(2026, 3, 23),
        "end": date(2026, 4, 1),
        "color": "#ffd6cc",
    },
    {
        "label": "Phase 2: Stopped urea + steroids + ocean",
        "start": date(2026, 4, 1),
        "end": date(2026, 4, 5),
        "color": "#ccf5d4",
    },
    {
        "label": "Phase 3: High-histamine diet",
        "start": date(2026, 4, 5),
        "end": date(2026, 4, 12),
        "color": "#fff3cc",
    },
    {
        "label": "Phase 4: Lower-histamine diet",
        "start": date(2026, 4, 12),
        "end": None,  # resolved dynamically to last data date + 1
        "color": "#cce5ff",
    },
]

# Hardcoded annotations: (date, severity_y, label, xytext offset, arrow_style)
ANNOTATIONS = [
    {
        "date": date(2026, 3, 31),
        "y": 9.0,
        "text": "Stopped urea\nmoisturiser",
        "xytext": (-45, 18),
        "arrowstyle": "->",
    },
    {
        "date": date(2026, 4, 1),
        "y": 8.5,
        "text": "GP visit,\nheavy steroids",
        "xytext": (12, 20),
        "arrowstyle": "->",
    },
    {
        "date": date(2026, 4, 4),
        "y": 4.3,
        "text": "Ocean\nsnorkel #1",
        "xytext": (-52, -30),
        "arrowstyle": "->",
    },
    {
        "date": date(2026, 4, 5),
        "y": 3.0,
        "text": "Best AM=3,\nthen food flare",
        "xytext": (8, -35),
        "arrowstyle": "->",
    },
    {
        "date": date(2026, 4, 6),
        "y": 6.5,
        "text": "Bay leaf\nsoup",
        "xytext": (-12, 22),
        "arrowstyle": "->",
    },
    {
        "date": date(2026, 4, 11),
        "y": 7.5,
        "text": "Wedding\n[brie, alcohol,\ncured fish]",
        "xytext": (-18, 22),
        "arrowstyle": "->",
    },
    {
        "date": date(2026, 4, 12),
        "y": 2.5,
        "text": "Diet shift to\nlower-histamine",
        "xytext": (10, -38),
        "arrowstyle": "->",
        "color": "#005a9e",
        "weight": "bold",
    },
    {
        "date": date(2026, 4, 13),
        "y": 7.0,
        "text": "Phototherapy\nstopped\n(nosebleed, #4)",
        "xytext": (12, 25),
        "arrowstyle": "->",
        "color": "#8b0000",
    },
    {
        "date": date(2026, 4, 16),
        "y": 5.5,
        "text": "Back-burning\nsmoke",
        "xytext": (-70, 35),
        "arrowstyle": "->",
    },
    {
        "date": date(2026, 4, 17),
        "y": 5.8,
        "text": "Ocean snorkel #2\n+ smoke, worst itch day",
        "xytext": (5, 32),
        "arrowstyle": "->",
    },
    {
        "date": date(2026, 4, 18),
        "y": 4.0,
        "text": "Dog exposure\n— wheezing",
        "xytext": (-60, -42),
        "arrowstyle": "->",
    },
    {
        "date": date(2026, 4, 25),
        "y": 4.0,
        "text": "No-leftovers policy\n+ bedroom vacuumed",
        "xytext": (8, -42),
        "arrowstyle": "->",
    },
    {
        "date": date(2026, 4, 28),
        "y": 6.0,
        "text": "High-histamine dinner\n[lasagna, anchovies,\ncultured butter]",
        "xytext": (10, 55),
        "arrowstyle": "->",
        "color": "#8b4513",
    },
]

SEVERITY_ZONES = [
    {"label": "SEVERE", "ymin": 8, "ymax": 10, "color": "#ffa07a", "alpha": 0.12},
    {"label": "MODERATE–\nSEVERE", "ymin": 6, "ymax": 8, "color": "#ffd700", "alpha": 0.10},
    {"label": "MODERATE", "ymin": 4, "ymax": 6, "color": "#98fb98", "alpha": 0.10},
    {"label": "MILD", "ymin": 0, "ymax": 4, "color": "#87ceeb", "alpha": 0.10},
]


def parse_ts(ts_str: str) -> datetime:
    ts_str = ts_str.replace("Z", "+00:00")
    dt = datetime.fromisoformat(ts_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def to_local_date(ts_str: str) -> date:
    dt = parse_ts(ts_str)
    return (dt + timedelta(hours=SYDNEY_OFFSET)).date()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "docs" / "reports" / "severity-timeline.png"))
    args = ap.parse_args()

    db = Database(DB_PATH)
    skin_entries = db.list_log_entries(entry_type="flare")

    # Daily averages
    by_day: dict[date, list[int]] = defaultdict(list)
    for e in skin_entries:
        sev = e.get("severity")
        if sev is not None:
            by_day[to_local_date(e["timestamp"])].append(sev)

    days_sorted = sorted(by_day.keys())
    daily_avg = {d: sum(v) / len(v) for d, v in by_day.items()}

    first_day = days_sorted[0]
    last_day = days_sorted[-1]

    # Resolve dynamic phase end
    for phase in PHASES:
        if phase["end"] is None:
            phase["end"] = last_day + timedelta(days=1)

    # Photo and Nizoral dates from DB
    conn = db._connect()
    photo_rows = conn.execute("SELECT timestamp FROM entry_images").fetchall()
    nizoral_rows = conn.execute(
        "SELECT timestamp FROM log_entries WHERE LOWER(notes) LIKE '%nizoral%'"
    ).fetchall()
    conn.close()
    photo_dates = sorted({to_local_date(r["timestamp"]) for r in photo_rows})
    nizoral_dates = sorted({to_local_date(r["timestamp"]) for r in nizoral_rows})

    # Phase 4 average for annotation
    phase4_start = date(2026, 4, 12)
    phase4_days = [d for d in days_sorted if d >= phase4_start]
    phase4_avg = sum(daily_avg[d] for d in phase4_days) / len(phase4_days) if phase4_days else None

    # x-axis bounds: 1 day padding each side, extra space for zone labels on right
    x_start = first_day - timedelta(days=1)
    x_end = last_day + timedelta(days=2)
    total_days = (x_end - x_start).days
    tick_interval = max(2, total_days // 16)

    # --- Plot ---
    fig, ax = plt.subplots(figsize=(20, 7))

    # Phase backgrounds
    for phase in PHASES:
        ax.axvspan(
            mdates.date2num(phase["start"]),
            mdates.date2num(phase["end"]),
            color=phase["color"], alpha=0.85, zorder=0,
        )

    # Severity zone bands (right-side labels)
    for zone in SEVERITY_ZONES:
        ax.axhspan(zone["ymin"], zone["ymax"], color=zone["color"], alpha=zone["alpha"], zorder=0)

    # Data line + markers
    plot_dates = [mdates.date2num(d) for d in days_sorted]
    plot_vals = [daily_avg[d] for d in days_sorted]
    ax.plot(plot_dates, plot_vals, color="#444444", linewidth=1.4, zorder=3)
    ax.scatter(plot_dates, plot_vals, color="#e85a1e", s=60, zorder=4)

    # Photo markers (downward purple triangles above dot)
    for pd in photo_dates:
        y = daily_avg.get(pd)
        if y is not None:
            ax.scatter(
                [mdates.date2num(pd)], [y + 0.35],
                marker="v", color="#7b2d8b", s=70, zorder=5,
            )

    # Nizoral markers (upward green triangles below dot)
    for nd in nizoral_dates:
        y = daily_avg.get(nd)
        if y is not None:
            ax.scatter(
                [mdates.date2num(nd)], [y - 0.4],
                marker="^", color="#2e8b57", s=70, zorder=5,
            )

    # Phase 4 average line
    if phase4_avg and phase4_days:
        x0 = mdates.date2num(phase4_days[0])
        x1 = mdates.date2num(phase4_days[-1])
        ax.annotate(
            "",
            xy=(x1, phase4_avg), xytext=(x0, phase4_avg),
            arrowprops=dict(arrowstyle="<->", color="#005a9e", lw=1.5),
            zorder=6,
        )
        ax.text(
            (x0 + x1) / 2, phase4_avg + 0.25,
            f"avg {phase4_avg:.1f}",
            ha="center", va="bottom", fontsize=14, color="#005a9e", fontweight="bold",
        )

    # Annotations
    for ann in ANNOTATIONS:
        xy_date = mdates.date2num(ann["date"])
        xy_y = ann["y"]
        xt, yt = ann["xytext"]
        ax.annotate(
            ann["text"],
            xy=(xy_date, xy_y),
            xytext=(xt, yt),
            textcoords="offset points",
            fontsize=11,
            color=ann.get("color", "#333333"),
            fontweight=ann.get("weight", "normal"),
            arrowprops=dict(arrowstyle=ann["arrowstyle"], color="#555555", lw=0.9),
            bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="#aaaaaa", alpha=0.85, lw=0.7),
            zorder=7,
        )

    # Right-side zone labels — clip_on=False so they render beyond the x limit
    x_label = mdates.date2num(x_end) + 0.1
    for zone in SEVERITY_ZONES:
        mid_y = (zone["ymin"] + zone["ymax"]) / 2
        ax.text(
            x_label, mid_y, zone["label"],
            fontsize=13, va="center", ha="left", color="#666666",
            clip_on=False,
        )

    # Axes formatting
    ax.set_xlim(mdates.date2num(x_start), mdates.date2num(x_end))
    ax.set_ylim(0, 10)
    ax.xaxis.set_major_locator(DayLocator(interval=tick_interval))
    ax.xaxis.set_major_formatter(DateFormatter("%b %-d"))
    plt.xticks(rotation=0, ha="center", fontsize=13)
    plt.yticks(range(0, 11, 2), fontsize=14)
    ax.set_xlabel("Date (2026)", fontsize=16, labelpad=8)
    ax.set_ylabel("Daily Average Severity", fontsize=16, labelpad=8)
    ax.grid(axis="y", linestyle="--", alpha=0.4, zorder=1)
    ax.tick_params(axis="both", which="major", labelsize=13)

    # Legend
    phase_patches = [
        mpatches.Patch(color=p["color"], label=p["label"]) for p in PHASES
    ]
    photo_marker = plt.scatter([], [], marker="v", color="#7b2d8b", s=70, label="Photo taken")
    nizoral_marker = plt.scatter([], [], marker="^", color="#2e8b57", s=70, label="Nizoral (antifungal)")
    ax.legend(
        handles=phase_patches + [photo_marker, nizoral_marker],
        loc="lower left",
        fontsize=12,
        framealpha=0.9,
        edgecolor="#cccccc",
    )

    n_days = len(days_sorted)
    n_checks = sum(len(v) for v in by_day.values())
    plt.title(
        "Eczema Severity Timeline — All-Time Self-Tracking",
        fontsize=20, fontweight="bold", pad=10,
    )
    plt.suptitle(
        f"Self-reported 0–10 scale · Lower = better · {n_checks} skin checks across {n_days} days with data",
        fontsize=13, y=0.97, color="#555555",
    )

    fig.subplots_adjust(left=0.06, right=0.82, top=0.88, bottom=0.10)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out}")


if __name__ == "__main__":
    main()
