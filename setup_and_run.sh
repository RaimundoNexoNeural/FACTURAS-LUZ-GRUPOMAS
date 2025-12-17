#!/bin/bash
# filepath: setup_and_run.sh
set -e

# --- CONFIGURACION ---
PROJECT_DIR=$(pwd)
VENV_DIR="$PROJECT_DIR/venv"
API_MODULE="api:app"
UVICORN_HOST="0.0.0.0"
UVICORN_PORT="9999"

# VERIFICACION DE CREDENCIALES
if [ -z "$ENDESA_USER" ] || [ -z "$ENDESA_PASSWORD" ]; then
    echo "ERROR: Variables de entorno ENDESA_USER o ENDESA_PASSWORD no definidas."
    exit 1
fi

# 1. ACTUALIZACION DE DEPENDENCIAS
sudo apt update && sudo apt install python3-venv python3-pip lsof -y

# 2. ENTORNO VIRTUAL
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
fi

# 3. INSTALACION DE LIBRERIAS
"$VENV_DIR/bin/pip" install --upgrade pip
"$VENV_DIR/bin/pip" install -r requirements.txt
sudo "$VENV_DIR/bin/playwright" install-deps
"$VENV_DIR/bin/playwright" install chromium

# 4. DIRECTORIOS
mkdir -p logs csv temp_endesa_downloads/Facturas_Endesa_PDFs temp_endesa_downloads/Facturas_Endesa_XMLs temp_endesa_downloads/Facturas_Endesa_HTMLs

# 5. LIMPIEZA DE PUERTO
PID=$(lsof -t -i :$UVICORN_PORT)
if [ ! -z "$PID" ]; then
    kill -9 "$PID"
fi

# 6. LANZAMIENTO (ESTRUCTURA REFORMULADA)
# Usamos 'python3 -m uvicorn' directamente desde el venv, que es más estable que el binario suelto.
echo "Lanzando servicio..."
nohup "$VENV_DIR/bin/python3" -m uvicorn $API_MODULE \
    --host $UVICORN_HOST \
    --port $UVICORN_PORT \
    --workers 2 \
    --proxy-headers > api_output.log 2>&1 &

# GUARDAR PID Y VERIFICAR
echo $! > api_server.pid
sleep 5

if ps -p $(cat api_server.pid) > /dev/null; then
    echo "ESTADO: Ejecutándose correctamente."
    echo "PID: $(cat api_server.pid)"
else
    echo "ERROR: El proceso falló al iniciar. Contenido de api_output.log:"
    cat api_output.log
    exit 1
fi