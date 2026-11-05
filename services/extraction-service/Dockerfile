FROM python:3.12-slim-trixie AS builder
COPY --from=ghcr.io/astral-sh/uv:0.11.14 /uv /bin/

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

FROM python:3.12-slim-trixie

WORKDIR /app
ENV PYTHONUNBUFFERED=1

COPY --from=builder /app/.venv ./.venv
COPY app ./app

# La imagen final no instala paquetes: pip solo sumaría superficie de ataque.
RUN pip uninstall -y pip && useradd --system --uid 10001 --no-create-home app
USER app

EXPOSE 8001
HEALTHCHECK --interval=5s --timeout=3s --start-period=5s --retries=10 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8001/health')"]
CMD ["/app/.venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
