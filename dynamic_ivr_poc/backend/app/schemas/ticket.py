import re
from typing import Any

from pydantic import BaseModel, field_validator

from backend.app.core.constants import PHONE_RE


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
