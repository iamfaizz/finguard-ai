
"""CP-5.6: /chat contract tests."""

import json
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient

from app import main
from app.config import settings
from app.rate_limit import RateLimiter

TOKEN = jwt.encode(
    {
        "sub": "42",
        "type": "access",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
    },
    settings.jwt_secret,
    algorithm=settings.jwt_algorithm,
)

AUTH = {"Authorization": f"Bearer {TOKEN}"}

SRC = {
    "index": 1,
    "title": "T",
    "source_url": "https://x.gov/",
    "section": "S",
    "as_of": "2025-04-01",
    "snippet": "s",
}


class FakeAdvisor:
    async def run(self, question, history, user):
        assert user.user_id == "42"

        yield {"type": "token", "text": "Hello "}
        yield {"type": "token", "text": "[1]"}
        yield {"type": "sources", "sources": [SRC]}
        yield {
            "type": "done",
            "refused": False,
            "used_tools": [],
        }


class BrokenAdvisor:
    async def run(self, question, history, user):
        raise RuntimeError("Simulated LLM failure")
        yield  # Makes this an async generator.


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(main, "advisor", FakeAdvisor())
    monkeypatch.setattr(main, "rate_limiter", RateLimiter(100))

    monkeypatch.setattr(
        settings,
        "llm_provider",
        "ollama",
    )
    monkeypatch.setattr(
        settings,
        "ollama_base_url",
        "http://host.docker.internal:11434",
    )
    monkeypatch.setattr(
        settings,
        "ollama_model",
        "llama3.2:3b",
    )

    return TestClient(main.app)


def test_health(client):
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "ok"
    assert data["provider"] == "ollama"
    assert data["llm_configured"] is True


def test_health_claude_without_key(client, monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "claude")
    monkeypatch.setattr(settings, "anthropic_api_key", "")

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["llm_configured"] is False


def test_health_unknown_provider(client, monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "unknown")

    response = client.get("/health")

    assert response.json()["llm_configured"] is False


def test_requires_valid_token(client):
    assert client.post(
        "/chat",
        json={"message": "hi"},
    ).status_code == 401

    assert client.post(
        "/chat",
        json={"message": "hi"},
        headers={"Authorization": "Bearer bad"},
    ).status_code == 401


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"message": ""},
        {"message": "a" * 501},
        {
            "message": "hi",
            "history": [
                {"role": "system", "content": "x"}
            ],
        },
    ],
)
def test_malformed_payload_is_422(client, body):
    response = client.post(
        "/chat",
        json=body,
        headers=AUTH,
    )

    assert response.status_code == 422


def test_json_mode_matches_contract(client):
    response = client.post(
        "/chat",
        json={
            "message": "What is 80C?",
            "stream": False,
        },
        headers=AUTH,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["answer"] == "Hello [1]"
    assert data["sources"][0]["as_of"] == "2025-04-01"
    assert data["used_tools"] == []
    assert data["refused"] is False


def test_stream_mode_emits_sse_events(client):
    response = client.post(
        "/chat",
        json={"message": "What is 80C?"},
        headers=AUTH,
    )

    assert response.headers["content-type"].startswith(
        "text/event-stream"
    )

    events = [
        block.split("\n")
        for block in response.text.strip().split("\n\n")
    ]

    names = [
        event[0].removeprefix("event: ")
        for event in events
    ]

    assert names == [
        "token",
        "token",
        "sources",
        "done",
    ]

    assert (
        json.loads(
            events[0][1].removeprefix("data: ")
        )["text"]
        == "Hello "
    )


def test_missing_llm_configuration_returns_503(client, monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "claude")
    monkeypatch.setattr(settings, "anthropic_api_key", "")

    response = client.post(
        "/chat",
        json={
            "message": "Hello",
            "stream": False,
        },
        headers=AUTH,
    )

    assert response.status_code == 503
    assert response.json()["detail"] == (
        "Advisor LLM is not configured"
    )


def test_llm_runtime_failure_returns_503(client, monkeypatch):
    monkeypatch.setattr(main, "advisor", BrokenAdvisor())

    response = client.post(
        "/chat",
        json={
            "message": "Hello",
            "stream": False,
        },
        headers=AUTH,
    )

    assert response.status_code == 503
    assert response.json()["detail"] == (
        "Advisor temporarily unavailable"
    )


def test_rate_limit_returns_429(client, monkeypatch):
    monkeypatch.setattr(
        main,
        "rate_limiter",
        RateLimiter(2),
    )

    codes = [
        client.post(
            "/chat",
            json={
                "message": "hi",
                "stream": False,
            },
            headers=AUTH,
        ).status_code
        for _ in range(3)
    ]

    assert codes == [200, 200, 429]
