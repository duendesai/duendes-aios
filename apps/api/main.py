import sys
import logging
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from routers import chat, dashboard, projects, tasks, documents, agents, search

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("aios-api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("AIOS API started")
    yield
    logger.info("AIOS API stopped")


app = FastAPI(title="AIOS API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://*.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "aios-api"}


app.include_router(chat.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(projects.router, prefix="/api")
app.include_router(tasks.router, prefix="/api")
app.include_router(documents.router, prefix="/api")
app.include_router(agents.router, prefix="/api")
app.include_router(search.router, prefix="/api")
