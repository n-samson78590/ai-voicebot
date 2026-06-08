from datetime import date

import requests
import streamlit as st


st.set_page_config(page_title="Dynamic IVR POC", page_icon="Phone", layout="wide")
st.title("Dynamic IVR POC - Exotel")
st.caption("Create invitation calls and inspect SQLite-backed IVR responses from the response table.")


def api_get(base_url: str, path: str, params: dict | None = None) -> dict:
	response = requests.get(f"{base_url.rstrip('/')}{path}", params=params, timeout=20)
	response.raise_for_status()
	return response.json()


def api_post(base_url: str, path: str, payload: dict) -> dict:
	response = requests.post(f"{base_url.rstrip('/')}{path}", json=payload, timeout=30)
	response.raise_for_status()
	return response.json()


default_base_url = "http://127.0.0.1:5000"
api_base = st.sidebar.text_input("Backend Base URL", value=default_base_url)

if "last_call_sid" not in st.session_state:
	st.session_state["last_call_sid"] = ""
if "last_ticket_id" not in st.session_state:
	st.session_state["last_ticket_id"] = ""
if "search_ticket_id" not in st.session_state:
	st.session_state["search_ticket_id"] = ""

left_col, right_col = st.columns([1.4, 1], gap="large")

with left_col:
	st.subheader("1) Trigger Dynamic IVR Call")
	with st.form("trigger_call_form"):
		phone_number = st.text_input("Phone Number", placeholder="+919876543210")
		doctor_name = st.text_input("Doctor Name", placeholder="Dr. Sharma")
		event_name = st.text_input("Event", placeholder="Annual Medical Conference")
		location = st.text_input("Location", placeholder="Mumbai")
		initiated_by = st.text_input("Initiated By (optional)", placeholder="ops_user")

		date_col, time_col = st.columns(2)
		with date_col:
			invitation_date = st.date_input("Date", value=date.today())
		with time_col:
			invitation_time = st.text_input("Time", value="10:00 AM")

		submit = st.form_submit_button("Trigger Call")

	if submit:
		payload = {
			"phone_number": phone_number,
			"doctor_name": doctor_name,
			"event_name": event_name,
			"location": location,
			"event_date": invitation_date.strftime("%Y-%m-%d"),
			"event_time": invitation_time,
			"initiated_by": initiated_by or None,
		}
		try:
			result = api_post(api_base, "/api/tickets", payload)
			call_sid = result.get("call_sid") or ""
			ticket_id = result.get("ticket_id") or ""
			st.session_state["last_call_sid"] = call_sid
			st.session_state["last_ticket_id"] = ticket_id
			st.session_state["search_ticket_id"] = ticket_id

			st.success("Ticket saved to SQLite and call trigger attempted.")
			if ticket_id:
				st.info(f"Ticket ID: {ticket_id}")
			if call_sid:
				st.info(f"Call SID: {call_sid}")
			if result.get("exotel_error"):
				st.warning(f"Exotel call was not initiated: {result.get('exotel_error')}")

			with st.expander("API Response"):
				st.json(result)
		except requests.HTTPError as exc:
			detail = ""
			try:
				detail = exc.response.text
			except Exception:
				detail = str(exc)
			st.error(f"Call trigger failed: {detail}")
		except Exception as exc:
			st.error(f"Call trigger failed: {exc}")

with right_col:
	st.subheader("2) Fetch SQLite Logs")
	st.text_input(
		"Search by Ticket ID",
		key="search_ticket_id",
		placeholder="Enter ticket id",
	)

	if st.session_state.get("last_ticket_id"):
		st.info(f"Current Ticket ID: {st.session_state['last_ticket_id']}")

	search = st.button("Search Ticket", use_container_width=True)
	if search:
		ticket_id = st.session_state.get("search_ticket_id", "").strip()
		if not ticket_id:
			st.warning("Enter a ticket id first.")
		else:
			st.session_state["last_ticket_id"] = ticket_id
			try:
				ticket = api_get(api_base, f"/api/tickets/{ticket_id}")
				st.write("Ticket Snapshot")
				st.json(ticket)
			except requests.HTTPError as exc:
				status_code = exc.response.status_code if exc.response is not None else "unknown"
				st.error(f"Could not fetch ticket (HTTP {status_code}).")
			except Exception as exc:
				st.error(f"Could not fetch ticket: {exc}")

			try:
				entries = api_get(api_base, "/api/logs", params={"ticket_id": ticket_id})
				st.success(f"Loaded {len(entries)} response rows")
				if entries:
					st.dataframe(entries, use_container_width=True)
				else:
					st.info("No response rows found yet.")
			except requests.HTTPError as exc:
				status_code = exc.response.status_code if exc.response is not None else "unknown"
				st.error(f"Could not fetch logs (HTTP {status_code}).")
			except Exception as exc:
				st.error(f"Could not fetch logs: {exc}")
