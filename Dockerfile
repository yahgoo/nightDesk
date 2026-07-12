FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

RUN mkdir -p logs

EXPOSE 8000

# The FastAPI server (app/server.py) serves /health, /api/status and the
# Telegram webhook, and can also boot the bot poller. For most hosts run the
# web server and point Telegram webhook at /webhook/telegram.
CMD ["python", "-m", "app.server"]
