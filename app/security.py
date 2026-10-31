import hmac

from fastapi import Header, HTTPException, status

from app.config import get_settings


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """Write endpoints require the X-API-Key header (compared in constant time)."""
    expected = get_settings().api_key
    if not x_api_key or not hmac.compare_digest(x_api_key, expected):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Missing or invalid API key")
