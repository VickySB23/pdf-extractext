# Arquitectura General

## Vista general

PDF ExtractText es un backend monolitico construido con FastAPI. La aplicacion se despliega como una unica unidad ejecutable que contiene los routers HTTP, servicios de aplicacion, contratos, configuracion e implementacion de persistencia.

Aunque es un monolito, el codigo esta organizado en capas para reducir acoplamiento y facilitar mantenimiento.

## Capas

### Presentation

Ubicacion: `app/presentation/`

Responsabilidades actuales:

- exponer endpoints HTTP;
- recibir `UploadFile` y requests JSON;
- validar condiciones de entrada propias de HTTP;
- convertir errores de negocio a respuestas HTTP;
- declarar modelos de entrada y salida con Pydantic;
- obtener `DocumentService` desde `request.app.state`.

Componentes principales:

- `document_router.py`;
- `health_router.py`;
- `document_schema.py`.

### Application

Ubicacion: `app/application/`

Responsabilidades actuales:

- contener la logica de caso de uso;
- definir el contrato de persistencia `DocumentRepository`;
- definir la entidad de transferencia interna `DocumentRecord`;
- coordinar extraccion, checksum, deteccion de duplicados y guardado;
- abstraer al dominio de FastAPI y MongoDB.

Componentes principales:

- `DocumentService`;
- `PDFService`;
- `DocumentRepository`;
- `DocumentRecord`;
- `ExtractedPDF`.

### Infrastructure

Ubicacion: `app/infrastructure/`

Responsabilidades actuales:

- implementar persistencia real en MongoDB;
- mapear documentos entre MongoDB y `DocumentRecord`;
- encapsular operaciones sobre la coleccion `documents`;
- ocultar detalles de `motor` a la capa de aplicacion.

Componente principal:

- `MongoDocumentRepository`.

### Core

Ubicacion: `app/core/`

Responsabilidades actuales:

- cargar configuracion con Pydantic Settings;
- leer `.env` en desarrollo;
- proveer valores por defecto;
- centralizar logging basico de la aplicacion.

Componentes principales:

- `Settings`;
- `get_settings`;
- `logger`.

### Application assembly

Ubicacion: `app/main.py`

Responsabilidades actuales:

- crear la instancia FastAPI;
- crear `AsyncIOMotorClient`;
- seleccionar la base de datos configurada;
- crear `PDFService`;
- crear `MongoDocumentRepository`;
- inyectar ambos en `DocumentService`;
- guardar servicios en `app.state`;
- registrar routers;
- cerrar el cliente MongoDB al finalizar el ciclo de vida.

## Flujo de dependencias

El flujo principal de dependencias es:

```text
FastAPI app
  -> presentation routers
  -> application services
  -> application interfaces
  <- infrastructure repository implementation
  -> MongoDB
```

La capa de aplicacion depende del contrato `DocumentRepository`, no de MongoDB directamente. La implementacion concreta `MongoDocumentRepository` se crea en `app/main.py` y se inyecta en `DocumentService`.

`PDFService` es un servicio de aplicacion usado por `DocumentService`. No depende de FastAPI ni de MongoDB.

## Principios aplicados

### KISS

El sistema mantiene una responsabilidad acotada: extraer texto nativo de PDFs y persistirlo. No agrega OCR, colas, microservicios, almacenamiento de binarios ni autenticacion porque el backend actual no los necesita para cumplir el flujo principal.

### DRY

La extraccion de texto y el calculo de checksum estan centralizados en `PDFService`. La persistencia esta centralizada en `MongoDocumentRepository`. Las rutas delegan logica de negocio en `DocumentService` en lugar de repetirla.

### SOLID

- Single Responsibility: routers manejan HTTP, servicios manejan casos de uso, repositorio maneja persistencia.
- Dependency Inversion: `DocumentService` trabaja contra el protocolo `DocumentRepository`.
- Interface Segregation: el contrato de repositorio contiene solo operaciones usadas por el caso de documentos.
- Open/Closed: una nueva implementacion de repositorio podria reemplazar a MongoDB respetando el contrato.

### YAGNI

El codigo evita funcionalidades no requeridas por el estado actual: no hay OCR, resumenes, frontend propio, procesamiento asincrono con colas, usuarios, permisos o versionado documental.

## Repository Pattern

El patron Repository aparece en:

- contrato: `app/application/interfaces/document_repository.py`;
- implementacion: `app/infrastructure/repositories/mongo_repository.py`;
- consumidor: `DocumentService`.

Beneficios actuales:

- aisla a `DocumentService` de `motor`;
- permite tests con mocks o repositorios simulados;
- concentra el mapeo `_id` de MongoDB a `UUID`;
- concentra operaciones CRUD sobre la coleccion `documents`.

## Por que sigue siendo un backend monolitico

El sistema sigue siendo monolitico porque:

- se ejecuta como una sola aplicacion FastAPI;
- todos los casos de uso viven en el mismo proceso;
- no hay servicios independientes comunicandose por red;
- el despliegue del backend es una unica unidad Docker;
- la separacion existente es interna al codigo, no de infraestructura distribuida.

La arquitectura por capas mejora mantenibilidad sin convertir el sistema en microservicios.

## Configuracion actual

Variables soportadas por `Settings`:

| Variable | Valor por defecto | Uso actual |
| --- | --- | --- |
| `UPLOAD_DIR` | `uploads` | Se crea al iniciar la app. No almacena PDFs procesados. |
| `MONGO_URI` | `mongodb://localhost:27017` | Conexion MongoDB. |
| `MONGO_DB_NAME` | `pdf-extractext` | Base de datos usada por la app. |
| `MAX_UPLOAD_SIZE_BYTES` | `10485760` | Limite de upload validado por el router. |

En Docker Compose se configuran:

- `MONGO_URI=mongodb://db:27017`;
- `MONGO_DB_NAME=pdf_db`.
