#!/usr/bin/env python3
"""Uptime + SSL-expiry monitor. Checks every site in sites.json and stores real results.

Outputs
  data/checks/YYYY-MM-DD.jsonl   one record per run (history)
  data/checks/latest.json        newest record
  data/state.json                consecutive failures + open incidents
  .incident_actions.json         issues the workflow should open/close
  .commit_msg                    describes what this run found
"""
import json
import socket
import ssl
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CONFIG = ROOT / "sites.json"
UA = {"User-Agent": "uptime-monitor/1.0 (+github actions)"}
SSL_WARN_DAYS = 14
DOWN_THRESHOLD = 2  # consecutive failed runs before an incident is opened


def ssl_days_left(host, port=443, timeout=10):
    ctx = ssl.create_default_context()
    with socket.create_connection((host, port), timeout=timeout) as sock:
        with ctx.wrap_socket(sock, server_hostname=host) as tls:
            cert = tls.getpeercert()
    return int((ssl.cert_time_to_seconds(cert["notAfter"]) - time.time()) // 86400)


def check_site(site, retries=1):
    expect = site.get("expect_status")
    status, err, latency, ok = None, None, 0, False
    for _ in range(retries + 1):
        start = time.monotonic()
        try:
            req = urllib.request.Request(site["url"], headers=UA)
            with urllib.request.urlopen(req, timeout=site.get("timeout", 15)) as r:
                status = r.status
                r.read(1024)
            err = None
        except urllib.error.HTTPError as e:
            status, err = e.code, f"HTTP {e.code}"
        except Exception as e:  # network errors, timeouts, TLS errors
            status, err = None, f"{type(e).__name__}: {str(e)[:100]}"
        latency = int((time.monotonic() - start) * 1000)
        ok = status is not None and (status == expect if expect else 200 <= status < 400)
        if ok:
            break
    days = None
    parsed = urlparse(site["url"])
    if parsed.scheme == "https" and parsed.hostname:
        try:
            days = ssl_days_left(parsed.hostname, parsed.port or 443)
        except Exception:
            days = None
    return {"name": site["name"], "url": site["url"], "ok": ok, "status": status,
            "latency_ms": latency, "ssl_days_left": days, "error": err}


def evaluate_incidents(results, state):
    """Pure function: update failure counters and decide which incidents to open/close."""
    failures = dict(state.get("failures", {}))
    for r in results:
        failures[r["name"]] = 0 if r["ok"] else failures.get(r["name"], 0) + 1
    active = {}
    for r in results:
        if failures[r["name"]] >= DOWN_THRESHOLD:
            active[f"{r['name']} is DOWN"] = (
                f"{r['url']} failed {failures[r['name']]} checks in a row.\n\n"
                f"Last error: `{r['error']}` (status {r['status']}, {r['latency_ms']} ms)")
        d = r["ssl_days_left"]
        if d is not None and d < SSL_WARN_DAYS:
            active[f"{r['name']} SSL expires in {SSL_WARN_DAYS} days or less"] = (
                f"Certificate for {r['url']} expires in **{d} day(s)**. Renew it.")
    open_now = set(state.get("open", []))
    opens = [{"title": t, "body": b} for t, b in active.items() if t not in open_now]
    closes = sorted(t for t in open_now if t not in active)
    new_state = {"failures": failures, "open": sorted(active)}
    return new_state, {"opens": opens, "closes": closes}


def main():
    sites = json.loads(CONFIG.read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(check_site, sites))

    record = {"fetched_at": now.isoformat(timespec="seconds"), "results": results}
    out = DATA / "checks"
    out.mkdir(parents=True, exist_ok=True)
    (out / "latest.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    with open(out / f"{now:%Y-%m-%d}.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")

    state_file = DATA / "state.json"
    state = json.loads(state_file.read_text()) if state_file.exists() else {}
    state, actions = evaluate_incidents(results, state)
    state_file.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    (ROOT / ".incident_actions.json").write_text(json.dumps(actions), encoding="utf-8")

    up = sum(r["ok"] for r in results)
    avg = sum(r["latency_ms"] for r in results) // max(len(results), 1)
    down = [r["name"] for r in results if not r["ok"]]
    msg = f"monitor: {up}/{len(results)} sites up, avg {avg} ms [{now:%Y-%m-%d %H:%M} UTC]"
    if down:
        msg += f"\n\nDown this run: {', '.join(down)}"
    (ROOT / ".commit_msg").write_text(msg + "\n", encoding="utf-8")
    print(msg)


if __name__ == "__main__":
    main()
