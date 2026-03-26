# Duendes AIOS — Telegram Bot

Bot: @DuendesCRM_bot
Corre en modo long-polling localmente en el Mac. Solo acepta mensajes de Oscar (whitelist por user_id).

## Instalación

```bash
cd ~/duendes-aios/scripts
pip install -r requirements.txt
```

## Configuración

Edita `~/duendes-aios/.env` y añade tus claves reales:

```
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
```

El token de Telegram ya está configurado.

## Arrancar el bot

```bash
cd ~/duendes-aios/scripts
python bot.py
```

El bot queda corriendo en terminal. Los logs se guardan en `scripts/logs/bot.log`.

## Comandos disponibles

| Comando | Descripción |
|---------|-------------|
| `/start` | Bienvenida + reinicia historial de conversación |
| `/status` | Muestra qué archivos del Context OS tiene cargados |
| `/reload` | Recarga el Context OS sin reiniciar el bot |
| `/tareas`, `/nueva`, `/hecho`, `/pendiente` | COO: gestión de tareas |
| `/leads`, `/lead`, `/leadstatus`, `/email`, `/followup`, `/leadnota` | SDR: pipeline de prospectos + email frío |
| `/post`, `/postguardar`, `/posts`, `/poststatus` | CMO: borradores y estado de contenido |
| `/deals`, `/deal`, `/dealstatus`, `/propuesta`, `/objecion` | AE: oportunidades de cierre + propuestas |

## Funcionalidades

- **Texto**: Envía cualquier mensaje de texto — responde usando Claude (claude-sonnet-4-6) con el Context OS completo como system prompt.
- **Voice notes**: Transcribe con Whisper (OpenAI) y pasa el texto a Claude. La respuesta incluye la transcripción.
- **Historial**: Mantiene los últimos 10 intercambios por sesión. Se resetea con `/start` o tras 2 horas de inactividad.
- **Whitelist**: Solo responde a Oscar (user_id 1848279273). Cualquier otro usuario recibe "No autorizado."

## Context OS cargado automáticamente

Al arrancar (y con `/reload`) lee:
- `CLAUDE.md` (raíz del proyecto)
- `context/*.md`
- `equipo/*.md`

## Parar el bot

`Ctrl+C` en la terminal donde corre.
