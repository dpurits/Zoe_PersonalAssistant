from fastapi import APIRouter, Form, Response
from twilio.twiml.messaging_response import MessagingResponse

from zoe_assistant.services.assistant_service import AssistantService


router = APIRouter(prefix="/twilio", tags=["twilio"])


@router.post("/whatsapp")
async def whatsapp_webhook(
    Body: str = Form(default=""),
    From: str = Form(default=""),
) -> Response:
    service = AssistantService()
    reply = await service.reply(message=Body, sender=From or "whatsapp")

    response = MessagingResponse()
    response.message(reply)
    return Response(content=str(response), media_type="application/xml")

