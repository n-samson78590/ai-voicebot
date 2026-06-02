import socket
import subprocess
import time
from typing import Optional

import requests

from config import ROOT_DIR, settings


class VoicebotService:
    def __init__(self) -> None:
        self._process: Optional[subprocess.Popen] = None

    def _is_tracked_process_alive(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def _is_port_open(self) -> bool:
        try:
            with socket.create_connection(
                (settings.voicebot_host, settings.voicebot_port),
                timeout=1,
            ):
                return True
        except OSError:
            return False

    def is_running(self) -> bool:
        return self._is_tracked_process_alive() or self._is_port_open()

    def status(self) -> dict:
        readiness = "ready" if self.is_running() else "stopped"
        return {
            "running": readiness == "ready",
            "pid": self._process.pid if self._is_tracked_process_alive() else None,
            "readiness": readiness,
        }

    def start(self) -> dict:
        if not self.is_running():
            self._process = subprocess.Popen(
                settings.voicebot_start_command,
                cwd=ROOT_DIR,
                shell=True,
            )
        self.wait_until_ready()
        return self.status()

    def wait_until_ready(self) -> None:
        deadline = time.time() + settings.voicebot_ready_timeout
        last_error = None

        while time.time() < deadline:
            if settings.voicebot_health_url:
                try:
                    response = requests.get(settings.voicebot_health_url, timeout=2)
                    if response.ok:
                        return
                    last_error = f"health check returned HTTP {response.status_code}"
                except requests.RequestException as exc:
                    last_error = str(exc)
            elif self._is_port_open():
                return
            time.sleep(0.5)

        detail = last_error or f"port {settings.voicebot_port} did not open"
        raise TimeoutError(f"Voicebot service was not ready in time: {detail}")


voicebot_service = VoicebotService()
