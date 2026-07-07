#!/usr/bin/env bash
#
# Verificación de restauración de backups de Twenty CRM.
#
# Por qué existe: un backup que nunca se ha restaurado no es un backup de
# fiar, es una esperanza. Este script es el "hard gate": levanta un Postgres
# EFÍMERO en un contenedor aparte (NUNCA toca el contenedor `db` de
# producción), restaura el dump más reciente (o el que le indiques) y corre
# unas queries mínimas de sanity-check. Si algo falla, el backup no sirve y
# hay que investigar ANTES de que haga falta un restore real.
#
# Uso:
#   ./restore-test.sh                            # usa el dump más reciente en ./backups/
#   ./restore-test.sh /ruta/a/otro.dump          # usa un dump concreto
#   ./restore-test.sh --check-email foo@bar.com  # además, verifica que existe una
#                                                 # persona con ese email Y que sus
#                                                 # custom fields del pipeline tienen valor
#
# Recomendado: corre esto periódicamente con --check-email apuntando a un lead
# real que sepas que debe existir (p.ej. avancerehabilitacionsl@hotmail.com),
# como segunda capa de verificación además del chequeo de esquema.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_DIR="$SCRIPT_DIR/backups"
CONTAINER_NAME="twenty-restore-test"
TEST_DB_PASSWORD="restore-test-only"
TEST_PORT="55432"
CHECK_EMAIL=""
DUMP_FILE=""

# ─── Parseo de argumentos ────────────────────────────────────────────────────
while [ $# -gt 0 ]; do
  case "$1" in
    --check-email)
      CHECK_EMAIL="$2"
      shift 2
      ;;
    *)
      DUMP_FILE="$1"
      shift
      ;;
  esac
done

if [ -z "$DUMP_FILE" ]; then
  DUMP_FILE="$(find "$BACKUP_DIR" -name 'twenty-backup-*.dump' | sort | tail -1)"
fi

if [ -z "$DUMP_FILE" ] || [ ! -f "$DUMP_FILE" ]; then
  echo "ERROR: no encuentro ningún dump que restaurar (busqué en $BACKUP_DIR)." >&2
  exit 1
fi

echo "▶ Voy a verificar el restore de: $DUMP_FILE"

# ─── Limpieza garantizada del contenedor efímero, pase lo que pase ──────────
cleanup() {
  echo "▶ Limpiando contenedor efímero '$CONTAINER_NAME' ..."
  docker rm -f "$CONTAINER_NAME" > /dev/null 2>&1 || true
}
trap cleanup EXIT

echo "▶ Levantando Postgres efímero (puerto local $TEST_PORT, aislado de producción) ..."
docker run --rm -d \
  --name "$CONTAINER_NAME" \
  -e POSTGRES_PASSWORD="$TEST_DB_PASSWORD" \
  -e POSTGRES_DB=restore_test \
  -p "127.0.0.1:${TEST_PORT}:5432" \
  postgres:16 > /dev/null

echo "▶ Esperando a que el Postgres efímero acepte conexiones ..."
for i in $(seq 1 30); do
  if docker exec "$CONTAINER_NAME" pg_isready -U postgres > /dev/null 2>&1; then
    break
  fi
  sleep 1
  if [ "$i" -eq 30 ]; then
    echo "ERROR: el Postgres efímero no arrancó a tiempo." >&2
    exit 1
  fi
done
echo "✓ Postgres efímero listo."

echo "▶ Restaurando $DUMP_FILE dentro del contenedor efímero ..."
docker cp "$DUMP_FILE" "$CONTAINER_NAME:/tmp/restore.dump"
docker exec "$CONTAINER_NAME" pg_restore -U postgres -d restore_test --no-owner --no-privileges /tmp/restore.dump || {
  echo "ERROR: pg_restore falló. El backup podría estar corrupto o incompleto." >&2
  exit 1
}
echo "✓ Restauración completada sin errores fatales."

# ─── Descubrir el esquema del workspace (dinámico: workspace_<id>) ──────────
# Twenty guarda los datos de negocio en un esquema por workspace, NO en public.
# El nombre cambia en cada instalación, así que lo descubrimos en runtime (esto
# es lo que hacía fallar el chequeo de email: buscaba `person` en public).
SCHEMA=$(docker exec "$CONTAINER_NAME" psql -U postgres -d restore_test -tAc \
  "SELECT table_schema FROM information_schema.tables WHERE table_name = 'person' AND table_schema LIKE 'workspace%' ORDER BY 1 LIMIT 1;" | tr -d '[:space:]')

if [ -z "$SCHEMA" ]; then
  echo "ERROR: no encuentro la tabla 'person' en ningún esquema workspace_. Restore sospechoso." >&2
  exit 1
fi
echo "✓ Esquema de workspace detectado: $SCHEMA"

# ─── Sanity check 1: la tabla `person` existe con columnas mínimas ──────────
COLUMN_COUNT=$(docker exec "$CONTAINER_NAME" psql -U postgres -d restore_test -tAc \
  "SELECT count(*) FROM information_schema.columns WHERE table_schema = '$SCHEMA' AND table_name = 'person';")

if [ "${COLUMN_COUNT:-0}" -lt 5 ]; then
  echo "ERROR: la tabla 'person' tiene muy pocas columnas ($COLUMN_COUNT). Restore sospechoso." >&2
  exit 1
fi
echo "✓ Tabla 'person' presente con $COLUMN_COUNT columnas."

# ─── Sanity check 2 (opcional): una fila conocida CON sus custom fields ─────
# No basta con que el email exista: verificamos que los custom fields del
# pipeline (sector, estadoDemo) tienen VALOR. Es lo que protege el backup
# (hallazgo #7 de la auditoría: un restore que trae la tabla sin los datos de
# los custom fields daría luz verde en falso).
if [ -n "$CHECK_EMAIL" ]; then
  echo "▶ Verificando la persona '$CHECK_EMAIL' y sus custom fields ..."
  # -tA => campos separados por '|'. Sin swallow de errores: si la query falla,
  # queremos verlo, no confundir un error con "no existe".
  ROW=$(docker exec "$CONTAINER_NAME" psql -U postgres -d restore_test -tAc \
    "SELECT sector, \"estadoDemo\" FROM \"$SCHEMA\".person WHERE \"emailsPrimaryEmail\" = '$CHECK_EMAIL' LIMIT 1;")
  if [ -z "$ROW" ]; then
    echo "AVISO: no se encontró ninguna persona con email '$CHECK_EMAIL'. Revisa manualmente." >&2
  else
    SECTOR="${ROW%%|*}"
    ESTADO="${ROW##*|}"
    if [ -n "$SECTOR" ] && [ -n "$ESTADO" ]; then
      echo "✓ Persona encontrada con custom fields poblados (sector=$SECTOR estadoDemo=$ESTADO)."
    else
      echo "AVISO: persona encontrada pero con custom fields vacíos (sector='$SECTOR' estadoDemo='$ESTADO'). El restore podría no traer los datos del pipeline." >&2
    fi
  fi
else
  echo "( Sin --check-email: pásalo con un email real, p.ej. --check-email lead@cliente.com )"
fi

echo ""
echo "✓ Restore-test completado. El backup $DUMP_FILE parece restaurable."
