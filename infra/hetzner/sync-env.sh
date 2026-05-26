#!/usr/bin/env bash
#
# Sincroniza las variables de entorno teams-api del .env LOCAL al .env del VPS.
#
# - Lee las variables de /Users/oscargrana/duendes-aios/.env (no hace eco a stdout)
# - Las añade a /opt/n8n-recepcionista/.env en el VPS via SSH
# - Mantiene POSTGRES_PASSWORD del VPS intacta
# - Idempotente: si ejecuto dos veces, no duplica entradas
#
# Uso:
#   ./infra/hetzner/sync-env.sh [vps_ip]

set -euo pipefail

VPS_IP="${1:-46.225.161.222}"
LOCAL_ENV="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/.env"

if [ ! -f "$LOCAL_ENV" ]; then
  echo "ERROR: No encuentro $LOCAL_ENV" >&2
  exit 1
fi

# Variables que queremos sincronizar
VARS=(
  AIRTABLE_API_KEY
  CALCOM_API_KEY
  CALCOM_EVENT_TYPE_ID
  ZADARMA_API_KEY
  ZADARMA_API_SECRET
  ZADARMA_SIP_USERNAME
  SUPABASE_URL
  SUPABASE_ANON_KEY
)

# Construir bloque con las vars leídas del .env local (sin imprimirlas)
TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

{
  echo ""
  echo "# ─── teams.duendes.net API (auto-sync $(date +%Y-%m-%d)) ───"
  for var in "${VARS[@]}"; do
    # Saca la línea "VAR=valor" del .env local; tolera espacios y comentarios
    line=$(grep -E "^${var}=" "$LOCAL_ENV" | head -1 || true)
    if [ -n "$line" ]; then
      echo "$line"
    fi
  done
} > "$TMP"

# Verificación: número de vars no vacías
COUNT=$(grep -cE "^[A-Z_]+=." "$TMP" || true)
echo "▶ Voy a sincronizar $COUNT variables al VPS $VPS_IP (sin mostrarlas)."

# Estrategia: sustituir el bloque entero si ya existe, o añadir si no
ssh "root@$VPS_IP" bash -s <<'EOF_REMOTE'
set -euo pipefail
ENVF=/opt/n8n-recepcionista/.env
mkdir -p /opt/n8n-recepcionista
touch "$ENVF"
# Quito bloque previo de auto-sync para evitar duplicados
awk '
  /^# ─── teams.duendes.net API \(auto-sync/ { skip=1 }
  !skip { print }
  skip && /^$/ { skip=0 }
' "$ENVF" > "${ENVF}.new"
mv "${ENVF}.new" "$ENVF"
EOF_REMOTE

# Ahora añado el bloque fresco
ssh "root@$VPS_IP" "cat >> /opt/n8n-recepcionista/.env" < "$TMP"

echo "✓ Sincronización OK."
echo "  Verifica en VPS:  ssh root@$VPS_IP 'grep -c \"^[A-Z_]\" /opt/n8n-recepcionista/.env'"
