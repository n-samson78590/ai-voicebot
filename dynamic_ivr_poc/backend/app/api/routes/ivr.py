from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db
from backend.app.models.call_attempt import CallAttempt

router = APIRouter(tags=["ivr"])


@router.get("/api/ivr/response", response_class=PlainTextResponse)
async def ivr_response(
    custom_field: str | None = Query(default=None, alias="CustomField"),
    db: Session = Depends(get_db),
) -> str:
    if not custom_field:
        return "Hello, you have received an invitation."

    attempt = db.query(CallAttempt).filter(CallAttempt.ticket_id == custom_field).first()
    if attempt is None:
        return "Hello, you have received an invitation."

    return (
        f"Hello, this is an invitation for {attempt.doctor_name}. "
        f"You are invited to {attempt.event_name}, to be held at {attempt.location}, "
        f"on {attempt.event_date} at {attempt.event_time}. "
    )


@router.head("/api/ivr/response")
async def ivr_response_head() -> PlainTextResponse:
    return PlainTextResponse(content="", headers={"Content-Type": "text/plain"})
