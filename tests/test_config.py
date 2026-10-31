"""Secrets are fetched from AWS Secrets Manager when ARNs are configured (mocked with moto)."""
import json

import boto3
import pytest
from moto import mock_aws

from app import config


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for var in ("DB_SECRET_ARN", "API_KEY_SECRET_ARN", "API_KEY", "DATABASE_URL", "DB_HOST", "APP_ENV"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("AWS_REGION", "ap-south-1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    config.get_settings.cache_clear()
    config.reset_credential_cache()
    yield
    config.get_settings.cache_clear()
    config.reset_credential_cache()


def _aws_env(monkeypatch):
    sm = boto3.client("secretsmanager", region_name="ap-south-1")
    db_arn = sm.create_secret(Name="db", SecretString=json.dumps({"username": "app", "password": "p@ss:w/rd"}))["ARN"]
    key_arn = sm.create_secret(Name="key", SecretString="super-secret-key\n")["ARN"]
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("DB_SECRET_ARN", db_arn)
    monkeypatch.setenv("DB_HOST", "db.internal")
    monkeypatch.setenv("API_KEY_SECRET_ARN", key_arn)
    return sm, db_arn


@mock_aws
def test_settings_load_from_secrets_manager(monkeypatch):
    _aws_env(monkeypatch)
    s = config.get_settings()
    assert s.api_key == "super-secret-key"
    assert s.database_url.host == "db.internal"
    assert s.database_url.password is None  # never baked into the URL
    assert s.database_url.query["sslmode"] == "require"
    assert config.get_db_credentials() == ("app", "p@ss:w/rd")


@mock_aws
def test_db_credentials_follow_rotation(monkeypatch):
    sm, db_arn = _aws_env(monkeypatch)
    assert config.get_db_credentials()[1] == "p@ss:w/rd"

    sm.put_secret_value(SecretId=db_arn, SecretString=json.dumps({"username": "app", "password": "rotated"}))
    assert config.get_db_credentials()[1] == "p@ss:w/rd"  # still cached
    assert config.get_db_credentials(force_refresh=True)[1] == "rotated"  # what db.py does after a login failure


def test_non_local_env_requires_api_key(monkeypatch):
    monkeypatch.setenv("APP_ENV", "prod")
    with pytest.raises(RuntimeError):
        config.get_settings()


def test_local_env_has_dev_defaults():
    s = config.get_settings()
    assert s.api_key == config.LOCAL_DEV_API_KEY
    assert s.database_url.get_backend_name() == "sqlite"
