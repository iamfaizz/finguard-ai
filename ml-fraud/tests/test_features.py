import pandas as pd
from src.features import build_features


def toy():
    rows = []
    for i in range(10):   # ten ordinary debits, one per day
        rows.append(dict(txn_id=f"T{i:02d}", user_id="U1", timestamp=f"2025-01-{i+1:02d}T12:00:00", amount=100.0,
                         merchant="ShopA", category="Shopping", device="Web", location="Pune",
                         txn_type="debit", balance=5000.0 - 100 * i))
    rows.append(dict(txn_id="T10", user_id="U1", timestamp="2025-01-20T03:00:00", amount=1000.0,
                     merchant="ShopB", category="Shopping", device="NewPhone", location="Delhi",
                     txn_type="debit", balance=3000.0))
    return pd.DataFrame(rows)


def test_deviation_features():
    f = build_features(toy())
    last = f.iloc[-1]
    assert abs(last.amount_ratio_cat - 10) < 1e-9          # 1000 vs a usual 100
    assert last.is_new_merchant == 1 and last.is_new_device == 1 and last.is_new_city == 1
    assert last.is_night == 1 and last.n_prior == 10
    assert f.iloc[1].is_new_merchant == 0                   # ShopA already seen


def test_velocity_burst():
    df = toy().iloc[:1].copy()
    burst = [dict(df.iloc[0], txn_id=f"B{i}", timestamp=f"2025-02-01T10:0{i}:00") for i in range(5)]
    f = build_features(pd.concat([df, pd.DataFrame(burst)], ignore_index=True))
    assert f.iloc[-1].txn_10m == 4                          # the four earlier burst rows, current row excluded


def test_no_future_leakage():
    base = toy()
    f1 = build_features(base)
    changed = base.copy()
    changed.loc[changed.index[-1], ["amount", "merchant", "device", "location"]] = [999999.0, "X", "Y", "Z"]
    f2 = build_features(changed)
    cols = [c for c in f1.columns if c != "txn_id"]
    pd.testing.assert_frame_equal(f1.iloc[:-1][cols], f2.iloc[:-1][cols])   # earlier rows must not change
