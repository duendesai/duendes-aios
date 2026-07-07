#!/usr/bin/env bash
#
# Backup diario de la base de datos de Twenty CRM (VPS dedicado crm.duendes.net).
#
# Uso:
#   ./backup.sh
#
# Qué hace:
# 1. Lee las credenciales de Postgres del .env del stack (../.env por defecto,
#    o exporta PG_DATABASE_USER / PG_DATABASE_NAME antes de llamar al script
#    si quieres sobreescribirlas).
# 2. Ejecuta pg_dump DENTRO del contenedor `db` (vía docker compose exec) en
#    formato custom (--format=custom, no SQL plano): permite restauración
#    selectiva por tabla y restore paralelo con pg_restore -j, y comprime
#    mejor que un .sql plano. El coste es que necesitas pg_restore (no un
#    simple `psql < backup.sql`) para reconstruirlo — ver restore-test.sh.
# 3. Nombra el fichero con timestamp: twenty-backup-YYYY-MM-DD_HHMMSS.dump
# 4. Guarda en ./backups/ (NO se commitea — contiene datos reales del pipeline
#    de ventas de Duendes, potencialmente con PII de prospectos/clientes;
#    no hace falta un .gitignore explícito para este ejercicio, pero recuerda
#    que este directorio no debe subirse nunca a git).
# 5. Purga backups locales más antiguos que RETENTION_DAYS.
#
# ─── Off-boxing (recomendado, no implementado aquí) ─────────────────────────
# Los backups en ./backups/ viven en el MISMO VPS que la base de datos: si el
# disco muere, se pierden ambos. Hay que copiarlos fuera (off-box), por
# ejemplo a un Hetzner Storage Box:
#
#   Opción simple — rsync (sin deduplicación ni cifrado propio, confía en el
#   transporte SSH):
#     rsync -avz backups/ user@storagebox:/twenty-backups/
#
#   Opción recomendada — borg (deduplicado + cifrado en reposo, mucho más
#   eficiente en espacio para backups diarios con poca diferencia entre sí,
#   y cifra antes de salir del VPS — relevante porque estos dumps contienen
#   PII del pipeline comercial de Duendes):
#     borg create storagebox:/repo::twenty-{now} backups/
#
# Ninguna de las dos está implementada todavía porque el Storage Box no está
# provisionado. Cuando lo esté, añade la llamada correspondiente al final de
# este script o como un cron separado.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STACK_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKUP_DIR="$SCRIPT_DIR/backups"
RETENTION_DAYS="${RETENTION_DAYS:-14}"

# Carga PG_DATABASE_USER / PG_DATABASE_NAME del .env del stack si no vienen
# ya exportadas al entorno (permite override puntual: PG_DATABASE_USER=x ./backup.sh)
ENV_FILE="$STACK_DIR/.env"
if [ -f "$ENV_FILE" ]; then
  PG_DATABASE_USER="${PG_DATABASE_USER:-$(grep -E '^PG_DATABASE_USER=' "$ENV_FILE" | head -1 | cut -d= -f2-)}"
  PG_DATABASE_NAME="${PG_DATABASE_NAME:-$(grep -E '^PG_DATABASE_NAME=' "$ENV_FILE" | head -1 | cut -d= -f2-)}"
fi
PG_DATABASE_USER="${PG_DATABASE_USER:-twenty}"
PG_DATABASE_NAME="${PG_DATABASE_NAME:-default}"

mkdir -p "$BACKUP_DIR"

TIMESTAMP="$(date +%Y-%m-%d_%H%M%S)"
OUT_FILE="$BACKUP_DIR/twenty-backup-${TIMESTAMP}.dump"

echo "▶ Volcando base de datos '$PG_DATABASE_NAME' (usuario '$PG_DATABASE_USER') ..."
(
  cd "$STACK_DIR"
  docker compose exec -T db pg_dump -U "$PG_DATABASE_USER" -d "$PG_DATABASE_NAME" --format=custom
) > "$OUT_FILE"

echo "✓ Backup guardado en $OUT_FILE ($(du -h "$OUT_FILE" | cut -f1))"

echo "▶ Purgando backups locales de más de $RETENTION_DAYS días ..."
DELETED=$(find "$BACKUP_DIR" -name 'twenty-backup-*.dump' -mtime "+$RETENTION_DAYS" -print -delete | wc -l | tr -d ' ')
echo "✓ Purgados $DELETED backups antiguos. Backups locales actuales: $(find "$BACKUP_DIR" -name 'twenty-backup-*.dump' | wc -l | tr -d ' ')"

echo ""
echo "Recuerda: este backup vive en el mismo disco que la base de datos."
echo "Off-boxéalo a un Hetzner Storage Box (rsync o borg, ver comentario arriba)."
