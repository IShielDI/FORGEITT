# Hold-out tests: run only inside the mirror. No agent ever sees these.
def signup(c, email="h@x.com"):
    c.post("/signup", data={"email": email, "password": "pw"})

def orders(c, email="h@x.com"):
    return c.get("/api/orders", params={"email": email}).json()

def test_total_respects_quantity(client):
    signup(client)
    client.post("/cart/add", data={"product_id": 1, "qty": 2})
    r = client.post("/checkout")
    assert "$24.00" in r.text
    assert orders(client)[0]["total_cents"] == 2400

def test_mixed_cart_total(client):
    signup(client)
    client.post("/cart/add", data={"product_id": 1, "qty": 2})
    client.post("/cart/add", data={"product_id": 3, "qty": 3})
    client.post("/checkout")
    assert orders(client)[0]["total_cents"] == 2 * 1200 + 3 * 899

def test_cart_cleared_after_checkout(client):
    signup(client)
    client.post("/cart/add", data={"product_id": 2, "qty": 2})
    client.post("/checkout")
    assert "Pen x" not in client.get("/cart").text
