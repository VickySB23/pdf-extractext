FROM python:3.12-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
ENV PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1

# Primero las dependencias (mejor cache de capas)
COPY pyproject.toml uv.lock* ./
RUN uv sync --no-dev

COPY app ./app

EXPOSE 8001
CMD ["uv", "run", "--no-dev", "--no-sync", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]