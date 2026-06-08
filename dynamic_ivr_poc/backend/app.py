import enum
import json
import os
import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Generator

import requests
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse, Response as FastAPIResponse
from pydantic import BaseModel, field_validator
from sqlalchemy import Column, DateTime, Enum as SAEnum, Integer, String, create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker


PHONE_RE = re.compile(r"^\+?[1-9]\d{7,14}$")

PROJECT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    exotel_sid: str = os.getenv("EXOTEL_SID", "").strip()
    exotel_api_key: str = os.getenv("EXOTEL_API_KEY", "").strip()
    exotel_api_token: str = os.getenv("EXOTEL_API_TOKEN", "").strip()
    exotel_caller_id: str = os.getenv("EXOTEL_CALLER_ID", "").strip()
    exotel_region: str = os.getenv("EXOTEL_REGION", "singapore").strip().lower()
    ivr_flow_url: str = os.getenv("IVR_FLOW_URL", "").strip()
    ivr_app_id: str = os.getenv("IVR_APP_ID", "").strip()
    exotel_call_type: str = os.getenv("EXOTEL_CALL_TYPE", "trans").strip()
    exotel_timeout_seconds: int = int(os.getenv("EXOTEL_TIMEOUT_SECONDS", "30") or "30")
    exotel_time_limit_seconds: int = int(os.getenv("EXOTEL_TIME_LIMIT_SECONDS", "1800") or "1800")

    @property
    def exotel_base_url(self) -> str:
        host = "api.in.exotel.com" if self.exotel_region == "mumbai" else "api.exotel.com"
        return f"https://{host}/v1/Accounts/{self.exotel_sid}/Calls/connect"

    @property
    def resolved_ivr_url(self) -> str:
        if self.ivr_flow_url:
            if self.ivr_flow_url.startswith(("http://", "https://")):
                return self.ivr_flow_url
            if self.ivr_flow_url.isdigit() and self.exotel_sid:
                return f"http://my.exotel.com/{self.exotel_sid}/exoml/start_voice/{self.ivr_flow_url}"
            return ""
        if self.ivr_app_id and self.exotel_sid:
            return f"http://my.exotel.com/{self.exotel_sid}/exoml/start_voice/{self.ivr_app_id}"
        return ""

    @property
    def exotel_ready(self) -> bool:
        return bool(
            self.exotel_sid
            and self.exotel_api_key
            and self.exotel_api_token
            and self.exotel_caller_id
            and self.resolved_ivr_url
        )

    def missing_exotel_fields(self) -> list[str]:
        missing: list[str] = []
        if not self.exotel_sid:
            missing.append("EXOTEL_SID")
        if not self.exotel_api_key:
            missing.append("EXOTEL_API_KEY")
        if not self.exotel_api_token:
            missing.append("EXOTEL_API_TOKEN")
        if not self.exotel_caller_id:
            missing.append("EXOTEL_CALLER_ID")
        if not self.resolved_ivr_url:
            missing.append("IVR_FLOW_URL or IVR_APP_ID")
        return missing


settings = Settings()
app = FastAPI(title="Dynamic IVR POC API")


DB_PATH = Path(__file__).resolve().parent.parent / "poc.db"
engine = create_engine(f"sqlite:///{DB_PATH.as_posix()}", connect_args={"check_same_thread": False})
Base = declarative_base()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class CallStatusType(str, enum.Enum):
    success = "success"
    failure = "failure"


class ResponseType(str, enum.Enum):
    accept = "Invitation Accepted"
    reject = "Invitation Rejected"


class CallAttempt(Base):
    __tablename__ = "call_attempt"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticket_id = Column(String, unique=True, nullable=False)
    phone_number = Column(String, nullable=False)
    doctor_name = Column(String, nullable=False)
    event_name = Column(String, nullable=False)
    location = Column(String, nullable=False)
    event_date = Column(String, nullable=False)
    event_time = Column(String, nullable=False)
    initiated_by = Column(String, nullable=True)
    created_at = Column(String, default=lambda: datetime.utcnow().isoformat())


