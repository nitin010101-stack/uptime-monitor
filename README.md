# uptime-monitor

A free, serverless uptime and SSL-expiry monitor that runs on GitHub Actions.

**Problem it solves:** you want to know when your websites or APIs go down or
when a TLS certificate is about to expire, without paying for a monitoring
service or running a server.

## How it works
- Every 3 hours (6x/day) the workflow checks every URL in `sites.json`:
  status code, latency (with one retry), and days until the SSL certificate expires.
- Results are committed to `data/checks/`, building a public history of your uptime.
- A site that fails 2 runs in a row opens a GitHub Issue labelled `incident`;
  the issue closes itself on recovery. SSL certificates expiring in under 14 days
  open an issue too.
- `docs/index.html` is a live status page (enable GitHub Pages from `main` / `docs`).
- A daily maintenance task (5-day rotation) writes uptime reports, draws a latency
  chart, indexes and gzip-archives old data, and keeps all-time stats.

## Add your own sites (optional)
The default list monitors well-known public services, so it works with no sites of your own.
Once your status page is live, add it too: `{"name": "My status page", "url": "https://YOUR_USERNAME.github.io/uptime-monitor/"}`.

Edit `sites.json`:
```json
{"name": "My API", "url": "https://api.example.com/health", "expect_status": 200}
```

## DevOps stack
GitHub Actions (cron, CI), ruff + pytest, Docker (non-root), Trivy, CodeQL,
Dependabot, weekly releases to GHCR, Kubernetes CronJob, Makefile, pre-commit.

## Setup
1. Push to GitHub (not a fork), branch `main`.
2. Settings > Actions > General > Workflow permissions > Read and write.
3. Settings > Secrets and variables > Actions > Variables: `GIT_USER_NAME`, `GIT_USER_EMAIL`.
4. Settings > Pages > Deploy from branch > `main` / `docs`.
5. Actions > monitor > Run workflow (tick `maintain` to test maintenance).

## Local
```
make install && make lint test
make check && make report
make maintain TASK=0
```
