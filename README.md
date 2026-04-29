# PDF ExtractText

Un sistema de API REST que extrae texto de archivos PDF en memoria y gestiona los documentos utilizando bases de datos NoSQL.

**Desarrolladoras:** 
* Julieta Bignet
* Sanchez B. Victoria

###### Estado Actual
Requerimientos y Funcionalidades del Proyecto:

* Arquitectura Limpia (Clean Architecture): Implementación de una estructura desacoplada en capas de Presentación, Aplicación e Infraestructura.
* Extracción en Memoria (Stateless): Procesamiento de archivos PDF íntegramente en memoria RAM mediante pypdf, sin almacenamiento temporal en disco.
* Persistencia NoSQL: Integración asíncrona con MongoDB para el almacenamiento persistente de los documentos procesados.
* Control de Duplicados: Validación de redundancia mediante el cálculo de Checksum SHA-256 sobre el contenido extraído.
* Operaciones CRUD: Implementación completa de endpoints para Cargar (Upload/Save), Buscar (Find), Actualizar (Update) y Eliminar (Delete) documentos.
* Calidad de Software: Suite de pruebas unitarias y de integración bajo metodología TDD y validación de tipos estáticos.
---

## 📖 Resumen

PDF ExtractText es una API REST desarrollada en Python que permite:

- **Subir** archivos PDF a través de una API REST.
- **Extraer texto** de los PDFs directamente en memoria RAM usando `pypdf`.
- **Prevenir duplicados** mediante el cálculo de un Checksum (SHA-256) sobre el texto extraído.
- **Persistir** los datos extraídos de forma asíncrona utilizando MongoDB.

> **⚠️ Limitación Conocida (OCR):**
> Si el PDF contiene solo imágenes o fue generado por un escáner físico sin texto digital inyectado, el sistema devolverá un texto vacío. Esto es el comportamiento esperado, ya que la herramienta extrae texto nativo de los metadatos del archivo y la implementación de un motor OCR (Reconocimiento Óptico de Caracteres) excede el alcance actual del proyecto (respetando el principio KISS).

## ✨ Características

- Extracción de texto de PDF en memoria.
- Persistencia de datos asíncrona.
- API REST rápida y moderna.
- Control estricto de duplicados mediante Huella Digital (Checksum).
- Desarrollo Guiado por Pruebas (TDD) con un 100% de cobertura.
- Diseño basado estrictamente en **Arquitectura Limpia** (Clean Architecture).
- Código limpio aplicando principios SOLID, DRY, KISS y YAGNI.

## 🛠️ Stack Tecnológico

| Categoría | Tecnología |
|----------|------------|
| Lenguaje | Python 3.13+ |
| Framework Web | FastAPI |
| Procesamiento PDF | pypdf |
| Base de Datos | MongoDB (Driver `motor`) |
| Gestión de Entorno | UV |
| Testing | Pytest, Pytest-asyncio, Mongomock-motor |

### Dependencias Principales

- **fastapi**: Framework web moderno, rápido y asíncrono.
- **uvicorn**: Servidor ASGI para correr la aplicación.
- **pypdf**: Procesamiento y extracción de texto de PDF.
- **motor**: Driver asíncrono oficial de MongoDB.
- **pytest / pytest-asyncio**: Framework de pruebas unitarias y de integración.
- **mongomock-motor**: Simulador asíncrono de base de datos para testing aislado.

## 📂 Estructura del Proyecto

```text
pdf-extractext/
├── app/
│   ├── main.py                 
│   ├── core/                   
│   ├── application/            
│   │   ├── interfaces/         
│   │   └── services/           
│   ├── infrastructure/         
│   │   └── repositories/       
│   │       └── mongo_repository.py
│   └── presentation/           
│       ├── routers/            
│       └── schemas/            
├── tests/                      
│   ├── test_api.py
│   ├── test_document_service.py
│   ├── test_mongo_repository.py
│   └── test_pdf_service.py
├── pyproject.toml              
└── README.md
```
### Descripción de Capas (Arquitectura Limpia)

