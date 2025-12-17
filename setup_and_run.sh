#!/bin/bash
# filepath: setup_and_run.sh
set -e

# --- CONFIGURACIÓN ---
PROJECT_DIR=$(pwd)
REQUIREMENTS_FILE="requirements.txt"
VENV_DIR="venv"
API_MODULE="api:app"
UVICORN_HOST="0.0.0.0"
UVICORN_PORT="9999"
PYTHON_BIN="python3"

# 🛡️ SEGURIDAD: Verificar credenciales
if [ -z "$ENDESA_USER" ] || [ -z "$ENDESA_PASSWORD" ]; then
    echo "❌ ERROR: Credenciales no detectadas en el entorno."
    echo "Uso: ENDESA_USER=usuario ENDESA_PASSWORD=clave ./setup_and_run.sh"
    exit 1
fi

echo "======================================================="
echo " 🚀 INICIANDO CONFIGURACIÓN Y ARRANQUE DE LA API 🚀 "
echo "======================================================="

# 1. Utilidades básicas
sudo apt update && sudo apt install python3-venv python3-pip lsof -y

# 2. Entorno Virtual
if [ ! -d "$VENV_DIR" ]; then
    $PYTHON_BIN -m venv $VENV_DIR
fi
source $VENV_DIR/bin/activate

# 3. Dependencias
pip install --upgrade pip
pip install -r $REQUIREMENTS_FILE

# 4. Playwright
sudo ./$VENV_DIR/bin/playwright install-deps
playwright install chromium

# 5. Directorios
mkdir -p logs csv temp_endesa_downloads/Facturas_Endesa_PDFs temp_endesa_downloads/Facturas_Endesa_XMLs temp_endesa_downloads/Facturas_Endesa_HTMLs

# 6. Limpieza de puerto
PID=$(lsof -t -i :$UVICORN_PORT)
if [ ! -z "$PID" ]; then
    kill -9 "$PID"
    echo "   Proceso anterior en puerto $UVICORN_PORT detenido."
fi

# 7. Lanzamiento con verificación (Workers reducidos a 2 para estabilidad)
echo "🚀 Lanzando Uvicorn en segundo plano..."
nohup env ENDESA_USER="$ENDESA_USER" ENDESA_PASSWORD="$ENDESA_PASSWORD" \
      uvicorn $API_MODULE --host $UVICORN_HOST --port $UVICORN_PORT --workers 2 --proxy-headers > api_output.log 2>&1 &

# Guardar el PID
echo $! > api_server.pid

# Pequeña espera para confirmar que no se cierra
sleep 2
if ps -p $(cat api_server.pid) > /dev/null; then
    echo "✅ API ARRANCADA CON ÉXITO."
    echo "URL: http://93.93.64.20:9999/docs"
    echo "PID: $(cat api_server.pid)"
else
    echo "❌ ERROR: La API se cerró tras el arranque. Revisa api_output.log"
    exit 1
fi

deactivate