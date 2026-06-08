from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import PlainTextResponse, Response as FastAPIResponse
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db
from backend.app.services.response_service import persist_callback_to_response_table

router = APIRouter(tags=["webhooks"])


@router.get("/log", response_class=PlainTextResponse)
async def log_call(
    request: Request,
    call_sid: str | None = Query(default=None, alias="CallSid"),
    custom_field: str | None = Query(default=None, alias="CustomField"),
    status: str | None = Query(default=None, alias="Status"),
    digits: str | None = Query(default=None, alias="Digits"),
    digit: str | None = None,
    db: Session = Depends(get_db),
) -> PlainTextResponse:
    del request
    pressed_digit = digits or digit
    persist_callback_to_response_table(
        db=db,
        ticket_id=custom_field,
        call_sid=call_sid,
        digit=pressed_digit,
        status=status,
    )
    return PlainTextResponse(content="", headers={"Content-Type": "text/plain"})


@router.post("/log")
async def log_call_post(request: Request, db: Session = Depends(get_db)) -> FastAPIResponse:
    payload = dict(await request.form())
    print(f"RAW PASSTHRU PAYLOAD: {payload}")

    call_sid = payload.get("CallSid")
    custom_field = payload.get("CustomField")
    status = payload.get("Status")
    digit = payload.get("Digits")

    persist_callback_to_response_table(
        db=db,
        ticket_id=custom_field,
        call_sid=call_sid,
        digit=digit,
        status=status,
    )

    return FastAPIResponse(content="", media_type="application/xml")


@router.head("/log")
async def log_head() -> PlainTextResponse:
    return PlainTextResponse(content="", headers={"Content-Type": "text/plain"})


@router.post("/api/webhooks/exotel/status")
async def call_status(request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    payload = dict(await request.form())

    ticket_id = payload.get("CustomField")
    call_sid = payload.get("CallSid")
    digit = payload.get("Digits")
    status = payload.get("Status")

    persist_callback_to_response_table(
        db=db,
        ticket_id=ticket_id,
        call_sid=call_sid,
        digit=digit,
        status=status,
    )

    return {"status": "received", "ticket_id": ticket_id, "digit": digit, "call_status": status}
