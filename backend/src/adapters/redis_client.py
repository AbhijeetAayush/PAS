from __future__ import annotations

import httpx


class RedisClient:
    def __init__(self, url: str, token: str) -> None:
        self.url = url.rstrip("/")
        self.token = token

    def get(self, key: str) -> str | None:
        result = self._command("GET", key)
        if result is None:
            return None
        return str(result)

    def set(self, key: str, value: str, ex: int) -> None:
        self._command("SET", key, value, "EX", str(ex))

    def lock(self, key: str, ex: int) -> bool:
        result = self._command("SET", key, "1", "NX", "EX", str(ex))
        return result == "OK"

    def unlock(self, key: str) -> None:
        self._command("DEL", key)

    def _command(self, *parts: str) -> object:
        response = httpx.post(
            self.url,
            json=list(parts),
            headers={"Authorization": f"Bearer {self.token}"},
            timeout=15,
        )
        response.raise_for_status()
        body = response.json()
        if isinstance(body, dict) and body.get("error"):
            raise RuntimeError(str(body["error"]))
        if isinstance(body, dict):
            return body.get("result")
        return body
