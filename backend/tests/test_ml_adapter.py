from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from app.ml_adapter import forecast_payload, forecast_summary

def test_forecast_contract():
    t=SimpleNamespace(amount=Decimal('12.50'),category='Food',timestamp=datetime(2026,1,1,tzinfo=timezone.utc),txn_type='debit')
    assert forecast_payload([t]) == {'transactions':[{'amount':12.5,'category':'Food','timestamp':'2026-01-01T00:00:00+00:00','type':'debit'}],'horizon':30}

def test_summary():
    assert forecast_summary({'total_predicted_spending':100,'low_confidence':True},Decimal('200')) == {'total_spend':'100','total_income':'200','low_confidence':True}
