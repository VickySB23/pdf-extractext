# PDF Extract — Test de carga, estrés y optimización de microservicio

Trabajo práctico universitario de Desarrollo de Software.
Universidad Tecnológica Nacional, Facultad Regional San Rafael, Ingeniería en Sistemas.
Año 2026.
Integrantes: Julieta Bignet y Victoria Sanchez Bujaldon.
Repositorio: https://github.com/VickySB23/pdf-extractext, rama `parte-dos`.

Este README documenta el stack de microservicios y las pruebas de carga. El monolito de la etapa 1 está en la rama `monolito`.

## 1. Descripción
El microservicio expone `POST /extract` para recibir un PDF y extraer su texto.
Acepta el archivo como cuerpo binario crudo o como `multipart/form-data`.
La respuesta exitosa es JSON con la forma `{"content": "...", "page_count": N}`.
El contenido se entrega en Markdown liviano por defecto, configurable a texto plano.

## 2. Arquitectura
```text
Cliente, k6 o Vegeta
    |
    v
Traefik :8080 <-- lee las rutas --- Consul :8500 <-- se registra cada réplica
    |
    |--- /extract ------------------> 5 réplicas de extraction-service
    |                                        ^
    | /api/documents, /health                | /extract
    v                                        |
document-service ----------------------------+
    |
    v
MongoDB
```

- `docker compose up --build` levanta todo el stack desde `docker-compose.yml`.
- Traefik publica el puerto `8080` y su dashboard en `8081`. Consul publica su interfaz en `8500`.
- Cada réplica se registra en Consul al arrancar, con ID propio, chequeo HTTP y sus rutas como tags, y se da de baja al apagarse. Traefik descubre las rutas desde Consul, sin labels en el compose ni acceso al socket de Docker.
- Traefik balancea `/extract` con estrategia `p2c`, también para las llamadas de `document-service`.
- Cada contenedor tiene límites de CPU y memoria; las réplicas usan 1 CPU y 512 MiB.
- Las imágenes propias están versionadas: `pdf-extraction-service:v1.0.0` y `pdf-document-service:v1.0.0`.
- La extracción usa PyMuPDF por su mejor rendimiento frente a `pypdf`.
- El backpressure se implementa con un cupo por réplica, `503` y header `Retry-After`.
- El cupo se adquiere antes de leer el cuerpo para no retener PDFs en memoria.
- El Markdown es una conversión propia y liviana: títulos, viñetas y párrafos.
- La configuración entra por variables de entorno y los logs salen por stdout.
- Las imágenes ejecutan los servicios con un usuario sin privilegios.
- `document-service` envía cada PDF a `extraction-service` como cuerpo binario y guarda el Markdown devuelto.
- El PDF se procesa en memoria, sin archivos temporales. El checksum SHA-256 se calcula sobre el archivo y un índice único evita duplicados.

## 3. Requisitos
- Docker con Docker Compose.
- k6 solo para ejecutar la prueba de carga tipo spike.
- Vegeta solo para ejecutar la prueba de carga fija a 50 req/s.
- PowerShell, Bash, Git Bash o una terminal equivalente para los scripts.

## 4. Cómo levantar
```bash
docker compose up --build
```
Ejemplo de llamada con un PDF del repositorio:
```bash
curl -X POST http://localhost:8080/extract \
  -H "Content-Type: application/pdf" \
  --data-binary "@tests/stress/pdfs/2020-Scrum-Guide-Spanish-Latin-South-American.pdf"
```
Respuesta de ejemplo:
Se muestra abreviada.
```json
{"content": "# Ken Schwaber & Jeff Sutherland La Guía de Scrum ...\n\n# Propósito de la Guía Scrum\n\nDesarrollamos Scrum a principios de la década de 1990. ...", "page_count": 16}
```

