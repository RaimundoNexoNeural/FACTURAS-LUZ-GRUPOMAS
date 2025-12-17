#!/bin/bash
# filepath: setup_and_run.sh

# Salir inmediatamente si un comando falla
set -e

# --- CONFIGURACIÓN Y VARIABLES DE ENTORNO ---
PROJECT_DIR=$(pwd)
REQUIREMENTS_FILE="requirements.txt"
VENV_DIR="venv"
API_MODULE="api:app"
UVICORN_HOST="0.0.0.0" # Escucha en todas las interfaces (IP pública)
UVICORN_PORT="9999" # Puerto solicitado

# Usamos python3, que es 3.11.2.
PYTHON_BIN="python3"

# -----------------------------------------------

echo "======================================================="
echo " INICIANDO CONFIGURACIÓN Y ARRANQUE DE LA API "
echo "======================================================="

# 1. Verificación de Requisitos e Instalación de Utilidades Básicas
echo "1. Instalando paquetes básicos del sistema (python3-venv, lsof, etc.)..."
if [ ! -f "$REQUIREMENTS_FILE" ] || [ ! -f "api.py" ]; then
    echo " ERROR: Asegúrate de ejecutar este script desde el directorio raíz del proyecto."
    exit 1
fi

# Instala paquetes de sistema que son estrictamente necesarios para el entorno.
sudo apt update
sudo apt install python3-venv python3-pip lsof -y


# 2. Crear y Activar Entorno Virtual
echo ""
echo "2.  Configurando entorno virtual '$VENV_DIR'..."
if [ ! -d "$VENV_DIR" ]; then
    $PYTHON_BIN -m venv $VENV_DIR
fi

# Activación del entorno
echo "   Activando entorno virtual..."
source $VENV_DIR/bin/activate

# 3. Instalar Dependencias de Python (Incluye Playwright)
echo "3. Instalando dependencias de Python desde $REQUIREMENTS_FILE (incluyendo Playwright)..."
pip install --upgrade pip
# Esto instala la librería 'playwright' en el venv.
pip install -r $REQUIREMENTS_FILE


# 4. Instalación de Dependencias del Sistema (Librerías de Linux para Playwright)
echo ""
echo "4.  Instalando dependencias del sistema para el navegador (requiere sudo)..."
#  CORRECCIÓN: Usamos la ruta completa del binario dentro del VENV.
sudo ./$VENV_DIR/bin/playwright install-deps


# 5. Configurar e Instalar Navegador de Playwright
echo "5.  Instalando el binario del navegador Chromium..."
# Instala el binario del navegador (Chromium) en el cache local de Playwright.
playwright install chromium


# 6. Preparación de Directorios de Trabajo
echo "6.  Creando directorios de logs y descargas si no existen..."
mkdir -p logs
mkdir -p csv
mkdir -p temp_endesa_downloads/Facturas_Endesa_PDFs
mkdir -p temp_endesa_downloads/Facturas_Endesa_XMLs


# 7. Desplegar la API con Uvicorn (Persistencia con nohup)
echo ""
echo "7.  Desplegando la API en http://$UVICORN_HOST:$UVICORN_PORT en segundo plano (nohup)..."

# A. Detener procesos anteriores que usen el puerto
echo "   Deteniendo procesos anteriores en el puerto $UVICORN_PORT..."
PID=$(lsof -t -i :$UVICORN_PORT)
if [ ! -z "$PID" ]; then
    kill -9 "$PID"
    echo "   Proceso Uvicorn anterior (PID $PID) detenido."
fi

# B. Ejecución con nohup y variables de entorno
nohup env ENDESA_USER="$ENDESA_USER" ENDESA_PASSWORD="$ENDESA_PASSWORD" \
      uvicorn $API_MODULE --host $UVICORN_HOST --port $UVICORN_PORT --workers 4 --proxy-headers > api_output.log 2>&1 &

# C. Guardar el PID para la gestión posterior
echo $! > api_server.pid

echo " CONFIGURACIÓN Y ARRANQUE COMPLETADO."
echo "La API se está ejecutando en segundo plano en http://[IP_PUBLICA]:$UVICORN_PORT."
echo "PID: $(<api_server.pid)"
echo "Revisa 'api_output.log' para la salida de Uvicorn."
echo "======================================================="

# Desactivar el entorno virtual
deactivate