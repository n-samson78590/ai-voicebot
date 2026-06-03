# Exotel Call Flow Console

Streamlit dashboard for triggering Exotel Connect-to-Flow calls without opening the Exotel dashboard. 

Refer: Exotel Connect-to-Flow API: https://developer.exotel.com/api/#connect-to-flow

It supports:

- AI voicebot flow initiation
- IVR appointment flow initiation
- Exotel `Calls/connect` routing to applet flow URLs
- Voicebot service startup through the existing backend

## Architecture

```text
Streamlit UI
  -> Backend FastAPI
  -> Exotel Connect-to-Flow API
  -> Voicebot or IVR applet
```

The Streamlit page stays thin. For voicebot calls, the backend first starts the local `main.py --health-bot` process if needed, then connects to the voicebot app flow. For IVR calls, it directly connects to the IVR app flow.

## Voicebot POC Caveat

The Exotel Voicebot Applet still needs a public WebSocket URL configured in the Exotel dashboard. For a local setup, that usually means:

1. Start ngrok for the local voicebot WebSocket server.
2. Copy the public `wss://.../ws` URL. Update URL with stream rate parameter.
3. Manually update the Exotel Voicebot Applet configuration inside Exotel dashboard.
4. Save and publish the flow.
5. Use the Streamlit console to start the service and place calls.

This app **does not automate** the Exotel dashboard update step

## Setup

```powershell
cd .\call_to_flow\
pip install -r backend\requirements.txt
cp .env.example .env
```

Fill in `.env` inside the `call_to_flow` directory. The root project `.env` still needs the voicebot values such as `OPENAI_API_KEY` and `COMPANY_NAME`.

Required settings:

```text
EXOTEL_SID=
EXOTEL_API_KEY=
EXOTEL_API_TOKEN=
EXOTEL_CALLER_ID=
VOICEBOT_APP_ID=
IVR_APP_ID=
VOICEBOT_START_COMMAND=python main.py --health-bot 
```

You can also set `VOICEBOT_FLOW_URL` and `IVR_FLOW_URL` explicitly. If they are blank, the backend builds:

```text
http://my.exotel.com/{EXOTEL_SID}/exoml/start_voice/{APP_ID}
```

## Run

Start the backend first:

```powershell
cd .\ai-voicebot\call_to_flow\backend
uvicorn app:app --reload --port 8000
```

Then start the frontend rendered with Streamlit:

```powershell
cd .\call_to_flow\
streamlit run streamlit_app.py
```

Optional: if the backend is not on `http://localhost:8000`, set `CALL_TO_FLOW_API_BASE` before launching Streamlit.

## API

### Start voicebot service

```http
POST /api/voicebot/start
```

Starts `VOICEBOT_START_COMMAND` from the repository root and waits until `VOICEBOT_HOST:VOICEBOT_PORT` accepts connections.

### Exotel status callback

```http
POST /api/webhooks/exotel/status
```

This currently acknowledges callbacks and gives you the extension point for CRM sync, call timelines, and analytics persistence.

## Notes

- The voicebot applet URL still has to be changed manually when ngrok changes.
- If the voicebot is already running outside this backend, the backend can still detect readiness through the configured port or health URL.
