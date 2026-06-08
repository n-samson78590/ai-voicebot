import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_DIR = Path(__file__).resolve().parents[3]
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
