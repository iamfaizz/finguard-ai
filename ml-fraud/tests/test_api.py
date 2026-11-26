import pytest
from fastapi.testclient import TestClient

from src.api import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def valid_payload():
    return {
        "n_prior": 17,
        "is_debit": 1,
        "hour": 13,
        "is_night": 0,
        "day_of_week": 2,
        "amount": 1065.4,
        "amount_z_user": -0.7873017912605824,
        "amount_ratio_cat": 0.5982620414695436,
        "amt_to_prev_balance": 0.21578814117170492,
        "is_new_merchant": 1,
        "is_new_device": 0,
        "is_new_city": 0,
        "hour_bucket_share": 0.35294117647058826,
        "txn_10m": 2,
        "txn_1h": 2,
        "txn_24h": 2,
        "secs_since_last": 65.0,
    }


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["model_version"] == "fraud_v2"


def test_missing_features_rejected(client):
    response = client.post("/score", json={})
    assert response.status_code == 422


def test_negative_amount_rejected(client, valid_payload):
    valid_payload["amount"] = -500
    response = client.post("/score", json=valid_payload)
    assert response.status_code == 422


def test_unexpected_feature_rejected(client, valid_payload):
    valid_payload["unknown_feature"] = 123
    response = client.post("/score", json=valid_payload)
    assert response.status_code == 422


def test_valid_transaction_scored(client, valid_payload):
    response = client.post("/score", json=valid_payload)

    assert response.status_code == 200

    result = response.json()
    assert 0 <= result["fraud_probability"] <= 1
    assert result["risk_level"] in ["LOW", "MEDIUM", "HIGH"]
    assert isinstance(result["reasons"], list)
    assert result["model_version"] == "fraud_v2"


def test_api_score_matches_direct_model(client, valid_payload):
    import pandas as pd
    import xgboost as xgb
    from src.api import MODEL_PATH

    response = client.post("/score", json=valid_payload)
    assert response.status_code == 200

    model = xgb.XGBClassifier()
    model.load_model(str(MODEL_PATH))

    features = app.state.features
    X = pd.DataFrame(
        [[valid_payload[name] for name in features]],
        columns=features,
    )

    expected_score = float(model.predict_proba(X)[0, 1])
    actual_score = response.json()["fraud_probability"]

    assert actual_score == pytest.approx(expected_score, abs=1e-7)
