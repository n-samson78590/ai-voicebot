import re
from typing import Optional

from pydantic import BaseModel, Field, field_validator


PHONE_RE = re.compile(r"^\+?[1-9]\d{7,14}$")


class CallRequest(BaseModel):
    phone_number: str = Field(..., examples=["+919876543210"])
    custom_field: Optional[str] = Field(default=None, max_length=500)

    @field_validator("phone_number")
    @classmethod
    def validate_phone_number(cls, value: str) -> str:
        normalized = re.sub(r"[\s().\-]", "", value or "")
        if not PHONE_RE.match(normalized):
            raise ValueError("Enter a phone number in the correct format, for example +919876543210.")
        return normalized


class CallResponse(BaseModel):
    success: bool
    flow_type: str
    call_sid: Optional[str] = None
    status: Optional[str] = None
    message: str
    raw: Optional[dict] = None


class VoicebotStatus(BaseModel):
    running: bool
    pid: int | None = None
    readiness: str
