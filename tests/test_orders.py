def _order(client, auth, items, email="Customer@Example.com"):
    return client.post("/orders", json={"customer_email": email, "items": items}, headers=auth)


def test_order_decrements_stock_and_totals(client, auth, make_product):
    shirt = make_product(sku="SHIRT-1", price_cents=50000, stock=10)
    cap = make_product(sku="CAP-1", price_cents=25000, stock=4)

    r = _order(client, auth, [{"product_id": shirt["id"], "quantity": 2}, {"product_id": cap["id"], "quantity": 1}])
    assert r.status_code == 201, r.text
    order = r.json()
    assert order["total_cents"] == 2 * 50000 + 25000
    assert order["customer_email"] == "customer@example.com"
    assert len(order["items"]) == 2

    assert client.get(f"/products/{shirt['id']}").json()["stock"] == 8
    assert client.get(f"/products/{cap['id']}").json()["stock"] == 3


def test_price_is_captured_at_order_time(client, auth, make_product):
    p = make_product(price_cents=1000)
    order = _order(client, auth, [{"product_id": p["id"], "quantity": 1}]).json()
    client.patch(f"/products/{p['id']}", json={"price_cents": 9999}, headers=auth)
    again = client.get(f"/orders/{order['id']}").json()
    assert again["items"][0]["unit_price_cents"] == 1000
    assert again["total_cents"] == 1000


def test_insufficient_stock_is_rejected_atomically(client, auth, make_product):
    a = make_product(sku="A-001", stock=5)
    b = make_product(sku="B-001", stock=1)
    r = _order(client, auth, [{"product_id": a["id"], "quantity": 2}, {"product_id": b["id"], "quantity": 3}])
    assert r.status_code == 409
    assert r.json()["detail"]["items"] == [{"product_id": b["id"], "requested": 3, "available": 1}]
    # nothing was deducted from A, even though A alone had enough stock
    assert client.get(f"/products/{a['id']}").json()["stock"] == 5


def test_unknown_product_in_order(client, auth, make_product):
    p = make_product()
    r = _order(client, auth, [{"product_id": p["id"], "quantity": 1}, {"product_id": 777, "quantity": 1}])
    assert r.status_code == 404
    assert r.json()["detail"]["product_ids"] == [777]


def test_order_validation(client, auth, make_product):
    p = make_product()
    assert _order(client, auth, []).status_code == 422  # no items
    assert _order(client, auth, [{"product_id": p["id"], "quantity": 0}]).status_code == 422
    assert _order(client, auth, [{"product_id": p["id"], "quantity": 1}], email="not-an-email").status_code == 422
    dup = [{"product_id": p["id"], "quantity": 1}, {"product_id": p["id"], "quantity": 2}]
    assert _order(client, auth, dup).status_code == 422


def test_order_requires_api_key(client, make_product):
    p = make_product()
    r = client.post("/orders", json={"customer_email": "a@b.com", "items": [{"product_id": p["id"], "quantity": 1}]})
    assert r.status_code == 401


def test_list_orders_newest_first(client, auth, make_product):
    p = make_product(stock=10)
    first = _order(client, auth, [{"product_id": p["id"], "quantity": 1}]).json()
    second = _order(client, auth, [{"product_id": p["id"], "quantity": 1}]).json()
    ids = [o["id"] for o in client.get("/orders").json()]
    assert ids == [second["id"], first["id"]]


def test_unknown_order_404(client):
    assert client.get("/orders/12345").status_code == 404
