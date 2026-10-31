def test_liveness(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_readiness_reports_database(client):
    r = client.get("/health/ready")
    assert r.status_code == 200
    assert r.json()["database"] == "reachable"


def test_request_id_is_echoed(client):
    r = client.get("/health", headers={"x-request-id": "abc-123"})
    assert r.headers["x-request-id"] == "abc-123"


def test_request_id_generated_when_absent(client):
    r = client.get("/health")
    assert len(r.headers["x-request-id"]) == 36
