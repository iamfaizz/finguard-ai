from datetime import datetime, timedelta
from types import SimpleNamespace
from app.fraud_adapter import score_payload, FEATURES

def test_payload():
    t = datetime(2026,1,1)
    rows = [SimpleNamespace(id=i,user_id=1,timestamp=t+timedelta(minutes=i),amount=100,merchant='Shop',category='Food',txn_type='debit') for i in range(3)]
    result = score_payload(rows)
    assert set(result) == set(FEATURES)
    assert result['n_prior'] == 2 and result['txn_10m'] == 2
    assert result['is_new_merchant'] == 0
    assert result['amt_to_prev_balance'] == 0
