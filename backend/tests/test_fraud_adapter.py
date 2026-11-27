from datetime import datetime, timedelta
from types import SimpleNamespace
import pandas as pd
import pytest

from app.fraud_adapter import score_payload, FEATURES, build_features


def history():
    return [
        SimpleNamespace(
            id=i,
            user_id=1,
            timestamp=datetime(2026, 1, 1) + timedelta(minutes=i),
            amount=100 + i * 10,
            merchant="Shop",
            category="Food",
            txn_type="debit",
            balance=5000 - i * 100,
            device="Phone-B" if i == 7 else "Phone-A",
            location="Delhi" if i == 7 else "Noida",
        )
        for i in range(8)
    ]


def test_all_17_features_match_original_builder():
    rows = history()
    raw = pd.DataFrame([
        dict(txn_id=t.id, user_id=t.user_id,
             timestamp=t.timestamp, amount=t.amount,
             merchant=t.merchant, category=t.category,
             txn_type=t.txn_type, balance=t.balance,
             device=t.device, location=t.location)
        for t in rows
    ])

    expected = build_features(raw).iloc[-1]
    actual = score_payload(rows)

    assert len(actual) == 17
    assert set(actual) == set(FEATURES)

    for feature in FEATURES:
        assert actual[feature] == pytest.approx(
            float(expected[feature])
        ), feature

    assert actual["amt_to_prev_balance"] == pytest.approx(170 / 4400)
    assert actual["is_new_device"] == 1
    assert actual["is_new_city"] == 1


@pytest.mark.parametrize("field", ["balance", "device", "location"])
def test_missing_data_rejected(field):
    rows = history()
    setattr(rows[-2], field, None)

    with pytest.raises(ValueError):
        score_payload(rows)


def test_insufficient_history_rejected():
    with pytest.raises(ValueError):
        score_payload(history()[:1])
