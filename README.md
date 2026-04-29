# PDF ExtractText

Un sistema de API REST que extrae texto de archivos PDF en memoria y gestiona los documentos utilizando bases de datos NoSQL.

**Desarrolladoras:** * Julieta Bignet
* Sanchez B. Victoria

###### Estado Actual
El proyecto se encuentra funcional y cumple con todos los requerimientos de la Etapa 1.

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