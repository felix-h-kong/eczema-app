#!/usr/bin/env python3
"""All-time severity timeline — Mar 23 to Jun 6, 2026."""
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
        "box_label": "CeraVe urea\nirritant in use",
        "start": date(2026, 3, 22),
        "end": date(2026, 4, 1),
        "color": "#ffd6cc",
    },
    {
        "box_label": "GP visit:\nsteroids +\nurea stopped",
        "start": date(2026, 4, 1),
        "end": date(2026, 4, 5),
        "color": "#ccf5d4",
        "fontsize": 7.5,
    },
    {
        "box_label": "High-histamine\nrebound",
        "start": date(2026, 4, 5),
        "end": date(2026, 4, 13),
        "color": "#ffe8b0",
    },
    {
        "box_label": "Frozen batch-cook\nno leftovers",
        "start": date(2026, 4, 13),
        "end": date(2026, 4, 18),
        "color": "#cce8ff",
        "fontsize": 8.0,
    },
    {
        "box_label": "In-laws + restaurant meals\n(ramen, pho, Korean,\nnem nuong)",
        "start": date(2026, 4, 18),
        "end": date(2026, 4, 26),
        "color": "#e0e8d0",
        "fontsize": 7.5,
    },
    {
        "box_label": "Re-exposure:\ngochugaru, anchovy\nlasagna, noodle soups",
        "start": date(2026, 4, 26),
        "end": date(2026, 5, 2),
        "color": "#ffd0b0",
    },
    {
        "box_label": "Sustained sev 7\nHK restaurant meals\n+ Cali Press, biscoff",
        "start": date(2026, 5, 2),
        "end": date(2026, 5, 5),
        "color": "#ffb8a0",
        "fontsize": 7.5,
    },
    {
        "box_label": "Frozen clean-diet\nrecovery\n(sev → 3)",
        "start": date(2026, 5, 5),
        "end": date(2026, 5, 9),
        "color": "#ccf5d4",
        "fontsize": 8.0,
    },
    {
        "box_label": "Cold/flu illness\n+ dust mite\ncovers installed",
        "start": date(2026, 5, 9),
        "end": date(2026, 5, 13),
        "color": "#e8d8f0",
        "fontsize": 7.5,
    },
    {
        "box_label": "Dupixent started\n(200mg loading)",
        "start": date(2026, 5, 13),
        "end": date(2026, 5, 17),
        "color": "#cce0ff",
        "fontsize": 8.0,
    },
    {
        "box_label": "Dupixent response:\nbody clearing\n(sev → 3–4)",
        "start": date(2026, 5, 17),
        "end": date(2026, 5, 26),
        "color": "#ccf5d4",
        "fontsize": 8.0,
    },
    {
        "box_label": "Residual: facial\nredness only\n(heat / flushing-linked)",
        "start": date(2026, 5, 26),
        "end": date(2026, 6, 7),
        "color": "#e6f0d6",
        "fontsize": 7.5,
    },
]

