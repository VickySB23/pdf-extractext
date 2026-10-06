# AGENTS.md

Repo: FastAPI PDF text-extraction backend, currently split into **two independent uv projects** (no workspace, no root `pyproject.toml`).

## Contexto del TP (leer primero)

TP de Desarrollo de Software (UTN San Rafael): microservicio `POST /extract`
que recibe un PDF y devuelve JSON `{"content": "<texto>", "page_count": N}`
con HTTP 200. Se evalúa con k6 (spike: 10s subida a 100 VUs, 20s sostenido,
10s bajada) y Vegeta (50 req/s durante 30s, timeout 30s) sobre los 4 PDFs de
`tests/stress/pdfs`. Ambos mandan el PDF como BODY BINARIO crudo con
`Content-Type: application/pdf` (no multipart).

Referencia de la cátedra a superar: k6 25.35 req/s con 0% error;
Vegeta 66.53% de éxito y p50 de 14.89 s.

Entorno de ejecución: docker compose, máximo 5 réplicas, 1 CPU y 512 MB
por réplica, reverse proxy (Traefik).

### Decisiones tomadas

- Se trabaja SOLO en `services/extraction-service`. NO tocar `document-service`
  ni MongoDB (son la primera etapa del proyecto y deben seguir funcionando).
- PyMuPDF es 12x-15x más rápido que pypdf (166 ms vs ~2100-2500 ms por PDF) y ya
  es la librería de extracción de `extraction-service`. `pypdf` queda como
  dependencia de DESARROLLO (los tests lo usan para armar el PDF cifrado).
- Decisión pendiente: texto plano vs Markdown real.
- Paso 2 HECHO: `/extract` acepta body crudo (cualquier Content-Type que no sea multipart, validado por firma %PDF-) y multipart; responde exactamente `{"content", "page_count"}`; PDF sin texto devuelve 200 con content vacío. Tests: 17 en extraction-service, 21 en document-service.
- Markdown HECHO: `content` es Markdown básico (títulos por tamaño de fuente, viñetas, párrafos) por defecto; `OUTPUT_FORMAT=text` devuelve texto plano. Costo medido: ~1,4x el texto plano (240 ms vs 172 ms). Se descartó pymupdf4llm por costo (3,7 s vs 23 ms en un PDF de 16 páginas). Tests: 57 en extraction-service.

### Reglas de trabajo

- Windows con PowerShell 5: no usar `&&`; usar `;` o comandos separados.
- Un objetivo por vez, cambios mínimos. ANTES de editar, explicar el plan
  y esperar confirmación.
- Cada cambio debe tener un test o un comando de verificación.
- Después de cada cambio, correr `uv run pytest -q` en el servicio y comprobar
  que los tests existentes siguen pasando (57 en extraction-service).
- Configuración por variables de entorno, logs a stdout (Twelve-Factor).
- No inventar resultados: si algo no se pudo ejecutar, decirlo.

## Layout: what actually runs

| Path | Reality |
| --- | --- |
| `services/document-service/` | Public API + CRUD. Own `pyproject.toml`/`uv.lock`/`.venv`/Dockerfile. Layered: `presentation` -> `application` -> `infrastructure`, plus `core` (settings, logger). Entrypoint `app.main:app`. |
| `services/extraction-service/` | Stateless `POST /extract` + `GET /health` on port **8001**. Deliberately flat: `app/main.py` + `app/pdf_service.py` (pure logic, no FastAPI). |
| `docker-compose.yml` | traefik (gateway, publishes `80` and dashboard `8080`), document-service (8000), extraction-service (8001, **no host port**), db (mongo:7.0, **no host port**). Two networks: `traefik-net`, `backend`. |
| `README.md`, `docs/architecture/**` | **STALE** — written for the pre-split monolith (`app/` at repo root, no Traefik, no extraction-service, roadmap explicitly says "don't build microservices"). Trust code, compose and `docs/diagnostico/informe-diagnostico.md`, not these. |
| `app/` at repo root | Only stale `__pycache__/*.pyc` leftovers from the old monolith (nvidia/summary code that no longer exists). Not source; ignore it and never edit it. |
| `tests/stress/` | Repo-root benchmark scripts + 4 committed PDFs (used by `tests/stress/pdfs/`). Not part of pytest. |

