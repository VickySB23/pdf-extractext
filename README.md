# PDF Extractext - Etapa 1

Una API RESTful orientada a producción para la extracción de texto de archivos PDF, control de duplicados mediante checksum y persistencia en una base de datos NoSQL. 

Este proyecto está diseñado siguiendo estrictamente los requerimientos de la Etapa 1, aplicando los principios **SOLID, KISS, DRY y YAGNI**, e implementando una **Arquitectura Limpia (Clean Architecture)**.

---

## 🏗️ Descripción General de la Arquitectura

El proyecto presenta una clara separación de responsabilidades estructurada en el módulo raíz `app/`:

* **Capa 1: Presentación (`app/presentation/`)**
  * **Routers:** Manejadores de los endpoints HTTP (FastAPI) exponiendo el CRUD completo.
  * **Schemas:** Modelos Pydantic estrictos para la validación de solicitudes (DTOs) y respuestas.
  * *Regla:* Solo maneja el transporte HTTP, no contiene lógica de negocio.

* **Capa 2: Aplicación / Servicios (`app/application/`)**
  * **Services:** Orquestación de la lógica de negocio (`PDFService`, `DocumentService`).
  * **Interfaces:** Contratos abstractos (`DocumentRepository`) que definen el comportamiento esperado (Inversión de Dependencias).

* **Capa 3: Infraestructura (`app/infrastructure/`)**
  * **Repositories:** Capa de persistencia implementada con TinyDB (NoSQL).
  * *Regla:* La extracción se procesa directamente en memoria sin guardar archivos temporales en el disco.

---

## 🚀 Inicio Rápido (Desarrollo Local)

### Requisitos Previos
* Python 3.11+
* Herramienta `uv` (Gestor de dependencias de Astral.sh)

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
2. Ejecutar la Aplicación
Bash
# Iniciar el servidor de desarrollo usando uv
uv run uvicorn app.main:app --reload
👀 Cómo usar la API (Interfaz Interactiva)
Al ser una API RESTful pura, el proyecto no cuenta con pantallas tradicionales, sino que utiliza Swagger UI, una interfaz gráfica interactiva autogenerada por FastAPI que es el estándar de la industria para probar endpoints.

Una vez que el servidor esté corriendo en tu terminal, abre tu navegador web y dirígete a:
👉 http://localhost:8000/docs

Verás un panel con el título "Sistema de Gestión de Documentos PDF" y una lista de barras de colores que representan el CRUD (POST, GET, PUT, DELETE).

Para probar la extracción de un PDF:

Haz clic en la barra verde POST /api/documents.

Presiona el botón derecho que dice "Try it out" (Pruébalo).

Selecciona un archivo PDF de tu computadora en el campo de subida (file).

Haz clic en el botón azul "Execute" (Ejecutar).

En la sección de respuestas (Server Response), verás el código HTTP 200 de éxito y un JSON con el texto puro extraído, su Checksum SHA-256 (para control de duplicados) y el ID guardado en la base de datos local (documents_db.json).

📂 Estructura del Proyecto
Plaintext
pdf-extractext/
│
├── app/                                 # 📦 Código principal de la aplicación
│   ├── application/                     # ⚙️ Lógica de negocio (Casos de uso y Contratos)
│   │   ├── interfaces/
│   │   │   └── document_repository.py   # Contrato CRUD para la base de datos
│   │   ├── services/
│   │   │   ├── document_service.py      # Orquestador del flujo y reglas (Anti-duplicados)
│   │   │   └── pdf_service.py           # Lógica pura de extracción de texto PDF en memoria
│   │
│   ├── core/                            # 🔧 Configuraciones globales (Settings)
│   │
│   ├── infrastructure/                  # 🔌 Conexiones al mundo exterior (Base de datos)
│   │   └── repositories/
│   │       └── nosql_repository.py      # Persistencia en NoSQL usando TinyDB
│   │
│   ├── presentation/                    # 🌐 Interfaz hacia el usuario (API REST)
│   │   ├── routers/
│   │   │   └── document_router.py       # Endpoints REST (GET, POST, PUT, DELETE)
│   │   ├── schemas/
│   │   │   └── document_schema.py       # DTOs y validación de tipos con Pydantic
│   │   └── templates/
│   │       └── index.html               # Interfaz visual básica
│   │
│   └── main.py                          # Ensamblador de Inyección de Dependencias y Entrypoint
│
├── tests/                               # 🧪 Pruebas automatizadas (TDD)
│   ├── test_api.py                      # Pruebas de integración de Endpoints
│   ├── test_document_service.py         # Pruebas unitarias de orquestación
│   ├── test_nosql_repository.py         # Pruebas de base de datos
│   └── test_pdf_service.py              # Pruebas de extracción y checksum
│
├── documents_db.json                    # 💾 Base de datos física NoSQL autogenerada
├── pyproject.toml                       # Gestión de dependencias (uv)
└── README.md                            # Presentación y manual del proyecto
🧪 Metodología de Desarrollo: TDD
Este proyecto se construyó bajo el enfoque TDD (Test-Driven Development), garantizando una cobertura total de las reglas de negocio, incluyendo la verificación obligatoria para evitar el procesamiento de archivos duplicados.

Ejecutar Pruebas:

Bash
# Ejecutar toda la suite de pruebas unitarias y de integración
uv run pytest