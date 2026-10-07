FROM python:3.12-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:0.11.14 /uv /uvx /bin/

WORKDIR /app
ENV PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 PORT=8001

COPY pyproject.toml uv.lock* ./
RUN uv sync --no-dev

COPY app ./app

RUN useradd --system --uid 10001 --no-create-home app
USER app

EXPOSE 8001
# exec permite que uvicorn reciba las señales del contenedor.
CMD ["sh", "-c", "exec /app/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