- Presentation (Presentación): Maneja las peticiones HTTP, valida los datos de entrada/salida usando Pydantic y enruta hacia los servicios.
- Application (Aplicación/Dominio): Contiene la lógica de negocio pura. No sabe que existe FastAPI ni MongoDB. Define las reglas mediante DocumentService y PDFService.
- Infrastructure (Infraestructura): Implementa los contratos definidos por la aplicación. Aquí reside la conexión real a MongoDB mediante el driver motor.

### ⚙️ Requisitos y Configuración

## Requisitos del Sistema
- SO: Windows 11 / Linux / macOS.
- Python: Versión 3.13 o superior.
- MongoDB: Instancia activa en el puerto 27017 (Nativo o vía Docker).
- Instalación Directa (con UV)
- Instalar dependencias del proyecto:Bashuv sync
  
## Instalar herramientas de desarrollo:
````
Bash
uv sync --extra dev
````

### 🚀 Ejecución
## Iniciar el servidor de desarrollo:
```
Bash
uv run uvicorn app.main:app --reload
```
La API estará disponible en http://localhost:8000. Al acceder, el sistema redirigirá automáticamente a la documentación interactiva:
Swagger UI: http://localhost:8000/docs

### 📡 Uso de la API
## Endpoints principales

| Método | Endpoint                 | Acción                                                       |
|--------|--------------------------|--------------------------------------------------------------|
| POST   | `/docs/documents`        | Sube un PDF, extrae texto y lo guarda                       |
| GET    | `/docs/documents/{id}`   | Recupera la información de un documento                     |
| PUT    | `/docs/documents/{id}`   | Actualiza el texto extraído                                 |
| DELETE | `/docs/documents/{id}`   | Elimina un registro del sistema                             |

## Nota técnica

El sistema utiliza checksum **SHA-256** sobre el texto extraído.  
Si intentas subir un documento diferente pero que contiene exactamente el mismo texto que uno ya registrado, el sistema lo detectará como duplicado para optimizar el almacenamiento.

### 🧪 Pruebas Automatizadas
Se ha implementado una suite completa de pruebas que garantiza el funcionamiento de cada capa de forma aislada.
Ejecutar todos los tests:
```
Bash
uv run pytest
```
### 📡 Uso de la API (Interfaz Interactiva)
Por decisiones arquitectónicas y estándares de la industria (KISS), el sistema no cuenta con un frontend tradicional en HTML (de momento), sino que utiliza Swagger UI.

Flujo de operación básico:
1. Ingrese a http://127.0.0.1:8000/docs desde su navegador
2. Localice el método HTTP de interés (por ejemplo, el POST para crear un documento).
3. Haga clic en el botón "Try it out".
4. Adjunte un archivo PDF válido en el formulario.
5. Presione el botón "Execute".

## Formato de Respuesta Esperada (Ejemplo POST)
Si el documento se procesa correctamente y no es un duplicado, el servidor devolverá un código HTTP 200 con la siguiente estructura:
```
JSON
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "original_filename": "documento.pdf",
  "full_text": "Texto completo extraído del documento...",
  "checksum": "a8b9c1d2e3f4g5...",
  "created_at": "2026-04-29T15:30:00Z"
}
```

### 🧪 Pruebas (Testing)
El proyecto cuenta con una suite de pruebas robusta que aísla la base de datos utilizando mongomock-motor y aplica simulación de objetos (Mocks) para garantizar la fiabilidad del código.

## Ejecutar toda la suite de pruebas:
```
Bash
uv run pytest
```

### 🧠 Metodología y Diseño
## TDD (Test-Driven Development): 
El proyecto sigue el ciclo Red-Green-Refactor:
1. Red: Escribir pruebas que fallan inicialmente.
2. Green: Implementar el código mínimo para pasar las pruebas.
3. Refactor: Mejorar el código y la arquitectura manteniendo las pruebas en verde.

## Principios de Diseño Aplicados

| Principio | Descripción en el Proyecto |
|----------|----------------------------|
| KISS     | Se mantuvo la simplicidad evitando integrar motores OCR pesados en la Etapa 1. |
| DRY      | La lógica de extracción y cálculo de hashes está centralizada y no se repite. |
| YAGNI    | No se añadieron validaciones binarias de bajo nivel que no fueron solicitadas en los requerimientos core. |
| SOLID    | Uso intensivo de Single Responsibility y Dependency Inversion para desacoplar MongoDB de la lógica de negocio. |