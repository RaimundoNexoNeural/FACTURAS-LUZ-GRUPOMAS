from navegador import NavegadorAsync, TEMP_DOWNLOAD_ROOT # Importamos la clase base y la ruta de descarga
import asyncio
import re
import csv # Necesario para exportar los logs
import base64 # Necesario para la codificación Base64
import os # Necesario para manejar rutas de archivos
from playwright.async_api import Page, TimeoutError, Locator # Importamos Page, TimeoutError, Locator
from modelos_datos import FacturaEndesaCliente # Importamos la clase modelo de datos (AHORA ES PYDANTIC)
# IMPORTACIÓN DEL PARSER XML
from xml_parser import procesar_xml_local
# IMPORTACIÓN DE LA FUNCIÓN DE LOGGING
from logs import escribir_log

# --- CONSTANTES DE ENDESA ---
URL_LOGIN = "https://endesa-atenea.my.site.com/miempresa/s/login/?language=es" 
URL_BUSQUEDA_FACTURAS = "https://endesa-atenea.my.site.com/miempresa/s/asistente-busqueda?tab=f"

# Credenciales REALES proporcionadas por el usuario
USER = os.environ.get("ENDESA_USER", "sin_usuario")
PASSWORD = os.environ.get("ENDESA_PASSWORD", "sin_contraseña")

GRUPO_EMPRESARIAL = "GRUPO HERMANOS MARTIN" # Constante para el filtro siempre aplicado

# LÍMITE DE FILAS Y ROBUSTEZ
TABLE_LIMIT = 50 
MAX_LOGIN_ATTEMPTS = 5 # NÚMERO MÁXIMO DE INTENTOS DE LOGIN

# Selector que aparece SÓLO después de un login exitoso (El botón de cookies)
SUCCESS_INDICATOR_SELECTOR = '#truste-consent-button' 

# --- CONSTANTE DE LOGGING Y CARPETAS DE DESCARGA ---
LOG_FILE_NAME_TEMPLATE = "csv/facturas_endesa_log_{cups}.csv"

# Definición de las subcarpetas usando la constante TEMP_DOWNLOAD_ROOT de navegador.py
DOWNLOAD_FOLDERS = {
    'PDF': os.path.join(TEMP_DOWNLOAD_ROOT, 'Facturas_Endesa_PDFs'),
    'XML': os.path.join(TEMP_DOWNLOAD_ROOT, 'Facturas_Endesa_XMLs'),
}
# Aseguramos que todas las carpetas existan
for folder in DOWNLOAD_FOLDERS.values():
    os.makedirs(folder, exist_ok=True)

escribir_log(f"[INFO] Carpetas de descarga configuradas en: {TEMP_DOWNLOAD_ROOT}")


# --- FUNCIONES DE UTILIDAD PARA EXTRACCIÓN Y LOGGING (INALTERADAS) ---

def _clean_and_convert_float(text: str) -> float:
    """Limpia una cadena de texto de importe (ej. '4697.73 €') y la convierte a float."""
    cleaned_text = re.sub(r'[^\d,\.]', '', text).replace(',', '.')
    try:
        return float(cleaned_text)
    except ValueError:
        return 0.0

async def _extraer_texto_de_td(td: Locator) -> str:
    """Extrae texto de una celda de tabla."""
    try:
        lightning_element = td.locator("lightning-formatted-date-time, button, a")
        if await lightning_element.count() > 0:
            return (await lightning_element.first.inner_text()).strip() 
        
        text = await td.inner_text() 
        return text.strip() if "No hay resultados" not in text else ""
    except Exception:
        return ""

