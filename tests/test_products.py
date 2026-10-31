import pytest


def test_create_and_get_product(client, make_product):
    created = make_product()
    r = client.get(f"/products/{created['id']}")
    assert r.status_code == 200
    body = r.json()
    assert body["sku"] == "TSHIRT-BLK-M"
    assert body["price_cents"] == 49900
    assert body["low_stock"] is False


def test_write_requires_api_key(client):
    payload = {"sku": "ABC-1", "name": "x", "price_cents": 1}
    assert client.post("/products", json=payload).status_code == 401
    assert client.post("/products", json=payload, headers={"X-API-Key": "wrong"}).status_code == 401


def test_reads_are_public(client, make_product):
    make_product()
    assert client.get("/products").status_code == 200


def test_duplicate_sku_conflicts(client, make_product):
    make_product(sku="DUP-001")
    r = client.post("/products", json={"sku": "DUP-001", "name": "Other", "price_cents": 1}, headers={"X-API-Key": "test-key"})
    assert r.status_code == 409


@pytest.mark.parametrize(
    "payload",
    [
        {"sku": "ab", "name": "x", "price_cents": 1},  # sku too short / lowercase
        {"sku": "GOOD-SKU", "name": "   ", "price_cents": 1},  # blank name
        {"sku": "GOOD-SKU", "name": "x", "price_cents": -5},  # negative price
        {"sku": "GOOD-SKU", "name": "x", "price_cents": 1, "stock": -1},  # negative stock
        {"sku": "GOOD-SKU", "name": "x"},  # missing price
        {"sku": "GOOD SKU; DROP TABLE", "name": "x", "price_cents": 1},  # injection-style input rejected by pattern
    ],
)
def test_invalid_product_rejected(client, auth, payload):
    assert client.post("/products", json=payload, headers=auth).status_code == 422


def test_unknown_product_404(client):
    assert client.get("/products/9999").status_code == 404


def test_update_product(client, auth, make_product):
    p = make_product()
    r = client.patch(f"/products/{p['id']}", json={"price_cents": 39900, "stock": 2}, headers=auth)
    assert r.status_code == 200
    assert r.json()["price_cents"] == 39900
    assert r.json()["low_stock"] is True


def test_empty_update_rejected(client, auth, make_product):
    p = make_product()
    assert client.patch(f"/products/{p['id']}", json={}, headers=auth).status_code == 422


def test_low_stock_filter(client, make_product):
    make_product(sku="PLENTY-1", stock=100)
    make_product(sku="SCARCE-1", stock=1, reorder_level=5)
    skus = [p["sku"] for p in client.get("/products", params={"low_stock": True}).json()]
    assert skus == ["SCARCE-1"]


def test_pagination_bounds(client):
    assert client.get("/products", params={"limit": 0}).status_code == 422
    assert client.get("/products", params={"limit": 101}).status_code == 422
    assert client.get("/products", params={"offset": -1}).status_code == 422


def test_delete_product(client, auth, make_product):
    p = make_product()
    assert client.delete(f"/products/{p['id']}", headers=auth).status_code == 204
    assert client.get(f"/products/{p['id']}").status_code == 404


def test_cannot_delete_product_with_orders(client, auth, make_product):
    p = make_product()
    client.post("/orders", json={"customer_email": "a@b.com", "items": [{"product_id": p["id"], "quantity": 1}]}, headers=auth)
    assert client.delete(f"/products/{p['id']}", headers=auth).status_code == 409
