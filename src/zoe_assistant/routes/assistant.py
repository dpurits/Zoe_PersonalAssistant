from fastapi import APIRouter
from pydantic import BaseModel

from zoe_assistant.services.assistant_service import AssistantService


router = APIRouter(prefix="/assistant", tags=["assistant"])


class ChatRequest(BaseModel):
    message: str
    sender: str = "local"


class ChatResponse(BaseModel):
    reply: str


@router.post("/chat")
async def chat(request: ChatRequest) -> ChatResponse:
    service = AssistantService()
    reply = await service.reply(message=request.message, sender=request.sender)
    return ChatResponse(reply=reply)

