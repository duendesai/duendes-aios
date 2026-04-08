from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import Optional
import logging

router = APIRouter(tags=["chat"])
logger = logging.getLogger("aios-api")


class SendMessageRequest(BaseModel):
    dept: str
    message: str
    conversation_id: Optional[str] = None


@router.websocket("/ws/chat/{dept}")
async def websocket_chat(websocket: WebSocket, dept: str):
    await websocket.accept()
    logger.info(f"WebSocket connected: dept={dept}")
    try:
        while True:
            data = await websocket.receive_json()
            message = data.get("message", "")
            try:
                from services.agent_service import run_agent
                response = await run_agent(dept, message)
            except Exception as e:
                logger.error(f"Agent error: {e}")
                response = f"Error al procesar: {str(e)}"

            await websocket.send_json({
                "type": "message",
                "role": "assistant",
                "content": response,
                "dept": dept,
            })
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: dept={dept}")


@router.post("/chat/send")
async def send_message(req: SendMessageRequest):
    try:
        from services.agent_service import run_agent
        response = await run_agent(req.dept, req.message)
        return {"response": response, "dept": req.dept}
    except Exception as e:
        logger.error(f"Chat error: {e}")
        return {"error": str(e)}, 500


@router.get("/conversations")
async def list_conversations(dept: Optional[str] = None):
    # Placeholder — will query Supabase in Phase 1
    return {"conversations": []}
