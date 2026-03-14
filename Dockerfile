# syntax=docker/dockerfile:1.6
FROM python:3.12-bookworm

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false \
    PYTHONPATH=/app/src \
    MOTOR_CONFIG_PATH=/app/config/config.yml

RUN apt-get update && apt-get install -y --no-install-recommends git \
 && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir poetry

COPY pyproject.toml poetry.lock* ./
RUN --mount=type=cache,target=/root/.cache/pypoetry \
    --mount=type=cache,target=/root/.cache/pip \
    poetry install --only main --no-root

COPY config ./config
COPY src ./src

CMD ["python", "-m", "capstone_motor.main"]
