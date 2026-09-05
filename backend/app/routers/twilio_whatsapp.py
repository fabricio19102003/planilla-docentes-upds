"""Public Twilio callbacks for official WhatsApp billing notifications."""

from urllib.parse import parse_qsl

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.services.whatsapp_webhook_service import WhatsAppWebhookService

router = APIRouter(prefix="/api/twilio/whatsapp", tags=["twilio-whatsapp"])


async def _fields(request: Request) -> list[tuple[str, str]]:
    return parse_qsl((await request.body()).decode("utf-8"), keep_blank_values=True)


def _service(db: Session) -> WhatsAppWebhookService:
    return WhatsAppWebhookService(
        db,
        auth_token=settings.TWILIO_AUTH_TOKEN,
        status_url=settings.TWILIO_STATUS_CALLBACK_URL,
        inbound_url=settings.TWILIO_INBOUND_CALLBACK_URL,
    )


@router.post("/status", status_code=status.HTTP_204_NO_CONTENT)
async def status_callback(request: Request, db: Session = Depends(get_db)) -> Response:
    outcome = _service(db).process_status(await _fields(request), request.headers.get("X-Twilio-Signature"), request.url.query)
    if outcome == "rejected":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid Twilio signature")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/inbound", status_code=status.HTTP_204_NO_CONTENT)
async def inbound_callback(request: Request, db: Session = Depends(get_db)) -> Response:
    outcome = _service(db).process_inbound(await _fields(request), request.headers.get("X-Twilio-Signature"), request.url.query)
    if outcome == "rejected":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid Twilio signature")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
