# uptime-monitor

[![monitor](https://github.com/nitin010101-stack/uptime-monitor/actions/workflows/monitor.yml/badge.svg)](https://github.com/nitin010101-stack/uptime-monitor/actions/workflows/monitor.yml)
[![ci](https://github.com/nitin010101-stack/uptime-monitor/actions/workflows/ci.yml/badge.svg)](https://github.com/nitin010101-stack/uptime-monitor/actions/workflows/ci.yml)

A small uptime and TLS-expiry monitor that runs entirely on GitHub Actions. Every three hours it requests each URL in `sites.json`, records the status code, response time and certificate expiry, publishes a status page, and opens a GitHub issue when a site stays down or a certificate is close to expiring. Results are committed to the repository, so the history lives in git and there is no server or database to run.

Status page: https://nitin010101-stack.github.io/uptime-monitor/

## How it works

The `monitor` workflow runs six times a day, at 17 minutes past 00, 03, 06, 09, 12 and 15 UTC. Each run does the following:

1. `scripts/monitor.py` checks every site in parallel. A failed request is retried once. For HTTPS sites it also reads the certificate and works out how many days are left.
2. The run is appended to `data/checks/YYYY-MM-DD.jsonl`, and the newest run is written to `data/checks/latest.json`.
3. `scripts/maintain.py` runs one housekeeping task, but only on the last run of the day (see below).
4. `scripts/report.py` rebuilds `REPORT.md` and the status page in `docs/index.html`.
5. The changes are committed and pushed. The commit message says what the run found, for example `monitor: 10/11 sites up, avg 240 ms`.
6. Issues are opened or closed based on `data/state.json`.

### Incident rules

- A site that fails two runs in a row opens an issue titled `[incident] <name> is DOWN`. One failed run is not enough, to avoid noise from a single timeout.
- A certificate with fewer than 14 days left opens an issue.
- An issue is closed automatically with a comment once its condition clears.

The thresholds are the constants `DOWN_THRESHOLD` and `SSL_WARN_DAYS` at the top of `scripts/monitor.py`.

### Daily housekeeping

`maintain.py` cycles through five tasks, one per day, selected by the date:

| Task | Result |
|---|---|
| report | writes `reports/YYYY-MM-DD.md` with per-site uptime for that day |
| chart | redraws `charts/latency.svg` from the average latency of every run |
| index | refreshes `data/INDEX.json`, listing data files and row counts |
| archive | compresses check files older than three days into `archive/checks/` |
| stats | updates `docs/STATS.md` (all-time uptime per site) and `CHANGELOG.md` |

Its output is added to the same commit as that run's check results.

## Configuration

Sites are listed in `sites.json`:

```json
[
  {"name": "GitHub", "url": "https://github.com"},
  {"name": "My API", "url": "https://api.example.com/health", "expect_status": 200, "timeout": 10}
]
```

| Field | Required | Meaning |
|---|---|---|
| `name` | yes | Label used in reports and issue titles |
| `url` | yes | Address to request |
| `expect_status` | no | Exact status code that counts as healthy. Default: any code from 200 to 399 |
| `timeout` | no | Seconds before a request is abandoned. Default: 15 |

## Setup

1. Fork or clone the repository. It must not be a fork if you want the commits to appear on your contribution graph.
2. Under **Settings > Actions > General > Workflow permissions**, select **Read and write permissions**. The workflow needs this to push commits and open issues.
3. Under **Settings > Secrets and variables > Actions > Variables**, add `GIT_USER_NAME` and `GIT_USER_EMAIL`. Use an email address that is verified on your GitHub account, otherwise the commits are attributed to `github-actions[bot]`.
4. Under **Settings > Pages**, deploy from the `main` branch, `/docs` folder.
5. Open the **Actions** tab, choose **monitor**, and run it once manually. Tick `maintain` to run the housekeeping task as well.

After that the schedule runs by itself.

## Running locally

Python 3.10 or newer, standard library only for the monitor itself.

```
python scripts/monitor.py      # check all sites, write data/ and .commit_msg
python scripts/report.py       # rebuild REPORT.md and docs/index.html
FORCE_MAINTAIN=true python scripts/maintain.py 0    # run housekeeping task 0 to 4
```

Tests:

```
pip install pytest
python -m pytest
```

A `Dockerfile` and `docker-compose.yml` are included. `k8s/cronjob.yaml` is a Kubernetes CronJob with the same schedule and a persistent volume for `data/`. Replace `OWNER` in the image name before using it.

## Repository layout

```
scripts/        monitor.py, report.py, maintain.py
tests/          unit tests for incident logic, reports and housekeeping
sites.json      the list of monitored URLs
data/           check history and incident state (written by the workflow)
docs/           status page and statistics (served by GitHub Pages)
reports/        daily summaries
charts/         latency chart
archive/        compressed older history
.github/        workflows: monitor, ci, codeql, release; dependabot config
k8s/            Kubernetes CronJob manifest
```

## Record format

Each line of a `YYYY-MM-DD.jsonl` file is one run:

```json
{
  "fetched_at": "2026-11-12T03:17:08+00:00",
  "results": [
    {"name": "GitHub", "url": "https://github.com", "ok": true, "status": 200,
     "latency_ms": 212, "ssl_days_left": 61, "error": null}
  ]
}
```

## Limitations

- GitHub's scheduler is not exact. Runs often start several minutes late and are occasionally skipped, so a day can have fewer than six checks.
- With a three-hour interval, an outage shorter than that can go unnoticed. Use a dedicated service if you need minute-level detection.
- Requests originate from GitHub's hosted runners, so results show availability from there, not from every region.
- GitHub disables scheduled workflows in public repositories after 60 days without repository activity. The workflow's own commits normally count as activity. If it is ever disabled, re-enable it from the Actions tab.
- Actions minutes are unlimited for public repositories. A private repository uses roughly 100 minutes a month of the free allowance.

## Other workflows

- `ci.yml` compiles the scripts, runs a lint pass for real errors, validates `sites.json`, runs the tests and builds the Docker image.
- `codeql.yml` runs CodeQL analysis on pushes and weekly.
- `release.yml` creates a tagged release every Sunday and pushes the image to the GitHub Container Registry.
- Dependabot opens one grouped pull request a month per ecosystem.
