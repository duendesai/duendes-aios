from fastapi import APIRouter
from typing import Optional
from pydantic import BaseModel

router = APIRouter(tags=["documents"])


class DocumentUpdate(BaseModel):
    content_md: Optional[str] = None
    title: Optional[str] = None


@router.get("/documents")
async def list_documents(project_id: Optional[str] = None):
    return {"documents": []}


@router.get("/documents/{doc_id}")
async def get_document(doc_id: str):
    return {"document": None}


@router.patch("/documents/{doc_id}")
async def update_document(doc_id: str, update: DocumentUpdate):
    return {"success": True}


@router.post("/documents/{doc_id}/execute")
async def execute_document(doc_id: str):
    return {"status": "queued", "doc_id": doc_id}


@router.get("/documents/{doc_id}/versions")
async def get_versions(doc_id: str):
    return {"versions": []}
