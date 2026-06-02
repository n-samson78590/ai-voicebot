import requests

from config import settings


class ExotelConfigError(RuntimeError):
    pass


class ExotelService:
    def _validate_config(self, flow_type: str) -> str:
        missing = [
            name
            for name, value in {
                "EXOTEL_SID": settings.exotel_sid,
                "EXOTEL_API_KEY": settings.exotel_api_key,
                "EXOTEL_API_TOKEN": settings.exotel_api_token,
                "EXOTEL_CALLER_ID": settings.exotel_caller_id,
            }.items()
            if not value
        ]
        flow_url = settings.flow_url_for(flow_type)
        if not flow_url:
            missing.append(
                "VOICEBOT_FLOW_URL or VOICEBOT_APP_ID"
                if flow_type == "voicebot"
                else "IVR_FLOW_URL or IVR_APP_ID"
            )
        if missing:
            raise ExotelConfigError(f"Missing required Exotel configuration: {', '.join(missing)}")
        return flow_url

    def connect_to_flow(
        self,
        *,
        flow_type: str,
        phone_number: str,
        custom_field: str | None = None,
    ) -> dict:
        flow_url = self._validate_config(flow_type)

        data: list[tuple[str, str | int]] = [
            ("From", phone_number),
            ("CallerId", settings.exotel_caller_id),
            ("Url", flow_url),
            ("CallType", settings.call_type),
            ("TimeOut", settings.default_timeout),
            ("TimeLimit", settings.default_time_limit),
        ]
        if settings.status_callback_url:
            data.extend(
                [
                    ("StatusCallback", settings.status_callback_url),
                    ("StatusCallbackEvents[]", "answered"),
                    ("StatusCallbackEvents[]", "terminal"),
                ]
            )
        if custom_field:
            data.append(("CustomField", custom_field))

        response = requests.post(
            settings.exotel_base_url,
            auth=(settings.exotel_api_key, settings.exotel_api_token),
            data=data,
            timeout=30,
        )

        try:
            payload = response.json()
        except ValueError:
            payload = {"raw_text": response.text}

        if response.status_code >= 400:
            message = payload.get("RestException", {}).get("Message") if isinstance(payload, dict) else None
            raise RuntimeError(message or f"Exotel returned HTTP {response.status_code}")

        return payload


exotel_service = ExotelService()
