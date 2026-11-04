from __future__ import annotations

import jwt
from jwt import PyJWKClient

from config.settings import Settings
from domain.models import AppError

_jwks: dict[str, PyJWKClient] = {}


def require_user(settings: Settings, authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AppError("Login required", 401)
    token = authorization.split(" ", 1)[1].strip()
    settings.require("supabase_url")
    try:
        if settings.supabase_jwt_secret:
            payload = jwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                audience="authenticated",
                leeway=20,
            )
        else:
            payload = _decode_jwks(settings.supabase_url, token)
    except jwt.PyJWTError as exc:
        raise AppError("Login expired or invalid", 401) from exc
    user_id = payload.get("sub")
    if not user_id:
        raise AppError("Login token has no user", 401)
    return str(user_id)


def _decode_jwks(supabase_url: str, token: str) -> dict:
    client = _jwks.get(supabase_url)
    if client is None:
        client = PyJWKClient(f"{supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json")
        _jwks[supabase_url] = client
    key = client.get_signing_key_from_jwt(token)
    try:
        return jwt.decode(token, key.key, algorithms=["RS256", "ES256"], audience="authenticated", leeway=20)
    except jwt.InvalidAudienceError:
        payload = jwt.decode(
            token,
            key.key,
            algorithms=["RS256", "ES256"],
            leeway=20,
            options={"verify_aud": False},
        )
        if payload.get("role") != "authenticated":
            raise jwt.InvalidTokenError("unexpected role")
        return payload
