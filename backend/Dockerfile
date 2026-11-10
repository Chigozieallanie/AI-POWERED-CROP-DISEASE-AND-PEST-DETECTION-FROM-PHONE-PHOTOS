FROM python:3.12-slim

RUN pip install --no-cache-dir uv
WORKDIR /srv

COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev

COPY backend/alembic.ini ./
COPY backend/migrations ./migrations
COPY backend/app ./app
COPY content /content

RUN useradd --create-home api && mkdir -p /data && chown api /data
USER api
ENV PATH="/srv/.venv/bin:$PATH"

EXPOSE 8000
# Access logs stay off because query strings can contain partner coordinates.
# One worker: the IP limiter and each model interpreter live in process memory.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.asgi:app --host 0.0.0.0 --port 8000 --no-access-log"]
