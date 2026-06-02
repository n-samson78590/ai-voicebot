import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


APP_DIR = Path(__file__).resolve().parent
CALL_TO_FLOW_DIR = APP_DIR.parent
ROOT_DIR = CALL_TO_FLOW_DIR.parent

load_dotenv(CALL_TO_FLOW_DIR / ".env")
load_dotenv(ROOT_DIR / ".env")


def _getenv(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


@dataclass(frozen=True)
class Settings:
    exotel_sid: str = _getenv("EXOTEL_SID")
    exotel_api_key: str = _getenv("EXOTEL_API_KEY")
    exotel_api_token: str = _getenv("EXOTEL_API_TOKEN")
    exotel_caller_id: str = _getenv("EXOTEL_CALLER_ID")
    exotel_region: str = _getenv("EXOTEL_REGION").lower()

    voicebot_app_id: str = _getenv("VOICEBOT_APP_ID")
    ivr_app_id: str = _getenv("IVR_APP_ID")
    voicebot_flow_url: str = _getenv("VOICEBOT_FLOW_URL")
    ivr_flow_url: str = _getenv("IVR_FLOW_URL")

    status_callback_url: str = _getenv("EXOTEL_STATUS_CALLBACK_URL")
    call_type: str = _getenv("EXOTEL_CALL_TYPE", "trans")
    default_timeout: int = int(_getenv("EXOTEL_TIMEOUT_SECONDS", "30") or "30")
    default_time_limit: int = int(_getenv("EXOTEL_TIME_LIMIT_SECONDS", "1800") or "1800")

    voicebot_start_command: str = _getenv(
        "VOICEBOT_START_COMMAND",
        f'"{sys.executable}" main.py --health-bot',
    )
    voicebot_host: str = _getenv("VOICEBOT_HOST", "127.0.0.1")
    voicebot_port: int = int(_getenv("VOICEBOT_PORT", _getenv("SERVER_PORT", "5000")) or "5000")
    voicebot_health_url: str = _getenv("VOICEBOT_HEALTH_URL")
    voicebot_ready_timeout: float = float(_getenv("VOICEBOT_READY_TIMEOUT_SECONDS", "20") or "20")

    cors_origins: str = _getenv("CORS_ORIGINS", "*")

    @property
    def exotel_base_url(self) -> str:
        host = "api.in.exotel.com" if self.exotel_region == "mumbai" else "api.exotel.com"
        return f"https://{host}/v1/Accounts/{self.exotel_sid}/Calls/connect"

    def flow_url_for(self, flow_type: str) -> str:
        configured_url = self.voicebot_flow_url if flow_type == "voicebot" else self.ivr_flow_url
        app_id = self.voicebot_app_id if flow_type == "voicebot" else self.ivr_app_id

        if configured_url:
            return configured_url
        if self.exotel_sid and app_id:
            return f"http://my.exotel.com/{self.exotel_sid}/exoml/start_voice/{app_id}"
        return ""


settings = Settings()
