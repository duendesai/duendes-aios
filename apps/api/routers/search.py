from fastapi import APIRouter

router = APIRouter(tags=["search"])


@router.get("/search")
async def search(q: str):
    return {"results": [], "query": q}
