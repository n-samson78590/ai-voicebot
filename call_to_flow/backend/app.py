from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse


from config import settings
from models import CallRequest, CallResponse, VoicebotStatus
from services.exotel_service import ExotelConfigError, exotel_service
from services.voicebot_service import voicebot_service
import logging

logging.basicConfig(
    filename="ivr.log",
    level=logging.INFO,
    format="%(asctime)s | %(message)s"
)

app = FastAPI(
    title="Exotel Call Flow Console",
    description="Initiate AI voicebot and IVR appointment flows through Exotel Connect-to-Flow.",
    version="0.1.0",
)

origins = ["*"] if settings.cors_origins == "*" else [
    origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/voicebot/status", response_model=VoicebotStatus)
def voicebot_status() -> dict:
    return voicebot_service.status()


@app.post("/api/voicebot/start", response_model=VoicebotStatus)
def start_voicebot() -> dict:
    try:
        return voicebot_service.start()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _format_call_response(flow_type: str, payload: dict) -> CallResponse:
    call = payload.get("Call", {}) if isinstance(payload, dict) else {}
    return CallResponse(
        success=True,
        flow_type=flow_type,
        call_sid=call.get("Sid"),
        status=call.get("Status"),
        message=f"{flow_type.title()} call initiated successfully.",
        raw=payload,
    )


@app.post("/api/calls/voicebot", response_model=CallResponse)
def start_voicebot_call(call_request: CallRequest) -> CallResponse:
    try:
        voicebot_service.start()
        payload = exotel_service.connect_to_flow(
            flow_type="voicebot",
            phone_number=call_request.phone_number,
            custom_field=call_request.custom_field,
        )
        return _format_call_response("voicebot", payload)
    except ExotelConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/calls/ivr", response_model=CallResponse)
def start_ivr_call(call_request: CallRequest) -> CallResponse:
    try:
        payload = exotel_service.connect_to_flow(
            flow_type="ivr",
            phone_number=call_request.phone_number,
            custom_field=call_request.custom_field,
        )
        return _format_call_response("ivr", payload)
    except ExotelConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    

@app.get("/api/ivr/log")
async def log_digit(request: Request):

    digit = request.query_params.get("digit")
    call_sid = request.query_params.get("CallSid")

    logging.info(
        f"CallSid={call_sid} | Digit={digit}"
    )

    return PlainTextResponse("OK")


@app.post("/api/webhooks/exotel/status")
async def exotel_status_webhook(request: Request) -> dict:
    form = await request.form()
    # Placeholder for CRM sync, call timeline persistence, and analytics.
    return {"received": True, "fields": dict(form)}

# @app.get("/debug/routes")
# async def debug_routes():
#     return [
#         {
#             "path": route.path,
#             "name": route.name
#         }
#         for route in app.routes
#     ]