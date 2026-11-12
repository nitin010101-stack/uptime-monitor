.PHONY: maintain install lint test check report docker-build docker-run clean

install:
	pip install -r requirements-dev.txt

lint:
	ruff check .

test:
	pytest -q

check:
	python scripts/monitor.py

report:
	python scripts/report.py

maintain:
	FORCE_MAINTAIN=true python scripts/maintain.py $(TASK)

docker-build:
	docker build -t uptime-monitor:local .

docker-run:
	docker compose run --rm collector

clean:
	rm -rf .last_source .pytest_cache .ruff_cache __pycache__ .commit_msg