def _exportar_log_csv(facturas: list[FacturaEndesaCliente], filepath: str):
    """
    Exporta TODA la metadata y datos detallados de las facturas 
    extraídas (incluyendo el parseo XML) a un archivo CSV.
    """
    # Se recomienda que esta función se mantenga igual o se elimine si el log 
    # se gestiona fuera de la API, pero la mantenemos por ahora.
    fieldnames = [
        # Metadata de la tabla
        'fecha_emision', 'numero_factura', 'fecha_inicio_periodo', 'fecha_fin_periodo', 
        'importe_total_tabla', 'contrato', 'cups', 'secuencial', 'estado_factura', 
        'fraccionamiento', 'tipo_factura', 'descarga_selector',
        # Datos detallados (XML/OCR)
        'mes_facturado', 'tarifa', 'direccion_suministro', 
        'potencia_p1', 'potencia_p2', 'potencia_p3', 'potencia_p4', 
        'potencia_p5', 'potencia_p6', 'importe_de_potencia', 'num_dias', 
        'consumo_kw_p1', 'consumo_kw_p2', 'consumo_kw_p3', 'consumo_kw_p4', 
        'consumo_kw_p5', 'consumo_kw_p6', 'kw_totales', 'importe_consumo', 
        'importe_bono_social', 'importe_impuesto_electrico', 'importe_alquiler_equipos', 
        'importe_otros_conceptos', 'importe_exceso_potencia', 'importe_reactiva', 
        'importe_base_imponible', 'importe_facturado', 'fecha_de_vencimiento', 
        'importe_total_final', 'fecha_de_cobro_en_banco'
    ]
    
    # NOTA: Pydantic.BaseModel tiene un método .dict() o .model_dump()
    # que simplifica esto, pero usamos getattr para la compatibilidad con el código original.
    data_to_write = [{key: getattr(f, key, '') for key in fieldnames} for f in facturas]

    try:
        escribir_log(f"[CSV]")
        
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames, delimiter=';')
            writer.writeheader()
            writer.writerows(data_to_write)
        escribir_log(f"    -> [OK] Log CSV exportado a: {filepath}")
    except Exception as e:
        escribir_log(f"    -> [ERROR CSV] Fallo al exportar CSV: {e}")

async def _wait_for_data_load(page: Page, timeout: int = 20000):
    """Espera a que los datos dinámicos de la primera fila estén cargados y estables."""
    importe_cell_selector = 'table#example1 tbody tr:nth-child(1) td:nth-child(5)'
    estado_cell_selector = 'table#example1 tbody tr:nth-child(1) td:nth-child(9)'
    
    await page.locator(importe_cell_selector).filter(
        has_not_text=re.compile(r"(Cargando|\.\.\.)", re.IGNORECASE)
    ).wait_for(state="visible", timeout=timeout)
    
    await page.locator(estado_cell_selector).filter(
        has_not_text=re.compile(r"(Cargando|\.\.\.)", re.IGNORECASE)
    ).wait_for(state="visible", timeout=timeout)
    
    await page.locator('span.pagination-flex-central').wait_for(state="visible", timeout=5000)


# --- LÓGICA DE DESCARGA LOCAL Y EXTRACCIÓN (INALTERADA) ---

async def _descargar_archivo_fila(page: Page, row_locator: Locator, factura: FacturaEndesaCliente, doc_type: str) -> str | None:
    """
    Intenta descargar un tipo de archivo (PDF, XML) haciendo clic en el botón de la fila
    y guardándolo localmente.
    """
    
    doc_type = doc_type.upper() # PDF, XML
    
    if doc_type == 'PDF':
        button_col_index = 13
        file_ext = 'pdf'
        button_locator_selector = f'button[value*="{factura.descarga_selector}"]' 
    
    elif doc_type == 'XML':
        button_col_index = 11
        file_ext = 'xml'
        button_locator_selector = 'button:has-text("@")' 
    else:
        return None

    try:
        button_locator = row_locator.locator(f'td').nth(button_col_index).locator(button_locator_selector)
        target_folder = DOWNLOAD_FOLDERS[doc_type]
        filename = f"{factura.cups}_{factura.numero_factura}.{file_ext}"
        save_path = os.path.join(target_folder, filename)
        
        async with page.expect_download(timeout=30000) as download_info:
            await button_locator.click(timeout=10000)
            
        download = await download_info.value
        await download.save_as(save_path)
        
        escribir_log(f"    -> [OK] [DESCARGA {doc_type}] Guardado en: {save_path}")
        
        return save_path
        
    except TimeoutError:
        escribir_log(f"   -> [ADVERTENCIA {doc_type}] Timeout (30s) al hacer clic o iniciar la descarga. Omitiendo.")
        return None
    except Exception as e:
        escribir_log(f"   -> [ERROR {doc_type}] Fallo inesperado en la descarga: {e}")
        return None

