from fastapi.testclient import TestClient

from forecast_service import app


def test_health_contract():
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "0.2.0-role-c"}


def test_single_transaction_categorization_contract():
    with TestClient(app) as client:
        response = client.post(
            "/categorize",
            json={"narration": "UPI/ZOMATO/123", "merchant": ""},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["category"] == "Food"
    assert body["method"] == "keyword_rule"


def test_batch_categorization_contract():
    with TestClient(app) as client:
        response = client.post(
            "/categorize",
            json={
                "transactions": [
                    {"narration": "SWIGGY ORDER", "merchant": "Swiggy"},
                    {"narration": "UBER TRIP", "merchant": "Uber"},
                ]
            },
        )

    assert response.status_code == 200
    results = response.json()["results"]
    assert [item["category"] for item in results] == ["Food", "Transport"]


def test_forecast_contract_and_low_history_flag():
    transactions = [
        {
            "timestamp": f"2026-01-0{day}T12:00:00",
            "amount": 100.0 * day,
            "category": "Food",
            "type": "debit",
        }
        for day in range(1, 6)
    ]

    with TestClient(app) as client:
        response = client.post(
            "/forecast",
            json={"transactions": transactions, "horizon": 7},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["forecast_days"] == 7
    assert body["low_confidence"] is True
    assert len(body["dates"]) == 7
    assert len(body["daily_predicted_spending"]) == 7
    assert body["total_predicted_spending"] >= 0
    assert "Food" in body["category_forecasts"]


def test_goal_planner_contract_and_cut_cap():
    with TestClient(app) as client:
        response = client.post(
            "/goal-plan",
            json={
                "target_amount": 10000,
                "saved_amount": 1000,
                "months_left": 3,
                "forecast_income": 5000,
                "forecast_spending": 3000,
                "category_forecasts": {"Food": 1000, "Shopping": 500},
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["goal"]["required_monthly_savings"] == 3000
    assert body["status"] in {"feasible", "infeasible"}
    assert body["total_recommended_cuts"] <= 0.30 * 1500 + 0.01


def test_invalid_forecast_horizon_returns_client_error():
    with TestClient(app) as client:
        response = client.post(
            "/forecast",
            json={
                "transactions": [
                    {
                        "timestamp": "2026-01-01T12:00:00",
                        "amount": 100,
                        "category": "Food",
                        "type": "debit",
                    }
                ],
                "horizon": 0,
            },
        )

    assert response.status_code == 400
