# PDF Extractext - API de Grado de Producción

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