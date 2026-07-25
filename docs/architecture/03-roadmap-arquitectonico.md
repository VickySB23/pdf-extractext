# Roadmap Arquitectonico

## Funcionalidades ya implementadas

- Backend monolitico FastAPI.
- Ensamblado de dependencias en `app/main.py`.
- Configuracion con Pydantic Settings y soporte de `.env`.
- Logging basico centralizado.
- Upload de archivos PDF mediante `multipart/form-data`.
- Validacion de extension `.pdf`.
- Validacion de archivo no vacio.
- Validacion de tamano maximo configurable.
- Validacion de magic bytes `%PDF-`.
- Extraccion de texto nativo en memoria con `pypdf`.
- Rechazo de PDF protegido con contrasena.
- Rechazo de PDF danado o no procesable.
- Rechazo de PDF sin texto extraible.
- Checksum SHA-256 del texto extraido.
- Deteccion de duplicados por checksum.
- Persistencia asincrona en MongoDB con `motor`.
- Repository Pattern mediante `DocumentRepository` y `MongoDocumentRepository`.
- CRUD de documentos:
  - crear desde PDF;
  - listar;
  - obtener por UUID;
  - actualizar texto;
  - eliminar.
- Health check con ping a MongoDB.
- Dockerfile para la API.
- Docker Compose con API y MongoDB.
- Tests unitarios e integracion basica con `pytest`, mocks y `mongomock-motor`.

## Mejoras futuras compatibles con la arquitectura actual

Estas mejoras podrian agregarse si aparecen requerimientos reales:

- indices en MongoDB para `checksum` y `_id`;
- restriccion unica de checksum a nivel de base de datos;
- paginacion explicita para `GET /api/documents`;
- filtros de busqueda por filename o checksum;
- timestamps de actualizacion (`updated_at`);
- manejo estructurado de errores con codigos internos;
- tests adicionales de endpoints `GET /api/documents/{doc_id}`, `PUT` y `DELETE`;
- tests de integracion con MongoDB real en entorno Docker;
- observabilidad basica con request id y metricas;
- configuracion diferenciada por ambiente;
- CI para ejecutar tests y linting;
- documentacion OpenAPI enriquecida con ejemplos;
- limite de paginas o tiempo de procesamiento para PDFs grandes;
- cierre mas explicito de recursos en pruebas de integracion.

## Mejoras que requieren una decision de producto o arquitectura

Estas opciones no contradicen necesariamente KISS/YAGNI, pero no deberian agregarse sin necesidad concreta:

- autenticacion y autorizacion;
- roles o permisos;
- almacenamiento del PDF original;
- versionado de documentos;
- historial de actualizaciones;
- auditoria de operaciones;
- procesamiento asincrono con cola;
- extraccion en background;
- soporte para multiples formatos ademas de PDF;
- API publica multi-tenant;
- despliegue separado por servicios.

## Funcionalidades que no deben implementarse ahora por KISS/YAGNI

No conviene incorporarlas al estado actual porque agregarian complejidad sin estar respaldadas por el comportamiento existente:

- microservicios para separar PDF, documentos y health check;
- broker de mensajes solo para procesar uploads simples;
- OCR pesado para PDFs escaneados sin requerimiento explicito;
- motor de resumenes o integracion con IA;
- cache distribuida;
- event sourcing;
- CQRS;
- almacenamiento dual en MongoDB y otro repositorio;
- panel administrativo o frontend propio;
- sistema de plugins;
- abstracciones genericas para multiples bases de datos si solo se usa MongoDB.

## Criterios para evolucionar sin romper la arquitectura

- Mantener los routers sin logica de negocio persistente.
- Mantener `DocumentService` dependiente del contrato `DocumentRepository`, no de MongoDB.
- Mantener `PDFService` independiente de FastAPI y de infraestructura.
- Agregar validaciones HTTP en presentation cuando dependan de la request.
- Agregar reglas de negocio en application cuando dependan del caso de uso.
- Agregar detalles tecnicos de MongoDB solo en infrastructure.
- Evitar nuevos paquetes o capas hasta que exista una necesidad verificable.
