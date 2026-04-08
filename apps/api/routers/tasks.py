from fastapi import APIRouter
from typing import Optional
from pydantic import BaseModel

router = APIRouter(tags=["tasks"])


class TaskCreate(BaseModel):
    project_id: str
    title: str
    priority: str = "medium"
    assignee_type: str = "oscar"


class TaskUpdate(BaseModel):
    status: Optional[str] = None
    title: Optional[str] = None


@router.get("/projects/{project_id}/tasks")
async def list_tasks(project_id: str):
    return {"tasks": []}


@router.post("/tasks")
async def create_task(task: TaskCreate):
    return {"task": None}


@router.patch("/tasks/{task_id}")
async def update_task(task_id: str, update: TaskUpdate):
    return {"success": True}
