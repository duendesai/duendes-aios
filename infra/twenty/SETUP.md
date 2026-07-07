# Setup de Twenty CRM — VPS dedicado (crm.duendes.net)

Runbook para levantar Twenty CRM self-hosted en el VPS netcup dedicado
(VPS 1000 G12: 4 vCPU / 8 GB RAM / 256 GB NVMe, Ubuntu 24.04, Nuremberg).
Stack aislado: solo Twenty vive aquí, con su propia Postgres y Redis — nada
compartido con infra/hetzner/ ni otros stacks de Duendes.

> Nota sobre el nombre del fichero de entorno: en este repo, `env.example.txt`
> es la plantilla (el harness de Claude Code bloquea la creación/lectura de
> ficheros `.env*` por política de protección de secretos, verificado
> directamente al intentarlo). En el VPS, renómbralo a `.env` en el paso 5.

---

## 1. Hardening inicial

Conéctate por SSH con las credenciales iniciales que da netcup (usuario
`root` + contraseña del panel):

```bash
ssh root@<VPS_IP>
```

Añade tu clave pública para no depender de la contraseña inicial:

```bash
mkdir -p ~/.ssh && chmod 700 ~/.ssh
echo "ssh-ed25519 AAAA...tu_clave_publica..." >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

Verifica que puedes entrar con la clave desde otra terminal ANTES de
deshabilitar la contraseña. Luego edita `/etc/ssh/sshd_config`:

```bash
# Cambia o añade esta línea:
PasswordAuthentication no
```

Reinicia sshd:

```bash
systemctl restart sshd
```

Firewall básico (buena práctica aunque sea un box dedicado):

```bash
ufw allow OpenSSH
ufw allow 80
ufw allow 443
ufw enable
```

(Deshabilitar password auth es opcional pero recomendado — solo hazlo tras
confirmar que el acceso por clave funciona.)

---

## 2. Instalar Docker Engine + compose plugin (Debian 13 trixie)

> El servidor netcup vino con **Debian 13 (trixie) minimal**, no Ubuntu. En
> una release tan reciente el repo APT de Docker puede no tener aún la entrada
> `trixie`, así que el método más fiable en este box es el **script de
> conveniencia oficial** (auto-detecta la distro y añade el repo correcto).

**Recomendado en este box:**

```bash
curl -fsSL https://get.docker.com | sh
```

**Alternativa — repo APT oficial de Debian** (si prefieres controlarlo a mano):

```bash
apt-get update
apt-get install -y ca-certificates curl gnupg
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  tee /etc/apt/sources.list.d/docker.list > /dev/null

apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

Verifica:

```bash
docker --version
docker compose version
```

---

## 3. DNS — antes de tocar Caddy

El dominio `duendes.net` se gestiona en **Squarespace** (backend heredado de
Google Domains tras la migración de Google Domains a Squarespace). Entra al
panel de DNS de Squarespace y crea un registro:

```
Tipo:      A
Host:      crm
Apunta a:  <VPS_IP>
TTL:       automático / el mínimo que permita el panel
```

Esto publica `crm.duendes.net`.

**Verifica la propagación ANTES de levantar el stack:**

```bash
dig +short crm.duendes.net
```

Debe devolver la IP del VPS. Si no resuelve todavía, ESPERA — puede tardar
desde minutos hasta un par de horas según el TTL previo del host. Caddy usa
el reto HTTP-01 de Let's Encrypt para emitir el certificado, y ese reto
falla si el dominio no apunta ya al VPS. No saltes este paso: es la causa
más común de "Caddy no arranca / no hay certificado" en un despliegue nuevo.

---

## 4. Copiar infra/twenty/ al VPS

No hace falta build ni tarball con código propio (a diferencia de
`infra/hetzner/deploy.sh`, que empaqueta `apps/api/`) — aquí solo hay
compose + Caddyfile + plantilla de entorno + scripts de backup, todo lo
demás es imagen oficial de Twenty.

