FROM python:3.12-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:0.11.14 /uv /uvx /bin/

WORKDIR /app
ENV PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 PORT=8001

# Primero las dependencias (mejor cache de capas)
COPY pyproject.toml uv.lock* ./
RUN uv sync --no-dev

COPY app ./app

# Proceso sin privilegios de administrador
RUN useradd --system --uid 10001 --no-create-home app
USER app

EXPOSE 8001
# Port binding por variable de entorno (Twelve-Factor); exec para que reciba las señales
CMD ["sh", "-c", "exec /app/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]