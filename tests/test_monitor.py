import gzip
import json
from datetime import datetime, timezone

import maintain
import monitor
import report


def res(name, ok=True, ssl_days=90):
    return {"name": name, "url": f"https://{name}.test", "ok": ok, "status": 200 if ok else None,
            "latency_ms": 100, "ssl_days_left": ssl_days, "error": None if ok else "Timeout"}


def test_incident_needs_two_failures():
    state, actions = monitor.evaluate_incidents([res("a", ok=False)], {})
    assert actions["opens"] == []  # first failure only counted
    state, actions = monitor.evaluate_incidents([res("a", ok=False)], state)
    assert [o["title"] for o in actions["opens"]] == ["a is DOWN"]


def test_incident_closes_on_recovery():
    state = {"failures": {"a": 2}, "open": ["a is DOWN"]}
    state, actions = monitor.evaluate_incidents([res("a", ok=True)], state)
    assert actions["closes"] == ["a is DOWN"] and state["open"] == []


def test_ssl_warning_opens_issue_once():
    state, actions = monitor.evaluate_incidents([res("a", ssl_days=5)], {})
    assert len(actions["opens"]) == 1
    state, actions = monitor.evaluate_incidents([res("a", ssl_days=4)], state)
    assert actions["opens"] == []


def test_status_page_renders(monkeypatch, tmp_path):
    monkeypatch.setattr(report, "CHECKS", tmp_path)
    rec = {"fetched_at": "2026-11-12T00:00:00+00:00", "results": [res("a"), res("b", ok=False)]}
    (tmp_path / "latest.json").write_text(json.dumps(rec))
    now = datetime(2026, 11, 12, tzinfo=timezone.utc)
    (tmp_path / "2026-11-12.jsonl").write_text(json.dumps(rec) + "\n")
    page = report.build_html(now)
    assert "Some systems have problems" in page and "DOWN" in page


def test_maintenance_tasks(monkeypatch, tmp_path):
    checks = tmp_path / "data" / "checks"
    checks.mkdir(parents=True)
    monkeypatch.setattr(maintain, "ROOT", tmp_path)
    monkeypatch.setattr(maintain, "CHECKS", checks)
    monkeypatch.setattr(maintain, "ARCHIVE", tmp_path / "archive" / "checks")
    for day in ("2026-11-01", "2026-11-12"):
        rec = {"fetched_at": f"{day}T00:00:00+00:00", "results": [res("a")]}
        (checks / f"{day}.jsonl").write_text(json.dumps(rec) + "\n")
    now = datetime(2026, 11, 12, tzinfo=timezone.utc)
    assert maintain.task_archive(now).startswith("archive 1")
    assert gzip.open(tmp_path / "archive" / "checks" / "2026-11-01.jsonl.gz").read()
    assert len(list(maintain.iter_records())) == 2
    assert "2 runs" in maintain.task_chart(now)
    assert "refresh data index" in maintain.task_index(now)
    assert "update stats" in maintain.task_stats(now)
    assert maintain.task_report(now).endswith("2026-11-12")


def test_last_run_slot():
    assert [maintain.is_last_run_of_day(h) for h in (0, 3, 6, 9, 12, 15, 16)] == [False] * 5 + [True, True]