async def _extraer_pagina_actual(page: Page) -> list[FacturaEndesaCliente]:
    """
    Extrae los datos de todas las filas visibles en la página actual de la tabla de resultados.
    Esta función también activa la descarga local e INTEGRA EL PARSEO XML.
    """
    facturas_pagina: list[FacturaEndesaCliente] = []
    rows = page.locator('table#example1 tbody tr')
    row_count = await rows.count()
    if row_count == 0:
        return facturas_pagina
    
    for i in range(row_count):
        escribir_log(f"[ROW {i+1}] {'='*40}",mostrar_tiempo=False)
        row = rows.nth(i)
        tds = row.locator('td')
        try:
            # Extracción de metadata
            pdf_value = await tds.nth(13).locator('button').get_attribute("value") or ""
            
            # 1. Crear instancia de Factura (solo metadata)
            factura = FacturaEndesaCliente(
                fecha_emision=await _extraer_texto_de_td(tds.nth(0)),
                numero_factura=await _extraer_texto_de_td(tds.nth(1)),
                fecha_inicio_periodo=await _extraer_texto_de_td(tds.nth(2)),
                fecha_fin_periodo=await _extraer_texto_de_td(tds.nth(3)),
                importe_total_tabla=_clean_and_convert_float(await _extraer_texto_de_td(tds.nth(4))),
                contrato=await _extraer_texto_de_td(tds.nth(5)),
                cups=await _extraer_texto_de_td(tds.nth(6)),
                secuencial=await _extraer_texto_de_td(tds.nth(7)),
                estado_factura=await _extraer_texto_de_td(tds.nth(8)),
                fraccionamiento=await _extraer_texto_de_td(tds.nth(9)),
                tipo_factura=await _extraer_texto_de_td(tds.nth(10)),
                descarga_selector=pdf_value, 
            )    
            escribir_log(f"    [OK] Datos extariados para fila {i+1}: Factura {factura.numero_factura} ({factura.cups})")

            # 2. Descargar localmente los 2 archivos
            escribir_log(f"[FILES]")
            
            xml_save_path = await _descargar_archivo_fila(page, row, factura, 'XML')
            await _descargar_archivo_fila(page, row, factura, 'PDF')
           
            
            # 3. INTEGRACIÓN DEL PARSEO XML: Si el XML se descargó, lo procesamos.
            if xml_save_path:
                escribir_log(f"[XML PROCESSING]")
                procesar_xml_local(factura, xml_save_path)
            
            facturas_pagina.append(factura)
            
        except Exception as e:
            escribir_log(f"[DEBUG_EXTRACTION] Fallo al procesar fila {i}: {e}")
            continue

    return facturas_pagina

async def leer_tabla_facturas(page: Page) -> list[FacturaEndesaCliente]:
    """Bucle principal para leer TODAS las páginas de la tabla de resultados."""
    facturas_totales: list[FacturaEndesaCliente] = []
    page_num = 1
    
    tabla_selector = 'div.style-table.contenedorGeneral table#example1'
    await page.wait_for_selector(tabla_selector, timeout=30000)
    
    
    next_button_selector = 'button.pagination-flex-siguiente'
    
    while True:
        try:
            await _wait_for_data_load(page, timeout=10000) 
        except TimeoutError:
            escribir_log("Advertencia: Los datos dinámicos no cargaron en el tiempo esperado. Extrayendo datos incompletos.")
            
        facturas_pagina = await _extraer_pagina_actual(page)
        
        facturas_totales.extend(facturas_pagina)
        
        next_button = page.locator(next_button_selector)
        is_disabled = await next_button.is_disabled()
        
        if is_disabled:
            break
            
        try:
            await next_button.click(timeout=10000)
            await page.wait_for_timeout(500) 
            page_num += 1
        except TimeoutError:
            escribir_log("Error: Fallo al hacer clic en 'SIGUIENTE' (Timeout). Finalizando bucle.")
            break
            
    return list(facturas_totales)


