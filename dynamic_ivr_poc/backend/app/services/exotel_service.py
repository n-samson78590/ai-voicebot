import json
from typing import Any

import requests

from backend.app.core.config import settings


def trigger_exotel_call(phone_number: str, ticket_id: str) -> tuple[bool, str | None, dict[str, Any] | None, str | None]:
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
