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

echo "Iniciando despliegue de API..."

# 1. ACTUALIZACION DE DEPENDENCIAS DE SISTEMA
sudo apt update && sudo apt install python3-venv python3-pip lsof -y

# 2. GESTION DE ENTORNO VIRTUAL
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
fi

# 3. INSTALACION DE LIBRERIAS
"$VENV_DIR/bin/pip" install --upgrade pip
"$VENV_DIR/bin/pip" install -r requirements.txt

# 4. CONFIGURACION DE PLAYWRIGHT
sudo "$VENV_DIR/bin/playwright" install-deps
"$VENV_DIR/bin/playwright" install chromium

# 5. ESTRUCTURA DE DIRECTORIOS
mkdir -p logs csv temp_endesa_downloads/Facturas_Endesa_PDFs temp_endesa_downloads/Facturas_Endesa_XMLs temp_endesa_downloads/Facturas_Endesa_HTMLs

# 6. CIERRE DE PROCESOS PREVIOS
PID=$(lsof -t -i :$UVICORN_PORT)
if [ ! -z "$PID" ]; then
    kill -9 "$PID"
    echo "Proceso previo en puerto $UVICORN_PORT (PID $PID) finalizado."
fi

# 7. EJECUCION EN SEGUNDO PLANO
# Se utiliza la ruta absoluta al binario de uvicorn para evitar fallos de PATH.
# Se reduce a 2 workers para optimizar el consumo de recursos en el servidor.
nohup env ENDESA_USER="$ENDESA_USER" ENDESA_PASSWORD="$ENDESA_PASSWORD" \
    "$VENV_DIR/bin/uvicorn" $API_MODULE \
    --host $UVICORN_HOST \
    --port $UVICORN_PORT \
    --workers 2 \
    --proxy-headers > api_output.log 2>&1 &

# REGISTRO DEL PID
echo $! > api_server.pid

# 8. VERIFICACION DE ESTABILIDAD
echo "Verificando estado del proceso..."
sleep 5

if ps -p $(cat api_server.pid) > /dev/null; then
    echo "DESPLIEGUE EXITOSO."
    echo "Endpoint: http://$UVICORN_HOST:$UVICORN_PORT/docs"
    echo "PID: $(cat api_server.pid)"
else
    echo "ERROR: El proceso no se mantuvo estable tras el lanzamiento."
    echo "Ultimos registros de api_output.log:"
    tail -n 20 api_output.log
    exit 1
fi