# --- FUNCIONES AUXILIARES DE FLUJO (INALTERADAS) ---

async def _iniciar_sesion(page: Page, username: str, password: str) -> bool:
    """Función interna para manejar la lógica de autenticación en Endesa."""
    
    try:
        await page.wait_for_selector('form.slds-form', timeout=10000)

        # 1. Rellenar campos
        await page.fill('input[name="Username"]', username)
        await page.fill('input[name="password"]', password)
        
        # 2. Hacer click en el botón de iniciar sesión
        login_button_selector = 'button:has-text("ACCEDER")'
        await page.click(login_button_selector)
        
        # 3. Esperar el indicador de éxito (el botón de cookies) en la nueva página
        await page.wait_for_selector(SUCCESS_INDICATOR_SELECTOR, timeout=60000)
        
        return True

    except TimeoutError:
        escribir_log("Fallo en el Login: El tiempo de espera para cargar el indicador de éxito (cookies o dashboard) ha expirado.")
        final_url = page.url
        if final_url.startswith(URL_LOGIN) and await page.is_visible('div[class*="error"]'):
             escribir_log("Razón: Credenciales incorrectas.")
        return False
    except Exception as e:
        escribir_log(f"Error inesperado durante la autenticación: {e}")
        return False

async def _aceptar_cookies(page: Page):
    """Función interna para aceptar el banner de cookies si está presente."""
    cookie_button_selector = '#truste-consent-button'
    
    try:
        await page.wait_for_selector(cookie_button_selector, timeout=5000)
        await page.click(cookie_button_selector)
        escribir_log("Cookies aceptadas.")
        await page.wait_for_timeout(500) 
        
    except TimeoutError:
        escribir_log("Banner de cookies no detectado. Continuando...")
        pass
    except Exception as e:
        escribir_log(f"Error al intentar aceptar las cookies: {e}")

async def realizar_busqueda_facturas(page: Page, grupo_empresarial: str, cups: str, fecha_desde: str, fecha_hasta: str):
    """Aplica los filtros de búsqueda de forma silenciosa."""
    # Eliminamos el log de "INICIO DE BÚSQUEDA" porque ya lo hace la función orquestadora
    
    await page.goto(URL_BUSQUEDA_FACTURAS, wait_until="domcontentloaded")
    main_filter_container_selector = 'div.filter-padd-container'
    await page.wait_for_selector(main_filter_container_selector, timeout=20000)

    # Filtros ejecutados sin escribir logs por cada paso
    await page.click('button[name="periodo"]:has-text("Grupo empresarial")')
    await page.fill('input[placeholder="Buscar"]', grupo_empresarial)
    await page.click(f'span[role="option"] >> text="{grupo_empresarial}"')

    await page.click('button[name="periodo"]:has-text("CUPS20/CUPS22")')
    await page.fill('input[placeholder="Buscar"]', cups)
    await page.click(f'span[role="option"] >> text="{cups}"')
    
    selector_fecha_desde = page.get_by_label("Desde", exact=True).nth(1)
    selector_fecha_hasta = page.get_by_label("Hasta", exact=True).nth(1)
    await selector_fecha_desde.fill(fecha_desde)
    await selector_fecha_hasta.fill(fecha_hasta)

    slider_input = page.get_by_label("Limite")
    await slider_input.fill(str(TABLE_LIMIT)) 
    
    await page.click('button.slds-button_brand:has-text("Buscar")')
    
    tabla_selector = 'div.style-table.contenedorGeneral table#example1'
    await page.wait_for_selector(tabla_selector, timeout=60000)
    # Solo un log final de confirmación
    escribir_log(f"    [OK] Filtros Aplicados con éxito para {cups}, desde {fecha_desde} hasta {fecha_hasta}.")