class Response(Base):
    __tablename__ = "response"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticket_id = Column(String, nullable=False)
    invitation_id = Column(Integer, nullable=False)
    call_sid = Column(String, unique=True, nullable=True)
    attempt_number = Column(Integer, nullable=True)
    call_status = Column(SAEnum(CallStatusType), nullable=True)
    digit_pressed = Column(String, nullable=True)
    ivr_response = Column(SAEnum(ResponseType), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


Base.metadata.create_all(bind=engine)


class TicketCreateRequest(BaseModel):
    phone_number: str
    doctor_name: str
    event_name: str | None = None
    event: str | None = None
    location: str
    event_date: str | None = None
    date: str | None = None
    event_time: str | None = None
    time: str | None = None
    initiated_by: str | None = None

    @field_validator("phone_number")
    @classmethod
    def validate_phone_number(cls, value: str) -> str:
        normalized = re.sub(r"[\s().\-]", "", value or "")
        if not PHONE_RE.match(normalized):
            raise ValueError("Enter a phone number like +919876543210")
        return normalized


class TicketCreateResponse(BaseModel):
    status: str
    ticket_id: str
    call_initiated: bool
    call_sid: str | None = None
    exotel_error: str | None = None
    exotel_response: dict[str, Any] | None = None


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _map_ivr_response(digit: str | None) -> ResponseType | None:
    if digit == "1":
        return ResponseType.accept
    if digit == "2":
        return ResponseType.reject
    return None


def _normalize_digit(digit: str | None) -> str | None:
    if digit is None:
        return None

    normalized = digit.strip().strip('"').strip("'")
    if normalized in {"1", "2"}:
        return normalized
    return None


def _map_call_status(status: str | None) -> CallStatusType | None:
    if not status:
        return None
    normalized = status.strip().lower()
    if normalized in {"completed", "answered"}:
        return CallStatusType.success
    if normalized in {"failed", "busy", "no-answer", "canceled", "cancelled"}:
        return CallStatusType.failure
    return None


def _find_or_create_response_row(
    db: Session,
    attempt: CallAttempt,
    call_sid: str | None,
) -> Response:
    response_row = None
    if call_sid:
        response_row = db.query(Response).filter(Response.call_sid == call_sid).first()

    if response_row is None:
        response_row = (
            db.query(Response)
            .filter(Response.ticket_id == attempt.ticket_id)
            .order_by(Response.attempt_number.desc())
            .first()
        )

    if response_row is None or (call_sid and response_row.call_sid and response_row.call_sid != call_sid):
        prior_count = db.query(Response).filter(Response.ticket_id == attempt.ticket_id).count()
        response_row = Response(
            ticket_id=attempt.ticket_id,
            invitation_id=attempt.id,
            call_sid=call_sid,
            attempt_number=prior_count + 1,
        )
        db.add(response_row)

    return response_row


def _persist_callback_to_response_table(
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

    response_row = _find_or_create_response_row(db, attempt, call_sid)
    if call_sid:
        response_row.call_sid = call_sid

    normalized_digit = _normalize_digit(digit)
    if normalized_digit:
        response_row.digit_pressed = normalized_digit
        response_row.ivr_response = _map_ivr_response(normalized_digit)
        # If user entered IVR digit, they picked up the call.
        response_row.call_status = CallStatusType.success
    else:
        mapped_status = _map_call_status(status)
        if mapped_status is not None:
            response_row.call_status = mapped_status
        elif response_row.call_status is None:
            # Default to failure for callbacks with no user response and no known success state.
            response_row.call_status = CallStatusType.failure

    db.commit()


def _trigger_exotel_call(phone_number: str, ticket_id: str) -> tuple[bool, str | None, dict[str, Any] | None, str | None]:
    if not settings.exotel_ready:
        missing_fields = settings.missing_exotel_fields()
        return False, None, None, f"Exotel configuration is incomplete. Missing: {', '.join(missing_fields)}"

    payload = {
        "From": phone_number,
        "CallerId": settings.exotel_caller_id,
        "CustomField": ticket_id,
        "Url": settings.resolved_ivr_url,
        "CallType": settings.exotel_call_type,
        "Timeout": settings.exotel_timeout_seconds,
        "TimeLimit": settings.exotel_time_limit_seconds,
    }

    try:
        response = requests.post(
            settings.exotel_base_url,
            auth=(settings.exotel_api_key, settings.exotel_api_token),
            data=payload,
            timeout=30,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        error_text = str(exc)
        if getattr(exc, "response", None) is not None:
            error_text = f"{error_text}. Exotel response: {exc.response.text}"
        return False, None, None, error_text

    response_text = response.text.strip() if response.text else ""
    exotel_payload: dict[str, Any]
    call_sid: str | None = None

    if response_text:
        try:
            parsed_payload = response.json()
            if isinstance(parsed_payload, dict):
                exotel_payload = parsed_payload
            else:
                exotel_payload = {"raw": parsed_payload}
        except (requests.exceptions.JSONDecodeError, json.JSONDecodeError, ValueError):
            exotel_payload = {"raw_text": response_text}
    else:
        exotel_payload = {"raw_text": ""}

    call_data = exotel_payload.get("Call") if isinstance(exotel_payload, dict) else None
    if not isinstance(call_data, dict):
        call_data = exotel_payload.get("call") if isinstance(exotel_payload, dict) else None
    if isinstance(call_data, dict):
        call_sid = call_data.get("Sid") or call_data.get("sid")

    return True, call_sid, exotel_payload, None


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/tickets", response_model=TicketCreateResponse)
async def create_ticket(payload: TicketCreateRequest, db: Session = Depends(get_db)) -> TicketCreateResponse:
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

    call_initiated, call_sid, exotel_response, exotel_error = _trigger_exotel_call(
        phone_number=payload.phone_number,
        ticket_id=ticket_id,
    )

    if call_initiated and call_sid:
        _persist_callback_to_response_table(
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


@app.get("/api/ivr/response", response_class=PlainTextResponse)
async def ivr_response(CustomField: str | None = None, db: Session = Depends(get_db)) -> str:
    if not CustomField:
        return "Hello, you have received an invitation. Press 1 to confirm or 2 to decline."

    attempt = db.query(CallAttempt).filter(CallAttempt.ticket_id == CustomField).first()
    if attempt is None:
        return "Hello, you have received an invitation. Press 1 to confirm or 2 to decline."

    return (
        f"Hello, this is an invitation for {attempt.doctor_name}. "
        f"You are invited to {attempt.event_name}, to be held at {attempt.location}, "
        f"on {attempt.event_date} at {attempt.event_time}. "
    )


@app.head("/api/ivr/response")
async def ivr_response_head() -> PlainTextResponse:
    return PlainTextResponse(content="", headers={"Content-Type": "text/plain"})


@app.get("/log", response_class=PlainTextResponse)
async def log_call(
    request: Request,
    db: Session = Depends(get_db),
) -> PlainTextResponse:
    params = dict(request.query_params)

    print(f"RAW PASSTHRU PARAMS: {params}")

    call_sid = params.get("CallSid")
    custom_field = params.get("CustomField")

    status = (
        params.get("Status")
        or params.get("DialCallStatus")
    )

    digit = (
        params.get("digits")
        or params.get("Digits")
        or params.get("digit")
    )

    print(
        f"Parsed values -> "
        f"CallSid={call_sid}, "
        f"CustomField={custom_field}, "
        f"Status={status}, "
        f"Digit={digit}"
    )

    _persist_callback_to_response_table(
        db=db,
        ticket_id=custom_field,
        call_sid=call_sid,
        digit=digit,
        status=status,
    )

    return PlainTextResponse(
        content="",
        headers={"Content-Type": "text/plain"},
    )

@app.post("/log")
async def log_call_post(request: Request, db: Session = Depends(get_db)) -> FastAPIResponse:
    payload = dict(await request.form())
    print(f"RAW PASSTHRU PAYLOAD: {payload}")

    call_sid = payload.get("CallSid")
    custom_field = payload.get("CustomField")
    status = payload.get("Status")
    digit = payload.get("Digits") or payload.get("digits")

    _persist_callback_to_response_table(
        db=db,
        ticket_id=custom_field,
        call_sid=call_sid,
        digit=digit,
        status=status,
    )

    # Return empty ExoML-compatible XML so Exotel continues flow.
    return FastAPIResponse(content="", media_type="application/xml")


@app.head("/log")
async def log_head() -> PlainTextResponse:
    return PlainTextResponse(content="", headers={"Content-Type": "text/plain"})


@app.post("/api/webhooks/exotel/status")
async def call_status(request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    payload = dict(await request.form())

    ticket_id = payload.get("CustomField")
    call_sid = payload.get("CallSid")
    digit = payload.get("Digits") or payload.get("digits")
    status = payload.get("Status")

    _persist_callback_to_response_table(
        db=db,
        ticket_id=ticket_id,
        call_sid=call_sid,
        digit=digit,
        status=status,
    )

    return {"status": "received", "ticket_id": ticket_id, "digit": digit, "call_status": status}


@app.get("/api/tickets/{ticket_id}")
async def get_ticket(ticket_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    attempt = db.query(CallAttempt).filter(CallAttempt.ticket_id == ticket_id).first()
    if attempt is None:
        raise HTTPException(status_code=404, detail="ticket not found")

    response_row = (
        db.query(Response)
        .filter(Response.ticket_id == ticket_id)
        .order_by(Response.attempt_number.desc())
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


@app.get("/api/logs")
async def get_logs(ticket_id: str | None = None, db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    query = db.query(Response)
    if ticket_id:
        query = query.filter(Response.ticket_id == ticket_id)

    responses = query.order_by(Response.created_at.desc()).all()
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