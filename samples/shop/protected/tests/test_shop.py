# Visible tests. Locked: agents may not change these.
def signup(c, email="a@x.com"):
    return c.post("/signup", data={"email": email, "password": "pw"}, follow_redirects=False)

def test_signup_sets_session_and_redirects(client):
    r = signup(client)
    assert r.status_code == 303 and r.headers["location"] == "/products"

def test_products_listed(client):
    signup(client)
    assert "Notebook" in client.get("/products").text

def test_cart_shows_single_item(client):
    signup(client)
    client.post("/cart/add", data={"product_id": 1, "qty": 1})
    assert "Notebook x 1" in client.get("/cart").text

def test_checkout_creates_order_for_one_item(client):
    signup(client)
    client.post("/cart/add", data={"product_id": 2, "qty": 1})
    r = client.post("/checkout")
    assert "Order placed" in r.text
    assert client.get("/api/orders", params={"email": "a@x.com"}).json()[0]["total_cents"] == 350
