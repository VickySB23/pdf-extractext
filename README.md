# PDF Extractext

Una aplicación FastAPI orientada a producción para la extracción de texto de archivos PDF y su posterior sumarización mediante Inteligencia Artificial. 

Este proyecto está diseñado siguiendo estrictamente los principios SOLID, KISS, DRY y YAGNI, implementando una Arquitectura Limpia (Clean Architecture) de 3 capas y cumpliendo con los lineamientos de 12 Factor App (especialmente en el manejo de dependencias y la naturaleza stateless de los procesos).

---

## Descripción General de la Arquitectura

El proyecto presenta una clara separación de responsabilidades estructurada en el módulo raíz app/:

* Capa 1: Presentación (app/presentation/)
  * Routers: Manejadores de los endpoints HTTP (FastAPI).
  * Schemas: Modelos Pydantic estrictos para la validación de solicitudes y respuestas.
  * Regla: Solo maneja el transporte HTTP, no contiene lógica de negocio.

* Capa 2: Aplicación / Servicios (app/application/)
  * Services: Orquestación de la lógica de negocio (PDFService, SummaryService).
  * Interfaces: Contratos abstractos que definen el comportamiento esperado de la infraestructura (Inversión de Dependencias).

* Capa 3: Infraestructura (app/infrastructure/)
  * Repositories: Capa de persistencia (actualmente en memoria, preparado para inyectar bases de datos).
  * External Clients: Integración con proveedores externos (NVIDIA NIM API).
  * Regla: Aquí ocurren los efectos secundarios. Ningún archivo se guarda en el contenedor (diseño stateless). La extracción se procesa directamente en memoria.

* Core (app/core/)
  * Settings: Gestión centralizada de configuración mediante variables de entorno (Pydantic-Settings).

---

## Inicio Rápido (Desarrollo Local)

### Requisitos Previos
* Python 3.11+
* Herramienta uv (Gestor de dependencias de Astral.sh)

### 1. Clonar y Configurar el Entorno

```bash
# Navegar al directorio del proyecto
cd pdf-extractext

# Sincronizar dependencias y crear el entorno virtual automáticamente con uv
uv sync

# Activar el entorno virtual
# En Windows:
.venv\Scripts\activate
# En macOS/Linux:
source .venv/bin/activate

2. Variables de Entorno
Crear el archivo .env en la raíz del proyecto para cumplir con el principio de configuración estricta de entornos:

Bash
cp .env.example .env
(Asegúrate de configurar NVIDIA_API_KEY en tu archivo local).

3. Ejecutar la Aplicación
Bash
# Iniciar el servidor de desarrollo usando uv
uv run uvicorn app.main:app --reload
Documentación Interactiva (Swagger): http://localhost:8000/docs

Verificación de Estado: http://localhost:8000/api/health

Estructura del Proyecto
Plaintext
pdf-extractext/
│
├── app/                                 # 📦 Código principal de la aplicación
│   ├── application/                     # ⚙️ Lógica de negocio (Casos de uso y Contratos)
│   │   ├── interfaces/
│   │   │   ├── ai_provider.py           # Contrato para la IA
│   │   │   └── summary_repository.py    # Contrato para la base de datos
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── pdf_service.py           # Lógica de extracción de PDFs
│   │   │   └── summary_service.py       # Orquestador del flujo
│   │   └── __init__.py
│   │
│   ├── core/                            # 🔧 Configuraciones globales (Settings)
│   │   └── __init__.py
│   │
│   ├── infrastructure/                  # 🔌 Conexiones al mundo exterior (BD y APIs)
│   │   ├── external/
│   │   │   └── nvidia_client.py         # Implementación de Nvidia NIM
│   │   ├── repositories/
│   │   │   ├── in_memory_repository.py  # (Opcional) Persistencia en RAM
│   │   │   └── nosql_repository.py      # Persistencia con TinyDB
│   │   └── __init__.py
│   │
│   ├── presentation/                    # 🌐 Interfaz hacia el usuario (API y Frontend)
│   │   ├── routers/
│   │   │   └── pdf_summary.py           # Endpoints REST (POST, GET, DELETE)
│   │   ├── schemas/
│   │   │   └── pdf_summary.py           # DTOs y validación con Pydantic
│   │   ├── templates/
│   │   │   └── index.html               # Frontend visual
│   │   └── __init__.py
│   │
│   └── main.py                          # Punto de entrada de FastAPI y ensamblaje
│
├── docs/                                # 📚 Documentación del proyecto
│   ├── estructura.md
│   └── image.png
│
├── tests/                               # 🧪 Pruebas unitarias y de integración (TDD)
│   ├── test_api.py
│   ├── test_nosql_repository.py
│   ├── test_pdf_service.py
│   └── test_summary_service.py
│
├── .gitignore                           # Exclusiones de Git (ej. .venv, pycache)
├── LICENSE                              # Licencia del proyecto
├── README.md                            # Presentación y manual del proyecto
├── main.py                              # (Parece un entrypoint raíz adicional o antiguo)
├── pyproject.toml                       # Gestión de dependencias (uv/pip)
├── summaries_db.json                    # 💾 Tu base de datos NoSQL física (TinyDB)
└── uv.lock                              # Bloqueo de versiones de dependencias
Metodología de Desarrollo: TDD
Este proyecto se construye obligatoriamente bajo el enfoque TDD (Test-Driven Development): Red -> Green -> Refactor.

Ejecutar Pruebas
Bash
# Ejecutar todas las pruebas unitarias
uv run pytest

# Ejecutar con detalles
uv run pytest -v


#Encender el server (no esta probado)
uv run uvicorn app.main:app --reload