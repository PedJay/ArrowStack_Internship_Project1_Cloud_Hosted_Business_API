"""Application settings.

Values come from environment variables. In AWS, credentials are NOT passed as
plain env vars: the app receives only the *ARN* of a Secrets Manager secret and
fetches the value using the EC2 instance role.
"""
from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass
from functools import lru_cache

from sqlalchemy.engine import URL, make_url

LOCAL_DEV_API_KEY = "local-dev-key"
DB_CREDENTIAL_TTL_SECONDS = 300


@dataclass(frozen=True)
class Settings:
    environment: str
    database_url: URL
    db_secret_arn: str | None
    api_key: str
    log_level: str


def _fetch_secret(secret_arn: str) -> str:
    import boto3  # imported lazily so local runs don't need AWS config

    client = boto3.client("secretsmanager", region_name=os.getenv("AWS_REGION"))
    return client.get_secret_value(SecretId=secret_arn)["SecretString"]


def _database_url(secret_arn: str | None) -> URL:
    if secret_arn:
        # Username/password are injected per connection (see db.py) so that
        # RDS's automatic 7-day password rotation never breaks the app.
        return URL.create(
            "postgresql+psycopg",
            host=os.environ["DB_HOST"],
            port=int(os.getenv("DB_PORT", "5432")),
            database=os.getenv("DB_NAME", "businessapi"),
            query={"sslmode": "require"},
        )
    return make_url(os.getenv("DATABASE_URL", "sqlite:///./local.db"))


def _api_key(environment: str) -> str:
    secret_arn = os.getenv("API_KEY_SECRET_ARN")
    if secret_arn:
        return _fetch_secret(secret_arn).strip()
    key = os.getenv("API_KEY", "")
    if key:
        return key
    if environment == "local":
        return LOCAL_DEV_API_KEY
    raise RuntimeError("API key is not configured (set API_KEY_SECRET_ARN or API_KEY)")


@lru_cache
def get_settings() -> Settings:
    environment = os.getenv("APP_ENV", "local")
    db_secret_arn = os.getenv("DB_SECRET_ARN") or None
    return Settings(
        environment=environment,
        database_url=_database_url(db_secret_arn),
        db_secret_arn=db_secret_arn,
        api_key=_api_key(environment),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )


_creds_lock = threading.Lock()
_creds_cache: tuple[float, tuple[str, str]] | None = None


def get_db_credentials(force_refresh: bool = False) -> tuple[str, str]:
    """(username, password) from the RDS-managed secret, cached for a few minutes."""
    global _creds_cache
    with _creds_lock:
        if not force_refresh and _creds_cache and time.monotonic() - _creds_cache[0] < DB_CREDENTIAL_TTL_SECONDS:
            return _creds_cache[1]
        secret = json.loads(_fetch_secret(get_settings().db_secret_arn))
        creds = (secret["username"], secret["password"])
        _creds_cache = (time.monotonic(), creds)
        return creds


def reset_credential_cache() -> None:
    global _creds_cache
    with _creds_lock:
        _creds_cache = None
