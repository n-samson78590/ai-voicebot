from __future__ import annotations

import os
import re
from typing import Any

import requests
import streamlit as st


DEFAULT_API_BASE = os.getenv("CALL_TO_FLOW_API_BASE", "http://localhost:5000").rstrip("/")
INDIA_PHONE_RE = re.compile(r"^\+91\d{10}$")


def api_base() -> str:
    return DEFAULT_API_BASE


def request_json(path: str, *, method: str = "GET", payload: dict[str, Any] | None = None) -> dict[str, Any]:
    response = requests.request(
        method,
        f"{api_base()}{path}",
        json=payload,
        timeout=30,
    )
    try:
        data = response.json()
    except ValueError:
        data = {"detail": response.text}

    if not response.ok:
        detail = data.get("detail") if isinstance(data, dict) else None
        raise RuntimeError(detail or f"Request failed with HTTP {response.status_code}")
    return data if isinstance(data, dict) else {"data": data}


def add_log(message: str, level: str = "info") -> None:
    st.session_state.activity_log.insert(0, {"message": message, "level": level})


def phone_value() -> str:
    return st.session_state.get("phone_number", "").strip()


def normalize_phone_value(raw_value: str) -> str:
    digits = re.sub(r"\D", "", raw_value or "")
    if digits.startswith("91") and len(digits) > 10:
        digits = digits[2:]
    if len(digits) > 10:
        digits = digits[-10:]
    if len(digits) == 10:
        return f"+91{digits}"
    if raw_value.strip().startswith("+91"):
        return raw_value.strip()
    return f"+91{digits}" if digits else "+91"


def is_valid_phone_value(value: str) -> bool:
    return bool(INDIA_PHONE_RE.match(value))


def call_payload() -> dict[str, Any]:
    return {"phone_number": phone_value()}


def render_status() -> None:
    st.subheader("Call Control")
    st.caption("Enter a phone number, then choose Voicebot or IVR.")


def render_status_cards() -> None:
    backend_online = False
    backend_label = "Offline"
    voicebot_label = "Unknown"

    try:
        request_json("/api/health")
        backend_online = True
        backend_label = "Online"
    except Exception:
        backend_label = "Offline"

    try:
        status = request_json("/api/voicebot/status")
        readiness = status.get("readiness", "unknown")
        pid = status.get("pid")
        voicebot_label = f"{readiness.title()}" + (f" (PID {pid})" if pid else "")
    except Exception as exc:
        voicebot_label = f"Unavailable: {exc}"

    left, right = st.columns(2)
    with left:
        st.metric("Backend", backend_label if backend_online else "Offline")
    with right:
        st.metric("Voicebot", voicebot_label)


def render_call_form() -> None:
    st.text_input(
        "Phone number",
        key="phone_number",
        value=st.session_state.get("phone_number", "+91"),
        placeholder="+919876543210",
        help="Enter a 10-digit Indian mobile number.",
        on_change=lambda: st.session_state.__setitem__(
            "phone_number", normalize_phone_value(st.session_state.get("phone_number", "+91"))
        ),
    )


def start_call(flow_type: str) -> None:
    try:
        payload = request_json(f"/api/calls/{flow_type}", method="POST", payload=call_payload())
        call_sid = payload.get("call_sid")
        message = payload.get("message", f"{flow_type.title()} call initiated")
        if call_sid:
            message = f"{message} Call SID: {call_sid}"
        add_log(message, "success")
    except Exception as exc:
        add_log(str(exc), "error")


def render_activity() -> None:
    st.subheader("Activity")
    if st.button("Clear activity"):
        st.session_state.activity_log = []
        st.rerun()

    if not st.session_state.activity_log:
        st.caption("No actions yet.")
        return

    for item in st.session_state.activity_log:
        prefix = {"success": "[OK]", "error": "[ERR]"}.get(item["level"], "[INFO]")
        st.write(f"{prefix} {item['message']}")


def inject_styles() -> None:
        st.markdown(
                """
                <style>
                    div[data-testid="stMetric"] {
                        padding: 0.35rem 0.5rem;
                    }

                    div[data-testid="stMetricLabel"] {
                        font-size: 0.82rem !important;
                        line-height: 1.15;
                    }

                    div[data-testid="stMetricValue"] {
                        font-size: 0.95rem !important;
                        line-height: 1.2;
                    }
                </style>
                """,
                unsafe_allow_html=True,
        )


def main() -> None:
    st.set_page_config(page_title="Exotel Call Flow Console", layout="wide")

    inject_styles()

    if "activity_log" not in st.session_state:
        st.session_state.activity_log = []

    st.title("Exotel Call Flow Console")
    st.write("Enter a phone number and choose Voicebot or IVR.")

    render_status()
    render_status_cards()
    render_call_form()

    action_left, action_right = st.columns(2)
    with action_left:
        if st.button("Start Voicebot Call", use_container_width=True):
            if not is_valid_phone_value(phone_value()):
                add_log("Enter a valid Indian phone number in the form +91xxxxxxxxxx.", "error")
            else:
                start_call("voicebot")
    with action_right:
        if st.button("Start IVR Call", use_container_width=True):
            if not is_valid_phone_value(phone_value()):
                add_log("Enter a valid Indian phone number in the form +91xxxxxxxxxx.", "error")
            else:
                start_call("ivr")

    st.divider()
    render_activity()


if __name__ == "__main__":
    main()