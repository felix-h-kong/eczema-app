#!/usr/bin/env python3
"""Severity timeline chart for the Apr 11 – May 1 analysis session."""
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
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

SYDNEY_OFFSET = 10

PHASES = [
    {
        "label": "Phase 1: Wedding + high-histamine restaurant meals",
        "start": date(2026, 4, 11),
        "end": date(2026, 4, 14),
        "color": "#ffd6cc",
    },
    {
        "label": "Phase 2: Clean diet · frozen batch-cook · no leftovers",
        "start": date(2026, 4, 14),
        "end": date(2026, 4, 23),
        "color": "#ccf5d4",
    },
    {
        "label": "Phase 3: Re-exposure to histamine triggers",
        "start": date(2026, 4, 23),
        "end": date(2026, 5, 2),
        "color": "#fff3cc",
    },
]

ANNOTATIONS = [
    {
        "date": date(2026, 4, 12),
        "y": 8.0,
        "text": "Wedding after-effects\n[brie, anchovy, alcohol,\ncured barramundi]",
        "xytext": (10, 18),
        "arrowstyle": "->",
    },
    {
        "date": date(2026, 4, 14),
        "y": 6.0,
        "text": "Diet shift:\nfrozen batch-cook,\nno leftovers",
        "xytext": (8, -48),
        "arrowstyle": "->",
        "color": "#005a9e",
        "weight": "bold",
    },
    {
        "date": date(2026, 4, 16),
        "y": 5.5,
        "text": "Pappa Flock\nspicy chicken\n+ back-burning smoke",
        "xytext": (-90, 28),
        "arrowstyle": "->",
    },
    {
        "date": date(2026, 4, 17),
        "y": 5.75,
        "text": "Ocean snorkel #3\n(partial benefit)",
        "xytext": (8, 28),
        "arrowstyle": "->",
    },
    {
        "date": date(2026, 4, 19),
        "y": 5.3,
        "text": "Granola first\nappears",
        "xytext": (-72, 32),
        "arrowstyle": "->",
        "color": "#8b5e00",
    },
    {
        "date": date(2026, 4, 22),
        "y": 3.5,
        "text": "Best reading:\navg 3.5\n\"rashes all brown,\nno new ones\"",
        "xytext": (8, -52),
        "arrowstyle": "->",
        "color": "#1a6e1a",
        "weight": "bold",
    },
    {
        "date": date(2026, 4, 25),
        "y": 3.0,
        "text": "\"This last week very\ngood — no-leftovers\npolicy working\"",
        "xytext": (8, -55),
        "arrowstyle": "->",
        "color": "#1a6e1a",
    },
    {
        "date": date(2026, 4, 26),
        "y": 4.5,
        "text": "Gochugaru\n(suspected reaction)",
        "xytext": (8, 30),
        "arrowstyle": "->",
        "color": "#8b0000",
    },
    {
        "date": date(2026, 4, 27),
        "y": 5.0,
        "text": "Anchovy on bread\n[very high histamine]",
        "xytext": (-110, 32),
        "arrowstyle": "->",
        "color": "#8b0000",
    },
    {
        "date": date(2026, 4, 29),
        "y": 6.0,
        "text": "Shin ramyun +\nsesame paste noodles",
        "xytext": (8, 20),
        "arrowstyle": "->",
    },
    {
        "date": date(2026, 5, 1),
        "y": 7.0,
        "text": "Today\nsev=7",
        "xytext": (-65, 18),
        "arrowstyle": "->",
        "color": "#cc0000",
        "weight": "bold",
    },
]

SEVERITY_ZONES = [
    {"label": "SEVERE",           "ymin": 8, "ymax": 10, "color": "#ffa07a", "alpha": 0.12},
    {"label": "MODERATE–\nSEVERE","ymin": 6, "ymax": 8,  "color": "#ffd700", "alpha": 0.10},
    {"label": "MODERATE",         "ymin": 4, "ymax": 6,  "color": "#98fb98", "alpha": 0.10},
    {"label": "MILD",             "ymin": 0, "ymax": 4,  "color": "#87ceeb", "alpha": 0.10},
]


