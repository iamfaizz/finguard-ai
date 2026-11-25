"""CP-5.6: /chat contract tests (auth, validation, JSON mode, SSE mode, rate limit)."""
import json

import jwt
import pytest
from fastapi.testclient import TestClient

from app import main
from app.config import settings
from app.rate_limit import RateLimiter

TOKEN = jwt.encode({"sub": "42"}, settings.jwt_secret, algorithm=settings.jwt_algorithm)
AUTH = {"Authorization": f"Bearer {TOKEN}"}
SRC = {"index": 1, "title": "T", "source_url": "https://x.gov/", "section": "S", "as_of": "2025-04-01", "snippet": "s"}


class FakeAdvisor:
    async def run(self, question, history, user):
        assert user.user_id == "42"  # id comes from the token
        yield {"type": "token", "text": "Hello "}
        yield {"type": "token", "text": "[1]"}
        yield {"type": "sources", "sources": [SRC]}
        yield {"type": "done", "refused": False, "used_tools": []}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(main, "advisor", FakeAdvisor())
    monkeypatch.setattr(main, "rate_limiter", RateLimiter(100))
    return TestClient(main.app)  # no `with`: skips model warm-up


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"


def test_requires_valid_token(client):
    assert client.post("/chat", json={"message": "hi"}).status_code == 401
    assert client.post("/chat", json={"message": "hi"}, headers={"Authorization": "Bearer bad"}).status_code == 401


@pytest.mark.parametrize("body", [{}, {"message": ""}, {"message": "a" * 501}, {"message": "hi", "history": [{"role": "system", "content": "x"}]}])
def test_malformed_payload_is_422(client, body):
    assert client.post("/chat", json=body, headers=AUTH).status_code == 422


def test_json_mode_matches_contract(client):
    r = client.post("/chat", json={"message": "What is 80C?", "stream": False}, headers=AUTH)
    assert r.status_code == 200
    d = r.json()
    assert d["answer"] == "Hello [1]" and d["sources"][0]["as_of"] == "2025-04-01"
    assert d["used_tools"] == [] and d["refused"] is False


def test_stream_mode_emits_sse_events(client):
    r = client.post("/chat", json={"message": "What is 80C?"}, headers=AUTH)
    assert r.headers["content-type"].startswith("text/event-stream")
    events = [b.split("\n") for b in r.text.strip().split("\n\n")]
    names = [e[0].removeprefix("event: ") for e in events]
    assert names == ["token", "token", "sources", "done"]
    assert json.loads(events[0][1].removeprefix("data: "))["text"] == "Hello "


def test_rate_limit_returns_429(client, monkeypatch):
    monkeypatch.setattr(main, "rate_limiter", RateLimiter(2))
    codes = [client.post("/chat", json={"message": "hi", "stream": False}, headers=AUTH).status_code for _ in range(3)]
    assert codes == [200, 200, 429]