```bash
ssh root@<VPS_IP> "mkdir -p /opt/twenty-crm"
scp docker-compose.yml Caddyfile env.example.txt root@<VPS_IP>:/opt/twenty-crm/
scp -r backup root@<VPS_IP>:/opt/twenty-crm/
```

O con rsync si prefieres sincronizar el directorio completo de una vez
(excluyendo dumps de backup si ya existieran localmente):

```bash
rsync -avz --exclude 'backup/backups' ./ root@<VPS_IP>:/opt/twenty-crm/
```

---

## 5. Configurar .env

En el VPS:

```bash
cd /opt/twenty-crm
cp env.example.txt .env
chmod 600 .env
```

Rellena los valores reales en `.env`:

- `ENCRYPTION_KEY` — genera con `openssl rand -base64 32`. Sin esto el
  server no arranca.
- `PG_DATABASE_PASSWORD` y `POSTGRES_PASSWORD` — una contraseña fuerte SIN
  caracteres especiales (rompe el parseo de la connection string), y deben
  coincidir entre sí. Genera con `openssl rand -hex 24`.
- `PG_DATABASE_URL` — actualiza el password embebido para que coincida con
  el que pusiste en `PG_DATABASE_PASSWORD` / `POSTGRES_PASSWORD` (no hay
  interpolación automática entre variables al usar `env_file` puro).
- `SERVER_URL=https://crm.duendes.net` — confirma que está EXACTAMENTE así
  (https, dominio exacto, sin barra final). Es la única variable de URL
  pública que existe en las versiones actuales de Twenty (no hay
  `FRONT_BASE_URL` separada) — un valor que no coincida con lo que teclea
  el navegador es la causa nº1 del bucle de redirección al hacer login.
- `TAG` — confirma que sigue en `v2.17.0` (o la versión que hayas decidido
  subir conscientemente; revisa el comentario en el propio
  `env.example.txt` y https://github.com/twentyhq/twenty/releases antes de
  desplegar si ha pasado tiempo desde que se escribió este runbook).

---

## 6. Levantar el stack

```bash
docker compose up -d
docker compose ps
```

Todos los servicios deben acabar en estado `healthy` (server, db, redis) o
`running` (worker, caddy — no tienen healthcheck obligatorio). Si `server`
o `db` no llegan a `healthy`:

```bash
docker compose logs server
docker compose logs db
```

Causas típicas: `PG_DATABASE_URL` mal compuesta (revisa que usuario,
password y host coincidan con las variables `PG_DATABASE_*` y `POSTGRES_*`),
o `ENCRYPTION_KEY` vacía (el server no arranca sin ella).

---

## 7. Primer login

Navega a `https://crm.duendes.net`. Crea el workspace y el usuario admin —
en Twenty self-hosted, el primer usuario que se registra pasa a ser el
owner del workspace automáticamente.

---

## 8. Generar la API key de Twenty

Dentro de la app: **Settings → API & Webhooks → API keys** → genera una
nueva, dale un nombre y (opcionalmente) fecha de expiración. Se muestra
UNA SOLA VEZ al crearla — cópiala inmediatamente. Se necesitará más
adelante para integraciones (p.ej. el adaptador FastAPI del resto del
proyecto). Guárdala en un gestor de secretos — NO la commitees en ningún
sitio del repo.

---

## 9. Backups

Ver `backup/`:

- `backup/backup.sh` — dump diario de Postgres con retención configurable
  (por defecto la que trae el script). Configúralo en cron:

  ```bash
  crontab -e
  # Todos los días a las 03:15
  15 3 * * * /opt/twenty-crm/backup/backup.sh >> /var/log/twenty-pg-backup.log 2>&1
  ```

- `backup/restore-test.sh` — restaura el dump más reciente en un contenedor
  Postgres efímero (aislado, no toca el `db` de producción) y verifica que
  los datos son legibles de verdad, no solo que el dump "existe". Ejecuta
  esto manualmente al menos una vez tras el primer backup, y periódicamente
  después (p.ej. mensual) — un backup sin restauración probada no es un
  backup, es una promesa. Un VPS en producción sin este ciclo cerrado no
  está realmente protegido.
