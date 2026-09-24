# Run the bot 24/7 in a container:
#   docker build -t trading-bot .
#   docker run -d --restart unless-stopped --env-file .env \
#     -v "$PWD/state:/app/state" -v "$PWD/logs:/app/logs" trading-bot
# or simply: docker compose up -d
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY bot ./bot
COPY configs ./configs

RUN useradd --create-home --uid 1000 bot \
    && mkdir -p state logs \
    && chown -R bot:bot /app
USER bot

VOLUME ["/app/state", "/app/logs"]
ENTRYPOINT ["python", "-m", "bot"]
CMD ["-c", "configs/stocks.yaml", "run"]
