#!/usr/bin/env python3
"""Daily maintenance on a 5-day rotation, run after the last check of the day.

  0  reports/YYYY-MM-DD.md       NEW file   per-site uptime summary for the day
  1  charts/latency.svg          NEW/updated  average latency trend over history
  2  data/INDEX.json             UPDATED    index of every data file + row counts
  3  archive/checks/*.gz         MOVES old  gzip check files older than 3 days
  4  docs/STATS.md + CHANGELOG   UPDATED    all-time uptime per site + changelog
"""
import gzip
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECKS = ROOT / "data" / "checks"
ARCHIVE = ROOT / "archive" / "checks"


def iter_records():
    """Every stored record, oldest first, from archive and live files."""
    if ARCHIVE.exists():
        for p in sorted(ARCHIVE.glob("*.jsonl.gz")):
            with gzip.open(p, "rt", encoding="utf-8") as f:
                yield from (json.loads(x) for x in f if x.strip())
    for p in sorted(CHECKS.glob("????-??-??.jsonl")):
        with open(p, encoding="utf-8") as f:
            yield from (json.loads(x) for x in f if x.strip())


def uptime_by_site(records):
    agg = {}
    for rec in records:
        for r in rec["results"]:
            a = agg.setdefault(r["name"], [0, 0])
            a[0] += r["ok"]
            a[1] += 1
    return agg


def task_report(now):
    day = f"{now:%Y-%m-%d}"
    recs = [r for r in iter_records() if r["fetched_at"].startswith(day)]
    lines = [f"# Uptime summary {day}", "", f"{len(recs)} check run(s)", ""]
    for name, (up, total) in sorted(uptime_by_site(recs).items()):
        lines.append(f"- **{name}**: {up}/{total} checks passed ({100 * up / total:.1f}%)")
    (ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "reports" / f"{day}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return f"add uptime summary for {day}"


def task_chart(now):
    pts = [sum(x["latency_ms"] for x in r["results"]) / max(len(r["results"]), 1) for r in iter_records()]
    if len(pts) < 2:
        return None
    lo, hi = min(pts), max(pts)
    span = (hi - lo) or 1
    w, h = 600, 200
    xy = [(10 + i * (w - 20) / (len(pts) - 1), h - 20 - (v - lo) / span * (h - 40)) for i, v in enumerate(pts)]
    poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in xy)
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">'
           f'<rect width="100%" height="100%" fill="white"/>'
           f'<polyline fill="none" stroke="#0969da" stroke-width="2" points="{poly}"/>'
           f'<text x="10" y="14" font-size="12">avg latency ms: low {lo:.0f} high {hi:.0f} ({len(pts)} runs)</text></svg>\n')
    (ROOT / "charts").mkdir(exist_ok=True)
    (ROOT / "charts" / "latency.svg").write_text(svg, encoding="utf-8")
    return f"redraw latency chart ({len(pts)} runs)"


def task_index(now):
    live = {p.name: sum(1 for _ in open(p, encoding="utf-8")) for p in sorted(CHECKS.glob("????-??-??.jsonl"))}
    archived = sorted(p.name for p in ARCHIVE.glob("*.gz")) if ARCHIVE.exists() else []
    (ROOT / "data" / "INDEX.json").write_text(json.dumps({"live": live, "archived": archived}, indent=2) + "\n",
                                              encoding="utf-8")
    return f"refresh data index ({len(live)} live, {len(archived)} archived)"


def task_archive(now):
    cutoff = (now - timedelta(days=3)).strftime("%Y-%m-%d")
    moved = 0
    for p in sorted(CHECKS.glob("????-??-??.jsonl")):
        if p.stem < cutoff:
            ARCHIVE.mkdir(parents=True, exist_ok=True)
            with open(p, "rb") as src, gzip.open(ARCHIVE / f"{p.name}.gz", "wb") as dst:
                dst.write(src.read())
            p.unlink()
            moved += 1
    return f"archive {moved} old check file(s) to gzip" if moved else None


def task_stats(now):
    recs = list(iter_records())
    lines = ["# All-time statistics", "", f"_Updated {now:%Y-%m-%d} UTC, {len(recs)} check runs_", "",
             "| Site | Checks | Uptime |", "|---|---|---|"]
    for name, (up, total) in sorted(uptime_by_site(recs).items()):
        lines.append(f"| {name} | {total} | {100 * up / total:.2f}% |")
    (ROOT / "docs").mkdir(exist_ok=True)
    (ROOT / "docs" / "STATS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    log, head = ROOT / "CHANGELOG.md", "# Changelog\n\n"
    body = log.read_text(encoding="utf-8").removeprefix(head) if log.exists() else ""
    log.write_text(head + f"- {now:%Y-%m-%d}: stats updated, {len(recs)} runs recorded\n" + body, encoding="utf-8")
    return f"update stats and changelog ({len(recs)} runs)"


TASKS = [task_report, task_chart, task_index, task_archive, task_stats]


def is_last_run_of_day(hour):
    """Runs happen at 00,03,06,09,12,15 UTC; the 6th slot is the last. +1 tolerates delays."""
    return ((hour + 1) // 3) % 6 == 5


def main():
    now = datetime.now(timezone.utc)
    forced = os.environ.get("FORCE_MAINTAIN") == "true"
    if not forced and not is_last_run_of_day(now.hour):
        print("not the last run of the day, skipping maintenance")
        return
    idx = int(sys.argv[1]) if len(sys.argv) > 1 else now.toordinal() % len(TASKS)
    task = TASKS[idx]
    note = task(now)
    if note:
        msg = ROOT / ".commit_msg"
        base = msg.read_text(encoding="utf-8").rstrip("\n") if msg.exists() else "chore: maintenance"
        msg.write_text(f"{base}\n\nmaintenance({task.__name__[5:]}): {note}\n", encoding="utf-8")
        print(note)


if __name__ == "__main__":
    main()
