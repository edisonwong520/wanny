FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

RUN apt-get update -o Acquire::Retries=5 \
    && apt-get install -y --no-install-recommends -o Acquire::Retries=5 \
        build-essential \
        curl \
        default-libmysqlclient-dev \
        pkg-config \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv

COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY backend/ ./

EXPOSE 8000

CMD ["sh", "-c", "uv run python manage.py migrate && uv run daphne -b 0.0.0.0 -p 8000 wanny_server.asgi:application"]
