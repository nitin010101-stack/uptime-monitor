#!/usr/bin/env python3
"""Build REPORT.md and the static status page docs/index.html from collected checks."""
import html
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECKS = ROOT / "data" / "checks"


def todays_records(now):
    p = CHECKS / f"{now:%Y-%m-%d}.jsonl"
    if not p.exists():
        return []
    return [json.loads(line) for line in open(p, encoding="utf-8") if line.strip()]


def summarize(now):
    latest_p = CHECKS / "latest.json"
    latest = json.loads(latest_p.read_text()) if latest_p.exists() else {"results": [], "fetched_at": "-"}
    today = todays_records(now)
    rows = []
    for r in latest["results"]:
        hist = [x for rec in today for x in rec["results"] if x["name"] == r["name"]]
        up = sum(x["ok"] for x in hist)
        pct = round(100 * up / len(hist), 1) if hist else None
        rows.append({**r, "uptime_today": pct, "checks_today": len(hist)})
    return latest["fetched_at"], rows


def build_markdown(now):
    fetched, rows = summarize(now)
    lines = ["# Status", "", f"_Last check {fetched} UTC_", "",
             "| Site | State | Latency | Uptime today | SSL days left |", "|---|---|---|---|---|"]
    for r in rows:
        state = "UP" if r["ok"] else "DOWN"
        lines.append(f"| {r['name']} | {state} | {r['latency_ms']} ms | "
                     f"{r['uptime_today'] if r['uptime_today'] is not None else '-'}% | {r['ssl_days_left']} |")
    return "\n".join(lines) + "\n"


def build_html(now):
    fetched, rows = summarize(now)
    all_up = bool(rows) and all(r["ok"] for r in rows)
    banner = "All systems operational" if all_up else "Some systems have problems"
    body = ""
    for r in rows:
        cls = "up" if r["ok"] else "down"
        ssl_txt = "-" if r["ssl_days_left"] is None else f"{r['ssl_days_left']}d"
        body += (f"<tr><td>{html.escape(r['name'])}</td><td class='{cls}'>{'UP' if r['ok'] else 'DOWN'}</td>"
                 f"<td>{r['latency_ms']} ms</td><td>{r['uptime_today'] if r['uptime_today'] is not None else '-'}%</td>"
                 f"<td>{ssl_txt}</td></tr>")
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Status</title>
<style>
:root{{--bg:#fff;--fg:#1a1a1a;--line:#ddd;--ok:#1a7f37;--bad:#cf222e}}
@media (prefers-color-scheme:dark){{:root{{--bg:#0d1117;--fg:#e6edf3;--line:#30363d;--ok:#3fb950;--bad:#f85149}}}}
body{{font:16px system-ui,sans-serif;background:var(--bg);color:var(--fg);max-width:760px;margin:2rem auto;padding:0 1rem}}
table{{width:100%;border-collapse:collapse}}th,td{{text-align:left;padding:.5rem;border-bottom:1px solid var(--line)}}
.up{{color:var(--ok);font-weight:600}}.down{{color:var(--bad);font-weight:600}}.banner{{font-size:1.3rem;margin:1rem 0}}
</style></head><body><h1>Service status</h1>
<div class="banner {'up' if all_up else 'down'}">{banner}</div>
<table><tr><th>Site</th><th>State</th><th>Latency</th><th>Uptime today</th><th>SSL</th></tr>{body}</table>
<p>Last check: {html.escape(fetched)} UTC. Page updated {now:%Y-%m-%d %H:%M} UTC.</p></body></html>
"""


if __name__ == "__main__":
    now = datetime.now(timezone.utc)
    (ROOT / "REPORT.md").write_text(build_markdown(now), encoding="utf-8")
    (ROOT / "docs").mkdir(exist_ok=True)
    (ROOT / "docs" / "index.html").write_text(build_html(now), encoding="utf-8")
    print("REPORT.md and docs/index.html written")