## Commands

Run uv commands **from inside the service directory** — there is no root project, and each service resolves its own `.venv`. A root `.venv` exists but uv ignores it (harmless `VIRTUAL_ENV ... does not match` warning).

```bash
cd services/extraction-service   # 17 tests
uv sync && uv run pytest -q

cd services/document-service     # 21 tests
uv sync && uv run pytest -q

# single test / file (from a service dir)
uv run pytest tests/test_api.py::test_extract_ok -q

# local dev servers
cd services/extraction-service && uv run uvicorn app.main:app --port 8001 --reload
cd services/document-service && uv run uvicorn app.main:app --reload   # needs a reachable MongoDB

# whole stack (dev only: bind mounts + uvicorn --reload + insecure Traefik dashboard)
docker compose up --build

# extractor benchmark (must run from repo root; pymupdf/pypdf are in neither project)
uv run --no-project --with pymupdf --with pypdf python tests/stress/bench_extractors.py
```

There is **no linter, formatter or typechecker** configured (no ruff/mypy/editorconfig/pre-commit). CI (`.github/workflows/ci.yml`) runs only `uv run pytest -q` per service (matrix) plus `docker compose build`. Don't invent a lint step and claim CI runs it.

## Known gaps — verify before "fixing"

These are real, verified breakages, not opinions. `docs/diagnostico/informe-diagnostico.md` lists them with evidence (written BEFORE step 2; some items below are updated).

- **The two services never talk to each other.** `document-service/app/main.py` wires the *local* `PDFService` (pypdf in-process via `asyncio.to_thread`), while `HttpTextExtractor` + `CircuitBreaker` (`app/infrastructure/clients/`) are only exercised by tests. `EXTRACTION_URL` exists in compose but is **not declared in `app/core/config.py`** and never read.
- **Two divergent extractors** existen: `document-service/app/application/services/pdf_service.py` lanza `ValueError` genérico; `extraction-service/app/pdf_service.py` lanza errores tipados (`invalid_pdf`/`encrypted_pdf`). Un PDF sin texto ya NO es error en extraction-service (200 con content vacío), mientras que `POST /api/documents` sigue devolviendo 400.
- **The router's error contract is `ValueError`-only** (`document_router.py` wraps `except ValueError` -> 400). `DocumentService` does not even import the `TextExtractor` Protocol. Wiring the remote extractor requires changing both layers (or the domain exceptions become 500s).
- **Public API ≠ TP contract.** La API pública de document-service es `POST /api/documents` -> `{id, original_filename, full_text, checksum, created_at}`. `extraction-service` YA cumple el contrato del TP (`POST /extract` -> `{content, page_count}`), pero NO es alcanzable por Traefik (la ruta solo cubre `PathPrefix(/api/documents) || Path(/health)`).
- `document-service/app/infrastructure/clients/http_text_extractor.py` (cliente no conectado al flujo real) sigue esperando el contrato viejo de extraction-service (`text/checksum/pages` y código `no_text`). No se arregla: está fuera del alcance del TP.
- `document-service` still uses `pypdf` (its own `pdf_service.py`), which is ~13-15x slower than `pymupdf` on the committed stress PDFs (`docs/mediciones/01-extractores.txt`). Only `extraction-service` migrated.
- Stale deps in `document-service/pyproject.toml`: `tinydb`, `python-dotenv`, `SECRET_KEY` (unused), `pytest` in runtime deps.

## Testing quirks