ANNOTATIONS = [
    {
        "date": date(2026, 3, 31),
        "y": 8.5,
        "text": "Stopped urea\nmoisturiser",
        "xytext": (-52, 20),
        "arrowstyle": "->",
    },
    {
        "date": date(2026, 4, 1),
        "y": 8.5,
        "text": "GP visit,\nheavy steroids",
        "xytext": (8, 20),
        "arrowstyle": "->",
    },
    {
        "date": date(2026, 4, 4),
        "y": 5.5,
        "text": "Ocean\nsnorkel #1",
        "xytext": (-55, -38),
        "arrowstyle": "->",
    },
    {
        "date": date(2026, 4, 5),
        "y": 3.0,
        "text": "Best AM=3,\nthen food flare\n(Papparich)",
        "xytext": (8, -48),
        "arrowstyle": "->",
    },
    {
        "date": date(2026, 4, 6),
        "y": 6.5,
        "text": "Bay leaf soup",
        "xytext": (-12, 22),
        "arrowstyle": "->",
    },
    {
        "date": date(2026, 4, 11),
        "y": 7.5,
        "text": "Wedding\n[brie, anchovy,\ncured barramundi,\nalcohol]",
        "xytext": (-20, 22),
        "arrowstyle": "->",
    },
    {
        "date": date(2026, 4, 13),
        "y": 2.5,
        "text": "Diet shift:\nfrozen batch-cook,\nno leftovers",
        "xytext": (8, -55),
        "arrowstyle": "->",
        "color": "#005a9e",
        "weight": "bold",
    },
    {
        "date": date(2026, 4, 13),
        "y": 7.2,
        "text": "Phototherapy\nstopped\n(nosebleed, #4)",
        "xytext": (8, 22),
        "arrowstyle": "->",
        "color": "#8b0000",
    },
    {
        "date": date(2026, 4, 16),
        "y": 5.5,
        "text": "Pappa Flock +\nback-burning smoke",
        "xytext": (-100, 32),
        "arrowstyle": "->",
    },
    {
        "date": date(2026, 4, 17),
        "y": 5.8,
        "text": "Ocean snorkel #3\n(partial benefit)",
        "xytext": (8, 28),
        "arrowstyle": "->",
    },
    {
        "date": date(2026, 4, 22),
        "y": 3.5,
        "text": "Best reading: avg 3.5\n\"all rashes brown,\nno new ones\"",
        "xytext": (8, -52),
        "arrowstyle": "->",
        "color": "#1a6e1a",
        "weight": "bold",
    },
    {
        "date": date(2026, 4, 25),
        "y": 3.0,
        "text": "\"No-leftovers\npolicy working\"",
        "xytext": (8, -42),
        "arrowstyle": "->",
        "color": "#1a6e1a",
    },
    {
        "date": date(2026, 4, 27),
        "y": 5.0,
        "text": "Anchovy on bread\n[very high histamine]",
        "xytext": (-115, 30),
        "arrowstyle": "->",
        "color": "#8b0000",
    },
    {
        "date": date(2026, 5, 3),
        "y": 7.0,
        "text": "HK restaurant\nrun (stir-fried\nbeef noodle,\ncurry, pepper beef)",
        "xytext": (-30, 22),
        "arrowstyle": "->",
        "color": "#8b0000",
    },
    {
        "date": date(2026, 5, 7),
        "y": 3.0,
        "text": "Sev=3 post-gym\n(frozen poached\nchicken + Marion's\nchili rotation)",
        "xytext": (-10, -55),
        "arrowstyle": "->",
        "color": "#1a6e1a",
        "weight": "bold",
    },
    {
        "date": date(2026, 5, 9),
        "y": 5.0,
        "text": "Got sick:\ncold + flu",
        "xytext": (-18, 28),
        "arrowstyle": "->",
        "color": "#8b0000",
    },
    {
        "date": date(2026, 5, 10),
        "y": 5.0,
        "text": "Dust mite\ncovers installed",
        "xytext": (10, -42),
        "arrowstyle": "->",
        "color": "#005a9e",
    },
    {
        "date": date(2026, 5, 13),
        "y": 8.0,
        "text": "Dupixent 200mg\n(double-dose loading)\nSev=8 same morning",
        "xytext": (-130, 18),
        "arrowstyle": "->",
        "color": "#005a9e",
        "weight": "bold",
    },
    {
        "date": date(2026, 5, 16),
        "y": 4.0,
        "text": "sev=4\n(improving on\nDupixent)",
        "xytext": (-78, -40),
        "arrowstyle": "->",
        "color": "#1a6e1a",
        "weight": "bold",
    },
    {
        "date": date(2026, 5, 26),
        "y": 3.5,
        "text": "Dupixent\n2nd dose",
        "xytext": (-8, -42),
        "arrowstyle": "->",
        "color": "#005a9e",
    },
    {
        "date": date(2026, 5, 30),
        "y": 6.0,
        "text": "Facial spike (6):\nsunscreen + heat\n+ aged-histamine\npile-up",
        "xytext": (-30, 26),
        "arrowstyle": "->",
        "color": "#8b0000",
    },
    {
        "date": date(2026, 6, 3),
        "y": 3.0,
        "text": "Body smooth;\nface-only redness\nremains (heat-linked)",
        "xytext": (8, -52),
        "arrowstyle": "->",
        "color": "#1a6e1a",
        "weight": "bold",
    },
]

SEVERITY_ZONES = [
    {"label": "SEVERE",           "ymin": 8, "ymax": 10, "color": "#ffa07a", "alpha": 0.12},
    {"label": "MODERATE–\nSEVERE","ymin": 6, "ymax": 8,  "color": "#ffd700", "alpha": 0.10},
    {"label": "MODERATE",         "ymin": 4, "ymax": 6,  "color": "#98fb98", "alpha": 0.10},
    {"label": "MILD",             "ymin": 0, "ymax": 4,  "color": "#87ceeb", "alpha": 0.10},
]

# Monday dates within the chart window for week boundary markers
WEEK_MONDAYS = [
    date(2026, 3, 23),
    date(2026, 3, 30),
    date(2026, 4, 6),
    date(2026, 4, 13),
    date(2026, 4, 20),
    date(2026, 4, 27),
    date(2026, 5, 4),
    date(2026, 5, 11),
    date(2026, 5, 18),
    date(2026, 5, 25),
    date(2026, 6, 1),
]


