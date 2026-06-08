# Dynamic IVR POC (Exotel + Streamlit)

This POC lets you:
1. Enter invitation data and target phone number in Streamlit.
2. Trigger an Exotel IVR call.
3. Capture IVR logs from `/log` callback.
4. Persist call outcomes directly in SQLite (`poc.db`) using the `response` table.

## Setup

1. Go to this folder:
   - `cd dynamic_ivr_poc`
2. Install dependencies:
   - `pip install -r requirements.txt`
3. Optional: set environment variables for Exotel call trigger:
   - `EXOTEL_SID`
   - `EXOTEL_API_KEY`
   - `EXOTEL_API_TOKEN`
   - `EXOTEL_CALLER_ID`
   - `IVR_APP_ID` or `IVR_FLOW_URL`

If Exotel config is missing, ticket creation still works and records are stored in SQLite.

## Run

1. Start backend API:
   - `uvicorn backend.app:app --host 127.0.0.1 --port 5000 --reload`
2. Start Streamlit UI (new terminal):
   - `streamlit run streamlit_app.py`

## Endpoints

- `POST /api/tickets` : Create ticket in SQLite and attempt Exotel call
- `GET /api/ivr/response` : Dynamic TTS response (reads from SQLite via `CustomField=ticket_id`)
- `GET /log` : Exotel app.get/log callback receiver (updates `response` table)
- `POST /api/webhooks/exotel/status` : Exotel status webhook (updates `response` table)
- `GET /api/tickets/{ticket_id}` : Fetch ticket and latest response state
- `GET /api/logs` : Fetch response-table rows (supports `?ticket_id=` filter)

## Exotel Flow Notes

Your ExoML app should call:
- IVR prompt URL: `http://<your-public-host>/api/ivr/response?CustomField=<%CustomField%>`
- Log URL: `http://<your-public-host>/log?CallSid=<%CallSid%>&Digits=<%Digits%>&Status=<%Status%>&CustomField=<%CustomField%>&From=<%From%>`

Use ngrok or another tunnel so Exotel can reach your local backend.
