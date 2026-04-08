from fastapi import APIRouter
import logging

router = APIRouter(tags=["dashboard"])
logger = logging.getLogger("aios-api")


@router.get("/dashboard/feed")
async def get_feed(limit: int = 20):
    return {"feed": [], "total": 0}


@router.get("/dashboard/kpis")
async def get_kpis():
    return {
        "active_projects": 0,
        "pending_tasks": 0,
        "running_agents": 0,
        "cost_today_usd": 0.0,
    }


@router.get("/dashboard/agents")
async def get_agents_status():
    depts = ["orchestrator", "cmo", "sdr", "cfo", "cs", "ae", "coo"]
    return {
        "agents": [
            {"dept": d, "status": "idle", "last_run": None}
            for d in depts
        ]
    }