# --------------------------------------------------------------------------------
# --- FUNCIÓN PRINCIPAL PARA LA API (Acepta Parámetros) ---
# --------------------------------------------------------------------------------

async def ejecutar_robot_api(lista_cups: list, fecha_desde: str, fecha_hasta: str) -> list[FacturaEndesaCliente]:
    """
    Orquesta el proceso batch: realiza un único login y procesa secuencialmente 
    una lista de CUPS acumulando los resultados.
    """
    robot = NavegadorAsync()
    facturas_totales = []
    login_successful = False
    
    try:
        # 1. Fase de Autenticación Única
        escribir_log(f"    [INICIO] Iniciando proceso RPA para {len(lista_cups)} CUPS. \n ",pretexto="\n",mostrar_tiempo=False)
        escribir_log(f"{'='*40} ",mostrar_tiempo=False)
        for attempt in range(1, MAX_LOGIN_ATTEMPTS + 1):
            escribir_log(f"[LOGIN] Intento {attempt}/{MAX_LOGIN_ATTEMPTS}...",pretexto="\n\t")
            await robot.iniciar()
            await robot.goto_url(URL_LOGIN)
            
            login_successful = await _iniciar_sesion(robot.get_page(), USER, PASSWORD)
            
            if login_successful:
                escribir_log(f"[LOGIN] Sesión establecida correctamente.")
                break
            
            escribir_log(f"[ADVERTENCIA] Intento de login {attempt} fallido. Cerrando contexto.")
            await robot.cerrar()
            
            if attempt < MAX_LOGIN_ATTEMPTS:
                await asyncio.sleep(5)
            else:
                raise Exception(f"Fallo crítico: No se pudo acceder al portal tras {MAX_LOGIN_ATTEMPTS} intentos.")

        page = robot.get_page()
        await _aceptar_cookies(page)
        
        # 2. Bucle Iterativo de CUPS
        for index, cups_actual in enumerate(lista_cups, start=1):
            escribir_log(f"{'='*40}",pretexto="\n",mostrar_tiempo=False)
            escribir_log(f"PROCESANDO [{index}/{len(lista_cups)}]: CUPS {cups_actual}")
            escribir_log(f"{'='*80}",mostrar_tiempo=False)
            
            try:
                # Búsqueda y Extracción para el CUPS actual
                escribir_log(f"[BUSQUEDA]")
                await realizar_busqueda_facturas(page, GRUPO_EMPRESARIAL, cups_actual, fecha_desde, fecha_hasta)
                
                escribir_log(f"[EXTRACCIÓN]")
                facturas_cups = await leer_tabla_facturas(page)
                
                if facturas_cups:
                    for f in facturas_cups:
                        f.error_RPA = False  # Añadiremos este campo al modelo
                    facturas_totales.extend(facturas_cups)

                    # Generamos el CSV individual de este CUPS como respaldo
                    log_path = LOG_FILE_NAME_TEMPLATE.format(cups=cups_actual)
                    _exportar_log_csv(facturas_cups, log_path)
                    escribir_log(f"{'='*80}",mostrar_tiempo=False)
                    escribir_log(f"[OK] {len(facturas_cups)} facturas procesadas con éxito para {cups_actual}.")
                    escribir_log(f"{'='*80}",mostrar_tiempo=False)
                
                else:
                    escribir_log(f"{'='*80}",mostrar_tiempo=False)
                    escribir_log(f"[INFO] No se encontraron facturas registradas para {cups_actual} en este rango.")
                    escribir_log(f"{'='*80}",mostrar_tiempo=False)
                    registro_vacio = FacturaEndesaCliente(cups=cups_actual, error_RPA=False, mes_facturado="SIN_FACTURAS")
                    facturas_totales.append(registro_vacio)

            except Exception as e:
                # Captura el error específico del CUPS actual pero permite que el bucle siga con el siguiente
                error_detalle = str(e)
                escribir_log(f"{'='*80}",mostrar_tiempo=False)
                escribir_log(f"[ERROR] Fallo al procesar CUPS {cups_actual}. Detalles del error: \n\t\t{error_detalle}")
                escribir_log(f"{'='*80}",mostrar_tiempo=False)

                registro_error = FacturaEndesaCliente(
                    cups=cups_actual, 
                    error_RPA=True,
                    direccion_suministro=f"ERROR: {error_detalle[:100]}" # Guardamos parte del error
                )
                facturas_totales.append(registro_error)
                
                escribir_log(f"Continuando con el siguiente código de la lista...")
                continue

        escribir_log(f"{'='*80}",pretexto="\n\n",mostrar_tiempo=False)
        escribir_log(f"[OK][FIN] Proceso RPA completado para todos los CUPS.\n\t\tTotal facturas extraídas: {len(facturas_totales)}")
        escribir_log(f"{'='*80}",pretexto="",mostrar_tiempo=False)
        return facturas_totales

    except Exception as e:
        escribir_log(f"🛑 FALLO CRÍTICO EN EL ROBOT: {e}")
        raise e
    finally:
        # El cierre del navegador ocurre una sola vez al terminar todos los CUPS o por error fatal
        if hasattr(robot, 'browser') and robot.browser:
            await robot.cerrar()
            escribir_log("[SISTEMA] Navegador cerrado y recursos liberados.\n\n")

