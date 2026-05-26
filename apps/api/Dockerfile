# FastAPI para teams.duendes.net — backend SDR power dialer
# Despliegue: container detrás de Caddy en el VPS Hetzner junto a n8n.

FROM python:3.12-slim

# Buenas prácticas: no buffer en logs, no .pyc, pip silencioso
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Sistema mínimo
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Deps Python primero (mejor cache)
COPY requirements.txt .
RUN pip install -r requirements.txt

# Código
COPY . .

# Usuario no-root
RUN useradd --create-home --shell /bin/bash app && chown -R app:app /app
USER app

EXPOSE 8000

# Healthcheck para Docker (Caddy también podrá usarlo)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/health || exit 1

# Entry point minimal: solo carga el router /calls (no el AIOS entero)
CMD ["uvicorn", "teams_main:app", "--host", "0.0.0.0", "--port", "8000"]
