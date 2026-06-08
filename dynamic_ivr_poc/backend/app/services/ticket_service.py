import uuid
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.app.models.call_attempt import CallAttempt
from backend.app.models.response import CallResponse
from backend.app.schemas.ticket import TicketCreateRequest, TicketCreateResponse
from backend.app.services.exotel_service import trigger_exotel_call
from backend.app.services.response_service import persist_callback_to_response_table


def create_ticket(payload: TicketCreateRequest, db: Session) -> TicketCreateResponse:
    event_name = payload.event_name or payload.event
    event_date = payload.event_date or payload.date
    event_time = payload.event_time or payload.time

    if not event_name or not event_date or not event_time:
        raise HTTPException(
            status_code=422,
            detail="event_name/event_date/event_time are required (or event/date/time aliases).",
        )

    ticket_id = str(uuid.uuid4())[:8]

    attempt = CallAttempt(
        ticket_id=ticket_id,
        phone_number=payload.phone_number,
        doctor_name=payload.doctor_name,
        event_name=event_name,
        location=payload.location,
        event_date=event_date,
        event_time=event_time,
        initiated_by=payload.initiated_by,
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)

    call_initiated, call_sid, exotel_response, exotel_error = trigger_exotel_call(
        phone_number=payload.phone_number,
        ticket_id=ticket_id,
    )

    if call_initiated and call_sid:
        persist_callback_to_response_table(
            db=db,
            ticket_id=ticket_id,
            call_sid=call_sid,
            digit=None,
            status="queued",
        )

    status_text = "call_initiated" if call_initiated else "ticket_created"
    return TicketCreateResponse(
        status=status_text,
        ticket_id=ticket_id,
        call_initiated=call_initiated,
        call_sid=call_sid,
        exotel_error=exotel_error,
        exotel_response=exotel_response,
    )


def get_ticket_snapshot(ticket_id: str, db: Session) -> dict[str, Any]:
    attempt = db.query(CallAttempt).filter(CallAttempt.ticket_id == ticket_id).first()
    if attempt is None:
        raise HTTPException(status_code=404, detail="ticket not found")

    response_row = (
        db.query(CallResponse)
        .filter(CallResponse.ticket_id == ticket_id)
        .order_by(CallResponse.attempt_number.desc())
        .first()
    )

    return {
        "ticket_id": ticket_id,
        "doctor_name": attempt.doctor_name,
        "event_name": attempt.event_name,
        "location": attempt.location,
        "event_date": attempt.event_date,
        "event_time": attempt.event_time,
        "phone_number": attempt.phone_number,
        "initiated_by": attempt.initiated_by,
        "call_status": response_row.call_status.value if response_row and response_row.call_status else "pending",
        "ivr_response": response_row.ivr_response.value if response_row and response_row.ivr_response else "pending",
        "digit_pressed": response_row.digit_pressed if response_row else None,
        "call_sid": response_row.call_sid if response_row else None,
        "attempt_number": response_row.attempt_number if response_row else 0,
    }


def get_logs(ticket_id: str | None, db: Session) -> list[dict[str, Any]]:
    query = db.query(CallResponse)
    if ticket_id:
        query = query.filter(CallResponse.ticket_id == ticket_id)

    responses = query.order_by(CallResponse.created_at.desc()).all()
    return [
        {
            "ticket_id": row.ticket_id,
            "call_sid": row.call_sid,
            "call_status": row.call_status.value if row.call_status else None,
            "ivr_response": row.ivr_response.value if row.ivr_response else None,
            "digit_pressed": row.digit_pressed,
            "attempt_number": row.attempt_number,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in responses
    ]