# --------------------------------------------------------------------------------
# --- NUEVA FUNCIÓN PARA LA SEGUNDA LLAMADA API (ACCESO A PDF LOCAL - SÍNCRONA) ---
# --------------------------------------------------------------------------------

def obtener_pdf_local_base64(cups: str, numero_factura: str) -> dict:
    """
    Lee un archivo PDF local. Si no existe, en lugar de dar error, 
    devuelve un mensaje informativo en el campo de base64.
    """
    target_folder = DOWNLOAD_FOLDERS['PDF']
    filename = f"{cups}_{numero_factura}.pdf"
    file_path = os.path.join(target_folder, filename)
    
    # Preparamos la respuesta base
    respuesta = {
        "filename": filename,
        "cups": cups,
        "numero_factura": numero_factura,
        "pdf_base64": "" 
    }

    try:
        if not os.path.exists(file_path):
            escribir_log(f"⚠️ PDF no encontrado en disco: {filename}. Devolviendo placeholder.")
            respuesta["pdf_base64"] = "ERROR: ARCHIVO_NO_ENCONTRADO_EN_SERVIDOR"
            return respuesta

        # Leer el PDF binario
        with open(file_path, 'rb') as pdf_file:
            pdf_data = pdf_file.read()
        
        # Codificar en Base64
        pdf_base64_encoded = base64.b64encode(pdf_data).decode('utf-8')
        respuesta["pdf_base64"] = pdf_base64_encoded
        
        escribir_log(f"✅ PDF '{filename}' enviado con éxito.")
        return respuesta

    except Exception as e:
        escribir_log(f"❌ Error inesperado al leer PDF {filename}: {e}")
        respuesta["pdf_base64"] = f"ERROR_CRITICO_LECTURA: {str(e)}"
        return respuesta

# --- FUNCIÓN DE PRUEBA Y EJECUCIÓN MANUAL ---
# ELIMINAMOS LA LÓGICA DE EJECUCIÓN MANUAL PARA EVITAR CONFLICTOS CON UVICORN
if __name__ == "__main__":
    escribir_log("robotEndesa.py se está ejecutando en modo manual, pero se detiene la ejecución asíncrona automática.")
    escribir_log("Para probar, llame a 'ejecutar_robot_api' manualmente con 'asyncio.run()'.")