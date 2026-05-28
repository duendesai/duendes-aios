"""
Entry FastAPI para el deploy de teams.duendes.net.

Carga SOLO el router `/calls` (power dialer) — no el AIOS completo.
Se usa en el container Docker del VPS Hetzner detrás de Caddy.

Para desarrollo local con todos los routers del AIOS, usa `main.py`.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import calls, admin

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("teams-api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("teams.duendes.net API started")
    yield
    logger.info("teams.duendes.net API stopped")


app = FastAPI(
    title="teams.duendes.net API",
    description="Power dialer SDR · Airtable + Cal.com + Zadarma",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3001",
        "https://teams.duendes.net",
    ],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "teams-api"}


app.include_router(calls.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
