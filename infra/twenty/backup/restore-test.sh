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
#   ./restore-test.sh                          # usa el dump más reciente en ./backups/
#   ./restore-test.sh /ruta/a/otro.dump        # usa un dump concreto
#   ./restore-test.sh --check-email foo@bar.com  # además, verifica que existe
#                                                 # una persona con ese email
#
# TODO (Oscar): en este momento el workspace de Twenty todavía no tiene datos
# reales, así que no hay un "email conocido" que verificar de forma fiable.
# Cuando el pipeline comercial tenga datos reales, añade una llamada regular
# a este script con --check-email apuntando a un contacto que sepas que debe
# existir (p.ej. un lead que llevas meses trabajando), como segunda capa de
# verificación además del chequeo de esquema.

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

# ─── Sanity check 1: existe la tabla `person` con columnas clave ────────────
# No comparamos el esquema exacto: cada workspace de Twenty puede tener
# campos custom distintos añadidos desde la UI, así que un chequeo de
# "columnas exactas" sería frágil. En vez de eso, verificamos que la tabla
# existe y que tiene un número mínimo de columnas esperadas (id, name-ish,
# email-ish), que es resiliente a customización del workspace.
echo "▶ Verificando que la tabla 'person' existe y tiene columnas mínimas esperadas ..."
COLUMN_COUNT=$(docker exec "$CONTAINER_NAME" psql -U postgres -d restore_test -tAc \
  "SELECT count(*) FROM information_schema.columns WHERE table_name = 'person';")

if [ "${COLUMN_COUNT:-0}" -lt 5 ]; then
  echo "ERROR: la tabla 'person' no existe o tiene muy pocas columnas ($COLUMN_COUNT). Restore sospechoso." >&2
  exit 1
fi
echo "✓ Tabla 'person' presente con $COLUMN_COUNT columnas."

# ─── Sanity check 2 (opcional): al menos una fila conocida es consultable ───
if [ -n "$CHECK_EMAIL" ]; then
  echo "▶ Verificando que existe una persona con email '$CHECK_EMAIL' ..."
  MATCH_COUNT=$(docker exec "$CONTAINER_NAME" psql -U postgres -d restore_test -tAc \
    "SELECT count(*) FROM person WHERE \"emailsPrimaryEmail\" = '$CHECK_EMAIL';" 2>/dev/null || echo "0")
  # Nota: el nombre exacto de la columna de email primario puede variar según
  # versión de Twenty (emailsPrimaryEmail es el nombre en el esquema estándar
  # de contactos). Si esta query falla por nombre de columna, revisa el
  # esquema real con: \d person dentro del contenedor efímero.
  if [ "${MATCH_COUNT:-0}" -lt 1 ]; then
    echo "AVISO: no se encontró ninguna persona con email '$CHECK_EMAIL'. Revisa manualmente." >&2
  else
    echo "✓ Encontrada al menos 1 persona con ese email."
  fi
else
  echo "( Sin --check-email: sáltate este chequeo hasta tener datos reales en el pipeline — ver TODO al inicio del script )"
fi

echo ""
echo "✓ Restore-test completado. El backup $DUMP_FILE parece restaurable."
