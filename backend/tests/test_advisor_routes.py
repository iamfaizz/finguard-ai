import os
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("JWT_SECRET_KEY", "test-only-secret-not-for-production-12345")
from fastapi.testclient import TestClient
from app.main import app

def test_advisor_registered():
    client = TestClient(app)
    paths = client.get("/openapi.json").json()["paths"]
    for route in ("spending-summary", "forecast", "affordability", "goal-status", "chat-messages"):
        assert "/api/advisor-tools/" + route in paths

def test_chat_requires_auth():
    client = TestClient(app)
    assert client.post("/api/advisor-tools/chat-messages", json={"question":"test", "answer":"test", "sources":[]}).status_code == 401
