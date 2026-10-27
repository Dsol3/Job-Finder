# Run the watcher anywhere that speaks Docker: Railway, Fly.io, a NAS, or any VPS.
#   docker build -t jobfinder .
#   docker run -d --restart=always \
#     -e TELEGRAM_BOT_TOKEN=123:ABC -e TELEGRAM_CHAT_ID=456 \
#     -v jobfinder-data:/app/state --name jobfinder jobfinder
FROM python:3.12-slim

WORKDIR /app
COPY job_finder/ ./job_finder/
COPY config.example.toml ./config.example.toml
COPY tests/fixtures/forhire_new.json ./tests/fixtures/forhire_new.json

# state lives on a volume so the dedupe memory survives restarts
RUN mkdir -p /app/state && cp config.example.toml config.toml \
    && sed -i 's#db_path = "seen.sqlite3"#db_path = "/app/state/seen.sqlite3"#; s#log_path = "matches.jsonl"#log_path = "/app/state/matches.jsonl"#' config.toml

ENV PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8

CMD ["python", "-m", "job_finder", "--loop", "--quiet"]