def to_local_date(ts_str: str) -> date:
    ts_str = ts_str.replace("Z", "+00:00")
    dt = datetime.fromisoformat(ts_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (dt + timedelta(hours=SYDNEY_OFFSET)).date()


def main():
    out_path = ROOT / "docs" / "reports" / "may-timeline.png"

    db = Database(DB_PATH)
    skin_entries = db.list_log_entries(entry_type="flare")

    by_day: dict[date, list[int]] = defaultdict(list)
    for e in skin_entries:
        sev = e.get("severity")
        if sev is None:
            continue
        d = to_local_date(e["timestamp"])
        if date(2026, 4, 11) <= d <= date(2026, 5, 1):
            by_day[d].append(sev)

    days_sorted = sorted(by_day.keys())
    daily_avg = {d: sum(v) / len(v) for d, v in by_day.items()}

    # Phase 2 average (the good period)
    p2_days = [d for d in days_sorted if date(2026, 4, 14) <= d < date(2026, 4, 23)]
    p2_avg = sum(daily_avg[d] for d in p2_days) / len(p2_days) if p2_days else None

    fig, ax = plt.subplots(figsize=(18, 7))

    for phase in PHASES:
        ax.axvspan(
            mdates.date2num(phase["start"]),
            mdates.date2num(phase["end"]),
            color=phase["color"], alpha=0.85, zorder=0,
        )

    for zone in SEVERITY_ZONES:
        ax.axhspan(zone["ymin"], zone["ymax"], color=zone["color"], alpha=zone["alpha"], zorder=0)

    plot_dates = [mdates.date2num(d) for d in days_sorted]
    plot_vals = [daily_avg[d] for d in days_sorted]
    ax.plot(plot_dates, plot_vals, color="#444444", linewidth=1.4, zorder=3)
    ax.scatter(plot_dates, plot_vals, color="#e85a1e", s=60, zorder=4)

    # Granola marker: daily from Apr 30
    granola_dates = [date(2026, 4, 19), date(2026, 4, 23), date(2026, 4, 25), date(2026, 4, 30)]
    for gd in granola_dates:
        y = daily_avg.get(gd)
        if y is not None:
            ax.scatter(
                [mdates.date2num(gd)], [y + 0.4],
                marker="*", color="#c47a00", s=110, zorder=5,
            )
    # Apr 30 has no skin check — mark at top of chart
    ax.scatter(
        [mdates.date2num(date(2026, 4, 30))], [0.6],
        marker="*", color="#c47a00", s=110, zorder=5,
    )
    ax.text(
        mdates.date2num(date(2026, 4, 30)), 0.8,
        "granola\ndaily", ha="center", va="bottom", fontsize=9,
        color="#c47a00", style="italic",
    )

    # Phase 2 average line
    if p2_avg and p2_days:
        x0 = mdates.date2num(p2_days[0])
        x1 = mdates.date2num(p2_days[-1])
        ax.annotate(
            "",
            xy=(x1, p2_avg), xytext=(x0, p2_avg),
            arrowprops=dict(arrowstyle="<->", color="#005a9e", lw=1.5),
            zorder=6,
        )
        ax.text(
            (x0 + x1) / 2, p2_avg + 0.22,
            f"avg {p2_avg:.1f}",
            ha="center", va="bottom", fontsize=13, color="#005a9e", fontweight="bold",
        )

    for ann in ANNOTATIONS:
        xy_date = mdates.date2num(ann["date"])
        xy_y = ann["y"]
        xt, yt = ann["xytext"]
        ax.annotate(
            ann["text"],
            xy=(xy_date, xy_y),
            xytext=(xt, yt),
            textcoords="offset points",
            fontsize=10,
            color=ann.get("color", "#333333"),
            fontweight=ann.get("weight", "normal"),
            arrowprops=dict(arrowstyle=ann["arrowstyle"], color="#555555", lw=0.9),
            bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="#aaaaaa", alpha=0.85, lw=0.7),
            zorder=7,
        )

    x_label = mdates.date2num(date(2026, 5, 1)) + 0.3
    for zone in SEVERITY_ZONES:
        mid_y = (zone["ymin"] + zone["ymax"]) / 2
        ax.text(
            x_label, mid_y, zone["label"],
            fontsize=12, va="center", ha="left", color="#666666",
            clip_on=False,
        )

    ax.set_xlim(mdates.date2num(date(2026, 4, 10)), mdates.date2num(date(2026, 5, 1)))
    ax.set_ylim(0, 10)
    ax.xaxis.set_major_locator(DayLocator(interval=2))
    ax.xaxis.set_major_formatter(DateFormatter("%b %-d"))
    plt.xticks(rotation=0, ha="center", fontsize=13)
    plt.yticks(range(0, 11, 2), fontsize=13)
    ax.set_xlabel("Date (2026)", fontsize=15, labelpad=8)
    ax.set_ylabel("Daily Average Severity", fontsize=15, labelpad=8)
    ax.grid(axis="y", linestyle="--", alpha=0.4, zorder=1)
    ax.tick_params(axis="both", which="major", labelsize=13)

    phase_patches = [mpatches.Patch(color=p["color"], label=p["label"]) for p in PHASES]
    granola_marker = plt.scatter([], [], marker="*", color="#c47a00", s=90, label="Granola eaten")
    ax.legend(
        handles=phase_patches + [granola_marker],
        loc="upper right",
        fontsize=11,
        framealpha=0.9,
        edgecolor="#cccccc",
    )

    n_days = len(days_sorted)
    n_checks = sum(len(v) for v in by_day.values())
    plt.title(
        "Eczema Severity Timeline — Apr 11 – May 1, 2026",
        fontsize=19, fontweight="bold", pad=10,
    )
    plt.suptitle(
        f"Self-reported 0–10 scale · Lower = better · {n_checks} skin checks across {n_days} days with data",
        fontsize=12, y=0.97, color="#555555",
    )

    fig.subplots_adjust(left=0.06, right=0.82, top=0.88, bottom=0.10)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    main()
