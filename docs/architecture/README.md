# Documentacion de Arquitectura

Esta carpeta documenta la arquitectura tecnica actual del backend monolitico de PDF ExtractText.

La documentacion refleja el estado del codigo fuente existente al momento de su escritura. No describe funcionalidades planificadas como si ya estuvieran implementadas.

## Indice

- [Arquitectura general](./01-arquitectura-general.md)
- [Flujos tecnicos](./02-flujos-tecnicos.md)
- [Roadmap arquitectonico](./03-roadmap-arquitectonico.md)

## Diagramas PlantUML

Los diagramas editables estan en [diagrams](./diagrams/):

- [01-sistema-general.puml](./diagrams/01-sistema-general.puml)
- [02-secuencia-post-documento.puml](./diagrams/02-secuencia-post-documento.puml)
- [03-flujo-get-documento.puml](./diagrams/03-flujo-get-documento.puml)
- [04-ciclo-vida-endpoints.puml](./diagrams/04-ciclo-vida-endpoints.puml)
- [05-componentes-uml.puml](./diagrams/05-componentes-uml.puml)
- [06-clases-uml.puml](./diagrams/06-clases-uml.puml)
- [07-flujo-pdfservice.puml](./diagrams/07-flujo-pdfservice.puml)
- [08-health-check.puml](./diagrams/08-health-check.puml)

## Alcance documentado

El sistema documentado es una API REST FastAPI que:

- procesa uploads de PDF en memoria;
- extrae texto nativo con `pypdf`;
- calcula checksum SHA-256;
- evita duplicados por checksum;
- persiste documentos en MongoDB mediante `motor`;
- expone operaciones CRUD de documentos;
- expone `GET /health` para verificar conectividad con MongoDB.

## Fuera de alcance actual

El backend actual no implementa:

- frontend propio;
- autenticacion o autorizacion;
- OCR;
- resumenes de documentos;
- procesamiento distribuido;
- almacenamiento del archivo PDF original.