- No MongoDB, network or Docker needed for the suite: repository tests use `mongomock-motor.AsyncMongoMockClient`; HTTP tests use `TestClient` with `app.dependency_overrides[get_document_service]`.
- **Global state across test modules**: `tests/test_api.py` sets `dependency_overrides` and a shared `mock_service` at import time; `tests/test_health.py` overwrites `app.state.mongo_client`. Side effects on `side_effect`/`return_value` must be reset in the test itself. New modules can therefore leak into existing ones — prefer injecting fakes over mutating `app.state`.
- `pytest-asyncio` runs in strict mode (no `asyncio_mode` config in `document-service`): every async test needs an explicit `@pytest.mark.asyncio`.
- `document-service` has no `[tool.pytest.ini_options]`; `from app...` works because `tests/__init__.py` makes the tests a package and pytest prepends the service dir to `sys.path`. Keep that file.
- `extraction-service` sets `pythonpath = ["."]` and `testpaths = ["tests"]`; its `tests/conftest.py::build_pdf` hand-builds a minimal PDF (no reportlab/fixtures dependency) — reuse it instead of adding PDF fixtures. `cryptography` is a dev-only dependency (used to build an encrypted PDF in a test); never add it to runtime dependencies. `pypdf` is dev-only too (`test_extract_cifrado` uses it to build the encrypted PDF); extraction uses `pymupdf`.
- PyMuPDF behaviors that the code depends on: `pymupdf.open(stream=..., filetype="pdf")` raises `pymupdf.FileDataError` (subclass of `RuntimeError`) on non-PDF data; an encrypted PDF opens fine and must be detected with `doc.needs_pass`/`doc.is_encrypted` **before** reading (`get_text()` raises `ValueError: document closed or encrypted`); and MuPDF **repairs** damaged/truncated PDFs instead of failing, yielding `page_count == 0` — that guard in `extract_text` is what turns a corrupt PDF into `invalid_pdf` (do not remove it; two tests cover it).
- `extraction-service`'s Dockerfile has **no `--workers`**: uvicorn runs a single process, so `_EXTRACTION_LOCK` (PyMuPDF is not thread-safe) fully serializes extraction per container. Parallelism comes from replicas, not threads.
- Test counts to sanity-check after changes: 17 in extraction-service, 21 in document-service.

## Config / env gotchas

- `Settings` (`document-service/app/core/config.py`) reads `env_file=".env"` **relative to CWD**, so the repo-root `.env` is ignored whenever you run from a service dir or from Docker (`WORKDIR /app`, no `.env` copied). Compose injects env vars explicitly.
- `extraction-service` uses `os.getenv` only — **no `.env` loading at all** (`MAX_UPLOAD_SIZE_BYTES`).
- Env vars: `MONGO_URI`, `MONGO_DB_NAME`, `MAX_UPLOAD_SIZE_BYTES`, `UPLOAD_DIR` (created on startup relative to CWD, never used to store PDFs). Compose overrides Mongo to `db:27017` / `pdf_db`.
- The root `.env` is gitignored and still holds a commented-out `NVIDIA_API_KEY` from an abandoned feature. Never commit it; if that key was ever pushed, rotate it.
- Compose is dev-mode: it overrides both Dockerfiles' `CMD` with `--reload` (document-service's Dockerfile has `--workers 4`; extraction-service's does **not**), and `container_name` is pinned on all services, so `deploy.replicas` scaling is blocked until those are removed.

## Conventions

- Code, docstrings, user-facing error messages and `docs/` are in **Spanish**; keep it. Older docs are ASCII-only (no accents); newer code uses accents — match the file you are editing.
- Layer rules from the original architecture doc still hold: routers do HTTP-only validation, `DocumentService` depends on the `DocumentRepository` Protocol (not Mongo), Mongo details stay in `infrastructure/repositories/mongo_repository.py`.
- Commit messages are in Spanish, short imperative (`Separar monolito en document-service y extraction-service`).
- Branch naming: `tp/baseline`, `tp/paso2-contrato` (one branch per TP step, `tp/pasoN-descripcion`).