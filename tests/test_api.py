from fastapi.testclient import TestClient

from place_search.api import app

client = TestClient(app)


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_search_cafe():
    r = client.get("/search", params={"q": "quán cà phê trứng", "top_k": 3})
    assert r.status_code == 200
    assert r.json()["results"][0]["category"] == "cat-cafe"


def test_empty_query_rejected():
    assert client.get("/search", params={"q": ""}).status_code == 422