"""Public, token-gated billing PDF delivery."""
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.billing_pdf_service import BillingPdfService

router = APIRouter(prefix="/api/public/billing-media", tags=["billing-media"])


def _service(db: Session) -> BillingPdfService:
    return BillingPdfService(db)


@router.api_route("/{token}", methods=["GET", "HEAD"])
def download_billing_media(token: str, db: Session = Depends(get_db)) -> Response:
    resolved = _service(db).resolve(token)
    if resolved is None:
        raise HTTPException(status_code=404, detail="Media not found")
    path, filename = resolved
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=filename,
        content_disposition_type="inline",
        headers={"Cache-Control": "no-store"},
    )
