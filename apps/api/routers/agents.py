from fastapi import APIRouter
from typing import Optional
from pydantic import BaseModel

router = APIRouter(tags=["agents"])


class AgentUpdate(BaseModel):
    system_prompt: Optional[str] = None
    model: Optional[str] = None
    is_active: Optional[bool] = None


@router.get("/agents")
async def list_agents():
    depts = [
        ("orchestrator", "Orquestador", "claude-haiku-4-5-20251001"),
        ("cmo", "CMO", "claude-sonnet-4-6"),
        ("sdr", "SDR", "claude-sonnet-4-6"),
        ("cfo", "CFO", "claude-sonnet-4-6"),
        ("cs", "CS", "claude-sonnet-4-6"),
        ("ae", "AE", "claude-sonnet-4-6"),
        ("coo", "COO", "claude-sonnet-4-6"),
    ]
    return {"agents": [{"id": d, "name": n, "model": m} for d, n, m in depts]}


@router.get("/agents/runs")
async def get_runs(dept: Optional[str] = None, limit: int = 20):
    return {"runs": []}


@router.get("/agents/{dept}")
async def get_agent(dept: str):
    return {"agent": {"id": dept}}


@router.patch("/agents/{dept}")
async def update_agent(dept: str, update: AgentUpdate):
    return {"success": True}
