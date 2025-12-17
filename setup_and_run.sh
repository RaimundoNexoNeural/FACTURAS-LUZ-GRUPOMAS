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

# --- VALIDACIÓN DE SEGURIDAD (Añadido) ---
if [ -z "$ENDESA_USER" ] || [ -z "$ENDESA_PASSWORD" ]; then
    echo " ERROR: No se han pasado las credenciales ENDESA_USER o ENDESA_PASSWORD."
    echo " Uso: ENDESA_USER=xxx ENDESA_PASSWORD=xxx ./setup_and_run.sh"
    exit 1
fi

# 1. Verificación de Requisitos e Instalación de Utilidades Básicas
echo "1. Instalando paquetes básicos del sistema (python3-venv, lsof, etc.)..."
if [ ! -f "$REQUIREMENTS_FILE" ] || [ ! -f "api.py" ]; then
    echo " ERROR: Asegúrate de ejecutar este script desde el directorio raíz del proyecto."
    exit 1
fi

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

# 3. Instalar Dependencias de Python
echo "3. Instalando dependencias de Python desde $REQUIREMENTS_FILE..."
pip install --upgrade pip
pip install -r $REQUIREMENTS_FILE

# 4. Instalación de Dependencias del Sistema para Playwright
echo ""
echo "4.  Instalando dependencias del sistema para el navegador..."
sudo ./$VENV_DIR/bin/playwright install-deps

# 5. Configurar e Instalar Navegador de Playwright
echo "5.  Instalando el binario del navegador Chromium..."
playwright install chromium

# 6. Preparación de Directorios de Trabajo
echo "6.  Creando directorios de logs y descargas si no existen..."
mkdir -p logs
mkdir -p csv
mkdir -p temp_endesa_downloads/Facturas_Endesa_PDFs
mkdir -p temp_endesa_downloads/Facturas_Endesa_XMLs
mkdir -p temp_endesa_downloads/Facturas_Endesa_HTMLs

# 7. Desplegar la API con Uvicorn
echo ""
echo "7.  Desplegando la API en http://$UVICORN_HOST:$UVICORN_PORT en segundo plano (nohup)..."

# A. Detener procesos anteriores
PID=$(lsof -t -i :$UVICORN_PORT)
if [ ! -z "$PID" ]; then
    kill -9 "$PID"
    echo "   Proceso Uvicorn anterior (PID $PID) detenido."
fi

# B. Ejecución con nohup (ESTRUCTURA ORIGINAL RECUPERADA)
nohup env ENDESA_USER="$ENDESA_USER" ENDESA_PASSWORD="$ENDESA_PASSWORD" \
      uvicorn $API_MODULE --host $UVICORN_HOST --port $UVICORN_PORT --workers 4 --proxy-headers > api_output.log 2>&1 &

# C. Guardar el PID
echo $! > api_server.pid

echo " CONFIGURACIÓN Y ARRANQUE COMPLETADO."
echo "La API se está ejecutando en segundo plano."
echo "PID: $(cat api_server.pid)"
echo "======================================================="

# Desactivar el entorno virtual
deactivate