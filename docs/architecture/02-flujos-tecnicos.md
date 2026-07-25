# Flujos Tecnicos

## Endpoints actuales

| Metodo | Ruta real | Handler | Componentes principales |
| --- | --- | --- | --- |
| `POST` | `/api/documents` | `create_document_endpoint` | Router, `DocumentService`, `PDFService`, Repository, MongoDB |
| `GET` | `/api/documents` | `list_documents_endpoint` | Router, `DocumentService`, Repository, MongoDB |
| `GET` | `/api/documents/{doc_id}` | `get_document_endpoint` | Router, `DocumentService`, Repository, MongoDB |
| `PUT` | `/api/documents/{doc_id}` | `update_document_endpoint` | Router, `DocumentService`, Repository, MongoDB |
| `DELETE` | `/api/documents/{doc_id}` | `delete_document_endpoint` | Router, `DocumentService`, Repository, MongoDB |
| `GET` | `/health` | `health_check` | Router, Mongo client, MongoDB |

## Flujo POST /api/documents

Diagrama: [02-secuencia-post-documento.puml](./diagrams/02-secuencia-post-documento.puml)

1. El cliente envia un `multipart/form-data` con el campo `file`.
2. FastAPI enruta la request a `create_document_endpoint`.
3. El router obtiene el nombre del archivo. Si no existe, usa `documento.pdf`.
4. El router valida extension `.pdf` sin distinguir mayusculas/minusculas.
5. El router lee el contenido completo del upload en memoria.
6. El router rechaza archivos vacios.
7. El router obtiene `MAX_UPLOAD_SIZE_BYTES` desde `Settings`.
8. El router rechaza archivos que excedan el tamano maximo.
9. El router valida que los bytes comiencen con `%PDF-`.
10. El router delega en `DocumentService.create_document`.
11. `DocumentService` ejecuta `PDFService.extract_text` usando `asyncio.to_thread`.
12. `PDFService` crea un stream en memoria con `io.BytesIO`.
13. `PDFService` crea un `PdfReader`.
14. `PDFService` rechaza PDFs protegidos con contrasena.
15. `PDFService` recorre las paginas y llama `page.extract_text()`.
16. `PDFService` concatena textos encontrados con saltos de linea y aplica `strip()`.
17. Si no queda texto, `PDFService` lanza `ValueError`.
18. `PDFService` calcula SHA-256 sobre el texto limpio codificado en UTF-8.
19. `PDFService` devuelve `ExtractedPDF`.
20. `DocumentService` consulta `repository.exists_by_checksum`.
21. Si ya existe el checksum, `DocumentService` lanza `ValueError`.
22. `DocumentService` crea un `DocumentRecord` con `uuid4`, filename, texto, checksum y `created_at=None`.
23. `DocumentService` llama `repository.save`.
24. `MongoDocumentRepository` mapea el documento a un diccionario MongoDB.
25. Si `created_at` esta vacio, el repositorio asigna `datetime.now(timezone.utc).isoformat()`.
26. MongoDB guarda el documento en la coleccion `documents`.
27. El repositorio mapea el documento guardado a `DocumentRecord`.
28. El router responde HTTP `200` con `DocumentResponse`.

Errores principales:

- extension no PDF: `400`;
- archivo vacio: `400`;
- tamano excedido: `413`;
- magic bytes invalidos: `400`;
- PDF protegido, danado, sin texto extraible o duplicado: `400`.

## Flujo GET

Diagrama: [03-flujo-get-documento.puml](./diagrams/03-flujo-get-documento.puml)

Para `GET /api/documents/{doc_id}`:

1. El cliente envia un UUID en la ruta.
2. FastAPI valida el formato UUID.
3. El router obtiene `DocumentService` desde `request.app.state`.
4. El router llama `service.get_document(doc_id)`.
5. `DocumentService` delega en `repository.get_by_id(doc_id)`.
6. `MongoDocumentRepository` consulta MongoDB por `_id = str(doc_id)`.
7. Si existe, el repositorio mapea el documento a `DocumentRecord`.
8. El router devuelve `DocumentResponse`.
9. Si no existe, el router devuelve `404`.

Para `GET /api/documents`:

1. El router llama `service.list_documents()`.
2. `DocumentService` usa limite por defecto `100`.
3. El repositorio ejecuta `find().limit(limit)`.
4. Los documentos se mapean a `DocumentRecord`.
5. El router devuelve una lista de `DocumentResponse`.

## Ciclo de vida de endpoints

Diagrama: [04-ciclo-vida-endpoints.puml](./diagrams/04-ciclo-vida-endpoints.puml)

Resumen de participacion:

| Endpoint | Router | DocumentService | PDFService | Repository | MongoDB | Mongo client directo |
| --- | --- | --- | --- | --- | --- | --- |
| `POST /api/documents` | Si | Si | Si | Si | Si | No |
| `GET /api/documents` | Si | Si | No | Si | Si | No |
| `GET /api/documents/{doc_id}` | Si | Si | No | Si | Si | No |
| `PUT /api/documents/{doc_id}` | Si | Si | No | Si | Si | No |
| `DELETE /api/documents/{doc_id}` | Si | Si | No | Si | Si | No |
| `GET /health` | Si | No | No | No | Si | Si |

## Flujo interno de PDFService

Diagrama: [07-flujo-pdfservice.puml](./diagrams/07-flujo-pdfservice.puml)

El flujo completo de subida de PDF reparte responsabilidades entre el router y `PDFService`.

Validaciones realizadas antes de `PDFService`, en `create_document_endpoint`:

1. recibir `UploadFile`;
2. resolver nombre de archivo;
3. validar extension `.pdf`;
4. leer bytes;
5. validar archivo no vacio;
6. validar tamano maximo;
7. validar magic bytes `%PDF-`.

Responsabilidades reales de `PDFService.extract_text`:

1. recibir bytes y filename;
2. envolver bytes en `io.BytesIO`;
3. crear `PdfReader`;
4. verificar si el PDF esta protegido con contrasena;
5. recorrer paginas;
6. extraer texto nativo con `page.extract_text()`;
7. ignorar resultados `None` o strings vacios;
8. unir el texto con `\n`;
9. limpiar extremos con `strip()`;
10. rechazar PDFs sin texto extraible;
11. generar checksum SHA-256 sobre el texto limpio;
12. devolver `ExtractedPDF`.

## Flujo de Health Check

Diagrama: [08-health-check.puml](./diagrams/08-health-check.puml)

`GET /health` verifica la disponibilidad operativa minima del backend:

1. FastAPI enruta la request a `health_check`.
2. El handler accede a `request.app.state.mongo_client`.
3. Ejecuta `mongo_client.admin.command("ping")`.
4. Si MongoDB responde, devuelve HTTP `200` con `{"status": "healthy"}`.
5. Si ocurre una excepcion, devuelve HTTP `503` con `{"status": "unhealthy"}`.

Este endpoint no utiliza `DocumentService` ni `MongoDocumentRepository`; valida directamente la conectividad del cliente MongoDB creado durante el lifespan de la app.
