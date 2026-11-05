# Integration Tests
PYTHON_URL = "https://www.python.org"


def create_link(client, url=PYTHON_URL):
    return client.post("/links", json={"long_url": url})


def test_create_link_returns_201_and_short_url(client):
    response = create_link(client)
    assert response.status_code == 201
    body = response.json()
    assert len(body["code"]) == 7
    assert body["short_url"].endswith(body["code"])


def test_create_link_rejects_invalid_url(client):
    response = create_link(client, url="not a url")
    assert response.status_code == 422


def test_redirect_goes_to_long_url(client):
    code = create_link(client).json()["code"]
    response = client.get(f"/{code}", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "https://www.python.org/"


def test_unknown_code_returns_404(client):
    response = client.get("/nope123", follow_redirects=False)
    assert response.status_code == 404


def test_redirect_fills_the_cache(client, fake_redis):
    code = create_link(client).json()["code"]
    client.get(f"/{code}", follow_redirects=False)
    assert fake_redis.get(f"link:{code}") == "https://www.python.org/"


def test_list_links_paginates(client):
    for i in range(3):
        create_link(client, url=f"https://example.com/{i}")
    body = client.get("/links", params={"limit": 2}).json()
    assert body["total"] == 3
    assert len(body["items"]) == 2


def test_rate_limit_blocks_eleventh_create(client):
    for _ in range(10):
        assert create_link(client).status_code == 201
    response = create_link(client)
    assert response.status_code == 429
    assert "retry-after" in response.headers


def test_redirect_publishes_click_event(client, published_clicks):
    code = create_link(client).json()["code"]
    client.get(f"/{code}", follow_redirects=False)
    assert published_clicks == [code]


def test_unknown_code_publishes_nothing(client, published_clicks):
    client.get("/nope123", follow_redirects=False)
    assert published_clicks == []


def test_health_and_ready(client):
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/ready").json() == {"status": "ready"}
