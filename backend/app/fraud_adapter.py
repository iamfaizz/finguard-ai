"""Use Member A's unmodified feature builder; adapt unavailable CSV fields explicitly."""
import math
import pandas as pd
try:
    from fraud_features import FEATURES, build_features
except ModuleNotFoundError as exc:
    if exc.name != "fraud_features":
        raise
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location("fraud_features", Path(__file__).resolve().parents[2] / "ml-fraud" / "src" / "features.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    FEATURES, build_features = module.FEATURES, module.build_features


def score_payload(history):
    rows = [dict(txn_id=t.id, user_id=t.user_id,
                 timestamp=pd.Timestamp(t.timestamp).tz_localize(None),
                 amount=float(t.amount), merchant=t.merchant,
                 category=t.category or 'Uncategorized', txn_type=t.txn_type,
                 balance=float('nan'), device=None, location=None) for t in history]
    row = build_features(pd.DataFrame(rows)).iloc[-1]
    # API requires finite values. Missing history/device/balance use neutral zero;
    # this is an integration fallback, not a validated training-time imputation.
    ints = {'n_prior','is_debit','hour','is_night','day_of_week','is_new_merchant','is_new_device','is_new_city','txn_10m','txn_1h','txn_24h'}
    result = {}
    for key in FEATURES:
        v = float(row[key])
        v = v if math.isfinite(v) else 0.0
        result[key] = int(v) if key in ints else v
    return result
