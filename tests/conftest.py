import pytest
from fastapi.testclient import TestClient

API_KEY = "test-key"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("API_KEY", API_KEY)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    for var in ("DB_SECRET_ARN", "API_KEY_SECRET_ARN"):
        monkeypatch.delenv(var, raising=False)

    from app import config, db

    config.get_settings.cache_clear()
    db.get_engine.cache_clear()
    db._session_factory.cache_clear()

    from app.main import app

    with TestClient(app) as c:
        yield c

    db.get_engine().dispose()
    config.get_settings.cache_clear()
    db.get_engine.cache_clear()
    db._session_factory.cache_clear()


@pytest.fixture()
def auth():
    return {"X-API-Key": API_KEY}


@pytest.fixture()
def make_product(client, auth):
    def _make(sku="TSHIRT-BLK-M", name="Black T-Shirt (M)", price_cents=49900, stock=10, reorder_level=3):
        r = client.post(
            "/products",
            json={"sku": sku, "name": name, "price_cents": price_cents, "stock": stock, "reorder_level": reorder_level},
            headers=auth,
        )
        assert r.status_code == 201, r.text
        return r.json()

    return _make
