# syntax=docker/dockerfile:1

FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build
COPY requirements.txt .
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip \
    && /opt/venv/bin/pip install -r requirements.txt

FROM python:3.12-slim AS runtime

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.settings \
    DB_PATH=/data/db.sqlite3

RUN groupadd --system app \
    && useradd --system --gid app --home-dir /app --create-home app \
    && mkdir -p /app /data /app/staticfiles \
    && chown -R app:app /app /data

COPY --from=builder /opt/venv /opt/venv
WORKDIR /app
COPY --chown=app:app . .
COPY --chown=app:app docker/entrypoint.sh /usr/local/bin/todo-entrypoint
RUN chmod 755 /usr/local/bin/todo-entrypoint

USER app
EXPOSE 8000
ENTRYPOINT ["todo-entrypoint"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "60"]
