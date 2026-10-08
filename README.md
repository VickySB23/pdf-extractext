# PDF Extract — Test de carga, estrés y optimización de microservicio (Parte 2)

Trabajo práctico universitario de Desarrollo de Software.
Universidad Tecnológica Nacional, Facultad Regional San Rafael, Ingeniería en Sistemas.
Año 2026.
Integrantes: Julieta Bignet y Victoria Sanchez Bujaldon.
Repositorio: https://github.com/VickySB23/pdf-extractext, rama `parte-dos`.

## 1. Descripción
El microservicio expone `POST /extract` para recibir un PDF y extraer su texto.
Acepta el archivo como cuerpo binario crudo o como `multipart/form-data`.
La respuesta exitosa es JSON con la forma `{"content": "...", "page_count": N}`.
El contenido se entrega en Markdown liviano por defecto, configurable a texto plano.

## 2. Arquitectura
```text
k6 / Vegeta
    |
    v
Traefik :8080
    |
    v
5 réplicas de extraction-service
1 CPU y 512 MiB por réplica
```

- `docker-compose.yml` publica Traefik en `8080:80` y enruta `/extract` y `/health`.
- Traefik balancea con estrategia `p2c`, según la etiqueta actual del compose.
- La extracción usa PyMuPDF por su mejor rendimiento frente a `pypdf`.
- El backpressure se implementa con semáforo, `503` y header `Retry-After`.
- El semáforo se adquiere antes de leer el cuerpo para no retener PDFs en memoria.
- El Markdown es una conversión propia y liviana: títulos, viñetas y párrafos.
- La configuración entra por variables de entorno y los logs salen por stdout.
- La imagen ejecuta el servicio con un usuario sin privilegios.

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
Estas son las variables que lee `services/extraction-service/app/main.py`.
El compose inyecta las cuatro de concurrencia/formato y deja el tamaño máximo con su default.
| Variable | Default | Uso |
| --- | --- | --- |
| `MAX_UPLOAD_SIZE_BYTES` | `10485760` | Tamaño máximo aceptado para el PDF. |
| `MAX_CONCURRENT` | `1` | Cantidad de extracciones simultáneas por réplica. |
| `QUEUE_TIMEOUT_SECONDS` | `20` | Tiempo máximo de espera antes de responder `503`. |
| `RETRY_AFTER_SECONDS` | `1` | Valor del header `Retry-After` ante saturación. |
| `OUTPUT_FORMAT` | `markdown` | Formato de salida: `markdown` o `text`. |

El puerto interno del contenedor es `8001`; Traefik lo expone hacia el host en `8080`.

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
  extraction-service/      Microservicio evaluado en la parte 2
  document-service/        Servicio de la primera etapa
tests/stress/              Scripts k6, Vegeta y PDFs oficiales
docs/informe/              Informe técnico final
docs/mediciones/           Registro y salidas crudas de medición
docker-compose.yml         Stack de benchmark con Traefik y 5 réplicas
docker-compose.full.yml    Stack completo de la primera etapa con MongoDB
```

## 9. Documentación y primera etapa
- Informe final: [`docs/informe/INFORME.md`](docs/informe/INFORME.md).
- Mediciones crudas y registro: [`docs/mediciones/`](docs/mediciones/).
- Primera etapa con MongoDB: [`main`](https://github.com/VickySB23/pdf-extractext/tree/main).
- Stack heredado de la primera etapa: `docker compose -f docker-compose.full.yml up --build`.

## 10. Licencia
El proyecto está publicado bajo licencia MIT; ver `LICENSE`.
PyMuPDF se distribuye bajo AGPL-3.0 o licencia comercial, un punto a revisar fuera del contexto académico.