def to_local_datetime(ts_str: str) -> datetime:
    ts_str = ts_str.replace("Z", "+00:00")
    dt = datetime.fromisoformat(ts_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (dt + timedelta(hours=SYDNEY_OFFSET)).replace(tzinfo=None)


def main():
    out_path = ROOT / "docs" / "reports" / "alltime-timeline.png"

    db = Database(DB_PATH)
    skin_entries = db.list_log_entries(entry_type="flare")

    # Every individual severity reading, kept at its actual local timestamp
    points: list[tuple[datetime, int]] = []
    for e in skin_entries:
        sev = e.get("severity")
        if sev is None:
            continue
        points.append((to_local_datetime(e["timestamp"]), sev))
    points.sort()

    # Phase 4 average for annotation (all readings in the window)
    phase4_pts = [(dt, s) for dt, s in points if date(2026, 4, 12) <= dt.date() < date(2026, 4, 23)]
    phase4_avg = sum(s for _, s in phase4_pts) / len(phase4_pts) if phase4_pts else None

    fig, ax = plt.subplots(figsize=(40, 7))

    for phase in PHASES:
        ax.axvspan(
            mdates.date2num(phase["start"]),
            mdates.date2num(phase["end"]),
            color=phase["color"], alpha=0.85, zorder=0,
        )

    for zone in SEVERITY_ZONES:
        ax.axhspan(zone["ymin"], zone["ymax"], color=zone["color"], alpha=zone["alpha"], zorder=0)

    # Phase label boxes near the bottom
    from datetime import timedelta as _td
    for phase in PHASES:
        mid_ord = (phase["start"].toordinal() + phase["end"].toordinal()) / 2
        mid = date.fromordinal(int(mid_ord))
        ax.text(
            mdates.date2num(mid), 0.35,
            phase["box_label"],
            ha="center", va="bottom",
            fontsize=phase.get("fontsize", 9),
            color="#333333",
            bbox=dict(
                boxstyle="round,pad=0.35",
                facecolor=phase["color"],
                edgecolor="#aaaaaa",
                alpha=0.97,
                lw=0.9,
            ),
            zorder=8,
        )

    # Week boundary markers
    for monday in WEEK_MONDAYS:
        ax.axvline(
            mdates.date2num(monday),
            color="#888888", linewidth=0.7, linestyle="--", alpha=0.5, zorder=1,
        )
        ax.text(
            mdates.date2num(monday) + 0.1, 9.7,
            f"w/c {monday.strftime('%a %-d %b')}",
            fontsize=8, color="#999999", va="top",
        )

    # Individual readings, plotted at their real timestamp
    plot_dates = [mdates.date2num(dt) for dt, _ in points]
    plot_vals = [s for _, s in points]
    ax.plot(plot_dates, plot_vals, color="#444444", linewidth=1.0, alpha=0.7, zorder=3)
    ax.scatter(plot_dates, plot_vals, color="#e85a1e", s=42, zorder=4)

    # Phase 4 average line
    if phase4_avg and phase4_pts:
        x0 = mdates.date2num(phase4_pts[0][0])
        x1 = mdates.date2num(phase4_pts[-1][0])
        ax.annotate(
            "",
            xy=(x1, phase4_avg), xytext=(x0, phase4_avg),
            arrowprops=dict(arrowstyle="<->", color="#005a9e", lw=1.5),
            zorder=6,
        )
        ax.text(
            (x0 + x1) / 2, phase4_avg + 0.22,
            f"avg {phase4_avg:.1f}",
            ha="center", va="bottom", fontsize=12, color="#005a9e", fontweight="bold",
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
            fontsize=9.5,
            color=ann.get("color", "#333333"),
            fontweight=ann.get("weight", "normal"),
            arrowprops=dict(arrowstyle=ann["arrowstyle"], color="#555555", lw=0.9),
            bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="#aaaaaa", alpha=0.88, lw=0.7),
            zorder=7,
        )

    # Right-side zone labels
    x_label = mdates.date2num(date(2026, 6, 7)) + 0.3
    for zone in SEVERITY_ZONES:
        mid_y = (zone["ymin"] + zone["ymax"]) / 2
        ax.text(
            x_label, mid_y, zone["label"],
            fontsize=11, va="center", ha="left", color="#666666",
            clip_on=False,
        )

    ax.set_xlim(mdates.date2num(date(2026, 3, 22)), mdates.date2num(date(2026, 6, 7)))
    ax.set_ylim(0, 10)
    ax.xaxis.set_major_locator(DayLocator(interval=2))
    ax.xaxis.set_major_formatter(DateFormatter("%b %-d"))
    plt.xticks(rotation=0, ha="center", fontsize=12)
    plt.yticks(range(0, 11, 2), fontsize=12)
    ax.set_xlabel("Date (2026)", fontsize=14, labelpad=8)
    ax.set_ylabel("Severity (0–10 scale)", fontsize=14, labelpad=8)
    ax.grid(axis="y", linestyle="--", alpha=0.4, zorder=1)
    ax.tick_params(axis="both", which="major", labelsize=12)

    reading_dots = plt.scatter([], [], color="#e85a1e", s=42, label="Severity reading")
    ax.legend(handles=[reading_dots], loc="upper right", fontsize=10,
              framealpha=0.92, edgecolor="#cccccc")

    n_checks = len(points)
    n_days = len({dt.date() for dt, _ in points})
    plt.title(
        "Eczema Severity — Full Tracking Period (Mar 23 – Jun 6, 2026)",
        fontsize=18, fontweight="bold", pad=10,
    )
    plt.suptitle(
        f"Self-reported 0–10 scale · Lower = better · {n_checks} skin checks across {n_days} days with data",
        fontsize=11.5, y=0.97, color="#555555",
    )

    fig.subplots_adjust(left=0.05, right=0.83, top=0.88, bottom=0.10)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    main()
