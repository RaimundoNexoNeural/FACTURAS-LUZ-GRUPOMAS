from fastapi import FastAPI, HTTPException
from typing import List, Dict, Any
from modelos_datos import FacturaEndesaCliente
# Importamos la función ASÍNCRONA para la extracción de datos
from robotEndesa import ejecutar_robot_api 
# Importamos la función SÍNCRONA para la lectura de PDF local
from robotEndesa import obtener_pdf_local_base64 
import asyncio
import re
import os # Necesario para manejar FileNotFoundError

# Inicializar la aplicación de FastAPI
app = FastAPI(
    title="API de Extracción de Facturas Endesa",
    description="API que automatiza la búsqueda y extracción de datos detallados de facturas de Endesa."
)

# --- Funciones de Validación ---

def validar_cups(cups: str):
    """Simple validación de formato de CUPS (ajustar según sea necesario)."""
    cups_pattern = r'^ES[A-Z0-9]{20}$' 
    if not re.match(cups_pattern, cups):
        raise HTTPException(
            status_code=400, 
            detail=f"El formato del código CUPS '{cups}' es inválido. Debe seguir el patrón ESXX... y tener 22 caracteres."
        )

def validar_fecha(fecha: str):
    """Simple validación de formato de fecha DD/MM/YYYY."""
    fecha_pattern = r'^\d{2}/\d{2}/\d{4}$'
    if not re.match(fecha_pattern, fecha):
        raise HTTPException(
            status_code=400, 
            detail="El formato de fecha es inválido. Use DD/MM/YYYY (ej: 01/10/2025)."
        )

# --- Endpoint de Extracción de Metadatos ---

@app.get("/")
def read_root():
    """Endpoint de salud (Health Check)"""
    return {"message": "Servicio de Extracción de Facturas Endesa activo. Visite /docs para la documentación."}

@app.get(
    "/facturas", 
    response_model=List[FacturaEndesaCliente],
    summary="Busca y extrae los datos de facturas para un CUPS en un rango de fechas."
)
async def get_facturas(
    cups: str, 
    fecha_desde: str, # Formato DD/MM/YYYY
    fecha_hasta: str  # Formato DD/MM/YYYY
):
    """
    Realiza el proceso completo de Login -> Búsqueda -> Descarga -> Extracción XML.
    Devuelve una lista de objetos FacturaEndesaCliente con el campo 'descarga_selector' 
    que se usará para la descarga de PDF local.
    """
    
    # Validaciones iniciales
    validar_cups(cups)
    validar_fecha(fecha_desde)
    validar_fecha(fecha_hasta)
    
    print(f"API llamada (Metadata): CUPS={cups}, Desde={fecha_desde}, Hasta={fecha_hasta}")
    
    try:
        facturas = await ejecutar_robot_api(
            cups=cups, 
            fecha_desde=fecha_desde, 
            fecha_hasta=fecha_hasta
        )

        if not facturas:
             print(f"Advertencia: No se encontraron facturas para el CUPS {cups} en el rango.")
             return []

        print(f"ÉXITO (Metadata): {len(facturas)} facturas extraídas.")
        return facturas

    except HTTPException:
        raise
        
    except Exception as e:
        error_msg = f"Fallo crítico en el proceso RPA para CUPS {cups}: {e}"
        print(f"ERROR: {error_msg}")
        raise HTTPException(status_code=500, detail=error_msg)


# --- NUEVO Endpoint de Lectura de PDF Local ---

@app.get(
    "/pdf-local/{cups}/{numero_factura}",
    response_model=Dict[str, Any], # Devolvemos un diccionario que incluye el Base64
    summary="Accede y codifica un PDF previamente descargado del servidor."
)
def get_pdf_local(
    cups: str,
    numero_factura: str,
):
    """
    Lee el PDF del disco local (temp_endesa_downloads/Facturas_Endesa_PDFs/) 
    usando el CUPS y el número de factura.

    - **cups**: Código CUPS.
    - **numero_factura**: Número de factura (ej: P25CON050642974).

    Devuelve un JSON con el contenido del PDF codificado en Base64 bajo la clave 'pdf_base64'.
    """
    
    # Validación básica de los parámetros entrantes
    if not numero_factura:
         raise HTTPException(status_code=400, detail="Falta el parámetro 'numero_factura'.")
    validar_cups(cups)
    
    print(f"API llamada (PDF Local): CUPS={cups}, Factura={numero_factura}")
    
    try:
        # Llamamos a la función síncrona de acceso a disco local
        # No necesitamos la descarga_selector ya que el archivo está en el disco.
        pdf_data = obtener_pdf_local_base64(
            cups=cups,
            numero_factura=numero_factura,
        )
        
        print(f"ÉXITO (PDF Local): PDF para {numero_factura} codificado.")
        return pdf_data
        
    except FileNotFoundError as e:
        error_msg = f"Archivo no encontrado. Asegúrese de que la factura se haya extraído previamente. Detalle: {e}"
        print(f"ERROR: {error_msg}")
        raise HTTPException(status_code=404, detail=error_msg)
        
    except Exception as e:
        error_msg = f"Fallo crítico al leer el PDF para {numero_factura}: {e}"
        print(f"ERROR: {error_msg}")
        raise HTTPException(status_code=500, detail=error_msg)