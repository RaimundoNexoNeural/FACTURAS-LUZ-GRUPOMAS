# FACTURAS-LUZ-GRUPOMAS

## Descripción del Proyecto

Este proyecto automatiza la búsqueda, descarga y procesamiento de facturas de Endesa para el grupo empresarial "GRUPO HERMANOS MARTIN". Utiliza tecnologías como FastAPI para la creación de una API, Playwright para la automatización del navegador y Pydantic para la validación de datos.

## Estructura del Proyecto

La estructura del proyecto es la siguiente:

```
DESCARGA FACTURAS MAS/
├── __init__.py
├── api.py                # Implementación de la API con FastAPI
├── decodificar_pdf.py    # Decodificación de PDFs (pendiente de detalles)
├── facturas_endesa_log_ES0034111300275021NX0F.csv # Log de facturas
├── modelos_datos.py      # Modelos de datos con Pydantic
├── navegador.py          # Clase para manejar el navegador con Playwright
├── robotEndesa.py        # Lógica principal del robot RPA
├── xml_parser.py         # Procesamiento de archivos XML
├── pdf_parser.py         # Procesamiento de archivos PDF mediante OCR de OpenAI
├── temp_endesa_downloads/
│   ├── Facturas_Endesa_HTMLs/ # Archivos HTML descargados
│   ├── Facturas_Endesa_PDFs/  # Archivos PDF descargados
│   └── Facturas_Endesa_XMLs/  # Archivos XML descargados
└── README.md             # Documentación del proyecto
```

## Funcionalidades Principales

1. **Extracción de Metadatos de Facturas**:
   - Endpoint: `/facturas`
   - Parámetros: `cups`, `fecha_desde`, `fecha_hasta`
   - Devuelve: Lista de facturas con metadatos extraídos.

2. **Acceso a PDFs Locales**:
   - Endpoint: `/pdf-local/{cups}/{numero_factura}`
   - Parámetros: `cups`, `numero_factura`
   - Devuelve: Contenido del PDF codificado en Base64.

3. **Automatización del Navegador**:
   - Login en el portal de Endesa.
   - Búsqueda y descarga de facturas en formatos XML, HTML y PDF.

4. **Procesamiento de Archivos XML**:
   - Extracción de datos detallados como potencia, consumo, impuestos, etc.

5. **Procesamiento de Archivos PDF**:
   - Extracción de datos detallados como potencia, consumo, impuestos, etc. Mediante OCR de OpenAI

## Requisitos del Sistema

- Python 3.9 o superior
- Playwright
- FastAPI
- Pydantic
- OpenAi

## Instalación y Configuración

1. Clonar el repositorio:
   ```bash
   git clone https://github.com/RaimundoNexoNeural/FACTURAS-LUZ-GRUPOMAS.git
   cd FACTURAS-LUZ-GRUPOMAS
   ```

2. Instalar dependencias:
   ```bash
   pip install -r requirements.txt
   ```

3. Configurar Playwright:
   ```bash
   playwright install
   ```

## Uso del Proyecto

1. **Iniciar la API**:
   ```bash
   uvicorn api:app --reload
   ```
   Acceder a la documentación interactiva en: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

2. **Ejemplo de Llamada a la API**:
   - Endpoint `/facturas`:
     ```bash
     curl -X GET "http://127.0.0.1:8000/facturas?cups=ES0034111300275021NX0F&fecha_desde=01/01/2025&fecha_hasta=31/01/2025"
     ```

3. **Procesar PDFs Locales**:
   - Endpoint `/pdf-local/{cups}/{numero_factura}`:
     ```bash
     curl -X GET "http://127.0.0.1:8000/pdf-local/ES0034111300275021NX0F/P25CON050642974"
     ```

## Notas Adicionales

- **Logs**: Los logs de las facturas procesadas se almacenan en archivos CSV dentro del directorio raíz.
- **Carpetas Temporales**: Los archivos descargados se organizan en subcarpetas dentro de `temp_endesa_downloads/`.

## Contribuciones

Las contribuciones son bienvenidas. Por favor, crea un fork del repositorio y envía un pull request con tus cambios.

## Licencia

Este proyecto está bajo la licencia MIT.