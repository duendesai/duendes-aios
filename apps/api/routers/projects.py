from fastapi import APIRouter
from typing import Optional
from pydantic import BaseModel

router = APIRouter(tags=["projects"])


class ProjectUpdate(BaseModel):
    status: Optional[str] = None
    title: Optional[str] = None


@router.get("/projects")
async def list_projects(status: Optional[str] = None, dept: Optional[str] = None):
    return {"projects": []}


@router.get("/projects/{project_id}")
async def get_project(project_id: str):
    return {"project": None}


@router.patch("/projects/{project_id}")
async def update_project(project_id: str, update: ProjectUpdate):
    return {"success": True}
