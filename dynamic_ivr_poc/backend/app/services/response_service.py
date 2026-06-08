from sqlalchemy.orm import Session

from backend.app.models.call_attempt import CallAttempt
from backend.app.models.enums import CallStatusType, ResponseType
from backend.app.models.response import CallResponse


def map_ivr_response(digit: str | None) -> ResponseType | None:
    if digit == "1":
        return ResponseType.accept
    if digit == "2":
        return ResponseType.reject
    return None


def normalize_digit(digit: str | None) -> str | None:
    if digit is None:
        return None

    normalized = digit.strip().strip('"').strip("'")
    if normalized in {"1", "2"}:
        return normalized
    return None


def map_call_status(status: str | None) -> CallStatusType | None:
    if not status:
        return None
    normalized = status.strip().lower()
    if normalized in {"completed", "answered"}:
        return CallStatusType.success
    if normalized in {"failed", "busy", "no-answer", "canceled", "cancelled"}:
        return CallStatusType.failure
    return None


def find_or_create_response_row(
    db: Session,
    attempt: CallAttempt,
    call_sid: str | None,
) -> CallResponse:
    response_row = None
    if call_sid:
        response_row = db.query(CallResponse).filter(CallResponse.call_sid == call_sid).first()

    if response_row is None:
        response_row = (
            db.query(CallResponse)
            .filter(CallResponse.ticket_id == attempt.ticket_id)
            .order_by(CallResponse.attempt_number.desc())
            .first()
        )

    if response_row is None or (call_sid and response_row.call_sid and response_row.call_sid != call_sid):
        prior_count = db.query(CallResponse).filter(CallResponse.ticket_id == attempt.ticket_id).count()
        response_row = CallResponse(
            ticket_id=attempt.ticket_id,
            invitation_id=attempt.id,
            call_sid=call_sid,
            attempt_number=prior_count + 1,
        )
        db.add(response_row)

    return response_row


def persist_callback_to_response_table(
    db: Session,
    ticket_id: str | None,
    call_sid: str | None,
    digit: str | None,
    status: str | None,
) -> None:
    if not ticket_id:
        return

    attempt = db.query(CallAttempt).filter(CallAttempt.ticket_id == ticket_id).first()
    if attempt is None:
        return

    response_row = find_or_create_response_row(db, attempt, call_sid)
    if call_sid:
        response_row.call_sid = call_sid

    normalized_digit = normalize_digit(digit)
    if normalized_digit:
        response_row.digit_pressed = normalized_digit
        response_row.ivr_response = map_ivr_response(normalized_digit)
        response_row.call_status = CallStatusType.success
    else:
        mapped_status = map_call_status(status)
        if mapped_status is not None:
            response_row.call_status = mapped_status
        elif response_row.call_status is None:
            response_row.call_status = CallStatusType.failure

    db.commit()
