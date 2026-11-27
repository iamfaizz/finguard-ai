import asyncio
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, AsyncMock
from app import main

def test_pending_worker_does_not_starve(monkeypatch):
    batches = [
        [SimpleNamespace(id=i, merchant="Shop", timestamp=datetime(2026, 1, 1)) for i in range(1, 21)],
        [SimpleNamespace(id=i, merchant="Shop", timestamp=datetime(2026, 1, 1)) for i in range(21, 26)]
    ]

    db = MagicMock()
    db.scalars.return_value.all.side_effect = batches

    session = MagicMock()
    session.__enter__.return_value = db

    monkeypatch.setattr(main, "SessionLocal", lambda: session)

    service = AsyncMock(side_effect=RuntimeError("Unavailable"))
    monkeypatch.setattr(main, "service", service)

    sleep = AsyncMock(side_effect=[None, asyncio.CancelledError()])
    monkeypatch.setattr(main.asyncio, "sleep", sleep)

    try:
        asyncio.run(main.retry_pending())
    except asyncio.CancelledError:
        pass

    assert service.await_count == 25
    assert db.commit.call_count == 25
    queries = db.scalars.call_args_list
    params = queries[1].args[0].compile().params
    assert 20 in params.values()
    assert all(t.reason.startswith("Pending review:") for batch in batches for t in batch)