## 5. Configuración
Estas son las variables de `extraction-service`. `document-service` usa `MONGO_URI`, `MONGO_DB_NAME`, `EXTRACTION_URL`, `CONSUL_URL` y `MAX_UPLOAD_SIZE_BYTES`.
El compose inyecta las de cola y formato, y deja el tamaño máximo con su default.
| Variable | Default | Uso |
| --- | --- | --- |
| `MAX_UPLOAD_SIZE_BYTES` | `10485760` | Tamaño máximo aceptado para el PDF. |
| `QUEUE_TIMEOUT_SECONDS` | `20` | Tiempo máximo de espera antes de responder `503`. |
| `RETRY_AFTER_SECONDS` | `1` | Valor del header `Retry-After` ante saturación. |
| `OUTPUT_FORMAT` | `markdown` | Formato de salida: `markdown` o `text`. |
| `CONSUL_URL` | sin definir | Dirección de Consul. Sin ella el servicio no se registra. |

El puerto interno de `extraction-service` es fijo: `8001`. Traefik expone el stack en `8080`.
Cada réplica atiende una extracción por vez, porque PyMuPDF no admite hilos concurrentes.

## 6. Pruebas de carga
k6, desde la raíz del repositorio:
```bash
k6 run tests/stress/k6-spike.js
```
Vegeta en Linux, macOS o Git Bash:
```bash
./tests/stress/run-vegeta.sh mi-prueba
```
Vegeta en Windows:
```powershell
.\tests\stress\run-vegeta.ps1 -Label mi-prueba
```
Para medir desde la red de Docker se usan:
`.\tests\stress\run-k6-docker.ps1` y `.\tests\stress\run-vegeta-docker.ps1`.

## 7. Resultados
Los valores se toman del informe técnico en `docs/informe/INFORME.md`.
| Prueba | Referencia cátedra | Resultado final |
| --- | ---: | ---: |
| k6, throughput sostenido | 25,35 req/s | 12,95 req/s con Markdown |
| k6, texto plano | 25,35 req/s | 19,60 req/s con `OUTPUT_FORMAT=text` |
| Vegeta, tasa de éxito | 66,53 % | 15,8 % |

No se superó la referencia de la cátedra.
El informe explica el análisis de capacidad, las hipótesis descartadas y el impacto del Markdown.

## 8. Estructura del repositorio
```text
services/
  extraction-service/      Extrae el texto del PDF
  document-service/        API de documentos y persistencia en MongoDB
tests/stress/              Scripts k6, Vegeta y PDFs oficiales
docs/informe/              Informe técnico final
docs/mediciones/           Registro y salidas crudas de medición
docker-compose.yml         Stack completo
```

## 9. API de documentos

| Método | Ruta | Uso |
| --- | --- | --- |
| `GET` | `/health` | Estado de `document-service` y MongoDB. |
| `POST` | `/api/documents` | Sube un PDF, extrae el texto y lo guarda. |
| `GET` | `/api/documents` | Lista hasta 100 documentos. |
| `GET` | `/api/documents/{id}` | Consulta un documento. |
| `PUT` | `/api/documents/{id}` | Actualiza el texto; el checksum sigue identificando el archivo original. |
| `DELETE` | `/api/documents/{id}` | Elimina un documento. |

```bash
curl -X POST http://localhost:8080/api/documents \
  -F "file=@documento.pdf;type=application/pdf"
curl http://localhost:8080/api/documents
```

La respuesta incluye `id`, `original_filename`, `full_text`, `checksum` y `created_at`. El router valida la extensión `.pdf`; `extraction-service` valida el archivo vacío, el tamaño máximo de 10 MB y la firma `%PDF-`. Una subida sin `Content-Length` se rechaza con `411`.

Traefik solo enruta los servicios que Consul marca como sanos. Justo después de arrancar, una petición puede devolver `404` durante unos segundos. Para esperar a que todo esté listo:

```bash
docker compose up --build -d --wait
```

Para detener el stack sin borrar datos, usá `docker compose down`. `down -v` borra la base.

### Limitaciones

- El listado devuelve como máximo 100 documentos y no tiene paginación.
- No hay autenticación, autorización, OCR ni frontend. Los PDFs no se guardan; solo se persiste el texto extraído.
- El gateway no publica la documentación interactiva (`/docs`).

## 10. Licencia
El proyecto está publicado bajo licencia MIT; ver `LICENSE`.
PyMuPDF se distribuye bajo AGPL-3.0 o licencia comercial, un punto a revisar fuera del contexto académico.
