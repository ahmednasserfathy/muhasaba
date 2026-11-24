FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:0.10.8 /uv /usr/local/bin/uv

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --locked --no-dev
COPY app ./app
COPY alembic.ini ./
COPY alembic ./alembic

RUN useradd --create-home --uid 10001 app
USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
