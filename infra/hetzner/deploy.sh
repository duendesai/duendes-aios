#!/usr/bin/env bash
#
# Deploy del backend teams-api al VPS Hetzner.
#
# Uso:
#   ./infra/hetzner/deploy.sh [vps_ip]
#
# Por defecto usa 46.225.161.222. Asume que tienes SSH a `root@$IP`.
#
# Lo que hace:
# 1. Empaqueta apps/api/ en un tar.gz local.
# 2. Lo sube a /tmp del VPS.
# 3. Lo extrae en /opt/n8n-recepcionista/teams-api/ (sobreescribiendo).
# 4. Reconstruye el container teams-api y lo reinicia.
#
# NO toca n8n ni postgres. NO toca el Caddyfile (eso se hace una sola vez).

set -euo pipefail

VPS_IP="${1:-46.225.161.222}"
REMOTE_DIR="/opt/n8n-recepcionista"
REMOTE_API_DIR="$REMOTE_DIR/teams-api"
LOCAL_REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TARBALL="/tmp/teams-api-$(date +%s).tar.gz"

echo "▶ Empaquetando apps/api/ ..."
tar --exclude='__pycache__' --exclude='*.pyc' --exclude='.venv' --exclude='.env' \
    -czf "$TARBALL" -C "$LOCAL_REPO/apps" api

echo "▶ Subiendo a $VPS_IP:/tmp/ ..."
scp "$TARBALL" "root@$VPS_IP:/tmp/teams-api.tar.gz"

echo "▶ Extrayendo en $REMOTE_API_DIR y reconstruyendo container ..."
ssh "root@$VPS_IP" bash -s <<EOF
set -euo pipefail
mkdir -p "$REMOTE_API_DIR"
# Limpio extra silenciosamente para que rsync-like funcione (no borra .env por estar excluido)
find "$REMOTE_API_DIR" -mindepth 1 -maxdepth 1 ! -name '.env' -exec rm -rf {} + 2>/dev/null || true
tar -xzf /tmp/teams-api.tar.gz -C "$REMOTE_API_DIR" --strip-components=1
rm /tmp/teams-api.tar.gz

cd "$REMOTE_DIR"
docker compose up -d --build teams-api
echo ""
echo "▶ Estado:"
docker compose ps teams-api
EOF

rm "$TARBALL"
echo "✓ Deploy completo."
echo "  Comprueba: curl https://api.duendes.net/health"
