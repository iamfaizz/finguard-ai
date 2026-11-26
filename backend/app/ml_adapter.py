"""Member C's confirmed HTTP contract; no fabricated predictions."""
from decimal import Decimal

def forecast_payload(rows, horizon=30):
    return {'transactions': [{'amount': float(t.amount), 'category': t.category or 'Uncategorized', 'timestamp': t.timestamp.isoformat(), 'type': t.txn_type} for t in rows if t.txn_type == 'debit'], 'horizon': horizon}

def forecast_summary(result, income):
    return {'total_spend': str(Decimal(str(result['total_predicted_spending']))), 'total_income': str(income), 'low_confidence': bool(result['low_confidence'])}
