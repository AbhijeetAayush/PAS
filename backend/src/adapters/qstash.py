from __future__ import annotations

import base64
import hashlib
import hmac
import httpx
import jwt

from domain.models import AppError

# The token from the Upstash console is regional. The EU host returns 404 for a US token.
_DEFAULT_BASE = "https://qstash-us-east-1.upstash.io"
# Page reads call Vertex. Three at a time, and no more than 10 starts a minute,
# stays under the quota that returned 429 when two pages ran with no cap.
_READ_KEY = "voter-roll"
_READ_CONTROL = "parallelism=3, rate=10, period=1m"
# Finding PDFs and queueing pages does not call Vertex, so it has its own key
# and does not hold a read slot.
_PREPARE_KEY = "voter-roll-prepare"
_PREPARE_CONTROL = "parallelism=4"


def lane_for(path: str) -> str:
    return "read" if path.endswith("/page") else "prepare"


def flow_control(lane: str) -> tuple[str, str]:
    if lane == "read":
        return _READ_KEY, _READ_CONTROL
    if lane == "prepare":
        return _PREPARE_KEY, _PREPARE_CONTROL
    raise AppError("Unknown QStash lane", 500)


class QStash:
    def __init__(self, token: str, current_key: str, next_key: str, base_url: str = _DEFAULT_BASE) -> None:
        self.token = token
        self.base_url = (base_url or _DEFAULT_BASE).rstrip("/")
        self.keys = [key for key in (current_key, next_key) if key]

    def publish(self, url: str, payload: dict, lane: str = "prepare") -> None:
        if not url.startswith("https://"):
            raise AppError("QStash destination must be an https URL", 500)
        key, control = flow_control(lane)
        # The destination stays in the path with its scheme visible. Encoding the
        # scheme makes QStash reject the URL.
        response = httpx.post(
            f"{self.base_url}/v2/publish/{url}",
            json=payload,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "Upstash-Retries": "5",
                "Upstash-Retry-Delay": "pow(2, retried) * 10000",
                "Upstash-Flow-Control-Key": key,
                "Upstash-Flow-Control-Value": control,
            },
            timeout=30,
        )
        if response.status_code >= 400:
            detail = _public_error(response.status_code, response.text)
            raise AppError(f"QStash publish failed: {detail}", 502)

    def verify(self, signature: str, body: bytes, url: str) -> None:
        if not signature or not self.keys:
            raise AppError("Missing QStash signature", 401)
        payload = None
        for key in self.keys:
            try:
                payload = jwt.decode(
                    signature,
                    key,
                    algorithms=["HS256"],
                    issuer="Upstash",
                    leeway=15,
                )
                break
            except jwt.PyJWTError:
                continue
        if payload is None:
            raise AppError("Invalid QStash signature", 401)
        if payload.get("sub") != url:
            raise AppError("QStash signature is for a different url", 401)
        expected = payload.get("body", "")
        actual = base64.urlsafe_b64encode(hashlib.sha256(body).digest()).decode().rstrip("=")
        if not hmac.compare_digest(str(expected).rstrip("="), actual):
            raise AppError("QStash body hash does not match", 401)


def _public_error(status: int, body: str) -> str:
    text = " ".join(body.split())
    if "not found in this region" in text:
        return f"{status} token is for a different QStash region"
    return f"{status} {text[:160]}"
