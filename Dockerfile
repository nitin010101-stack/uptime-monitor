FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN useradd --create-home --uid 10001 app
WORKDIR /app
COPY scripts/ scripts/
COPY sites.json .
RUN mkdir -p data && chown -R app:app /app
USER app

HEALTHCHECK NONE
ENTRYPOINT ["sh", "-c", "python scripts/monitor.py && python scripts/report.py"]
