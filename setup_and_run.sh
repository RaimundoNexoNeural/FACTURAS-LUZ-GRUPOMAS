#!/bin/bash
# filepath: setup_and_run.sh

# Salir inmediatamente si un comando falla
set -e

# --- CONFIGURACIÓN Y VARIABLES DE ENTORNO ---
PROJECT_DIR=$(pwd)
REQUIREMENTS_FILE="requirements.txt"
VENV_DIR="venv"
API_MODULE="api:app"
UVICORN_HOST="0.0.0.0"
UVICORN_PORT="9999"
PYTHON_BIN="python3"

# -----------------------------------------------

echo "======================================================="
echo " INICIANDO CONFIGURACIÓN Y ARRANQUE DE LA API "
echo "======================================================="

# --- VALIDACIÓN DE CREDENCIALES ---
if [ -z "$ENDESA_USER" ] || [ -z "$ENDESA_PASSWORD" ]; then
    echo " ERROR: Credenciales no detectadas. Pásalas al ejecutar el script."
    exit 1
fi

# 1. Instalación de Utilidades Básicas
echo "1. Verificando paquetes del sistema (venv, lsof)..."
sudo apt update
sudo apt install python3-venv python3-pip lsof -y

# 2. Configurar Entorno Virtual
echo "2. Configurando entorno virtual..."
if [ ! -d "$VENV_DIR" ]; then
    $PYTHON_BIN -m venv $VENV_DIR
fi

# Activación
source $VENV_DIR/bin/activate

# 3. Instalar Dependencias
echo "3. Instalando dependencias de Python..."
pip install --upgrade pip
pip install -r $REQUIREMENTS_FILE

# 4. Configuración de Playwright
echo "4. Instalando dependencias del navegador..."
sudo ./$VENV_DIR/bin/playwright install-deps
playwright install chromium

# 5. Preparación de Directorios
echo "5. Creando directorios de trabajo..."
mkdir -p logs csv temp_endesa_downloads/Facturas_Endesa_PDFs temp_endesa_downloads/Facturas_Endesa_XMLs temp_endesa_downloads/Facturas_Endesa_HTMLs

# 6. Limpieza de Procesos Previos
echo "6. Deteniendo procesos en puerto $UVICORN_PORT..."
PID=$(lsof -t -i :$UVICORN_PORT)
if [ ! -z "$PID" ]; then
    kill -9 "$PID"
    echo "   PID $PID terminado."
fi

# 7. Lanzamiento de la API (Versión de 1 solo Worker para n8n)
echo "7. Desplegando API en segundo plano..."
nohup env ENDESA_USER="$ENDESA_USER" ENDESA_PASSWORD="$ENDESA_PASSWORD" \
      uvicorn $API_MODULE --host $UVICORN_HOST --port $UVICORN_PORT > api_output.log 2>&1 &

# Guardar el PID
echo $! > api_server.pid

echo "======================================================="
echo " CONFIGURACIÓN COMPLETADA."
echo " PID: $(cat api_server.pid)"
echo "======================================================="

deactivate