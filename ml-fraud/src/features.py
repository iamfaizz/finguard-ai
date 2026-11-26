"""Point-in-time fraud features: every value uses only the user's transactions BEFORE the current one."""
import numpy as np
import pandas as pd

FEATURES = [
    "n_prior", "is_debit", "hour", "is_night", "day_of_week",
    "amount", "amount_z_user", "amount_ratio_cat", "amt_to_prev_balance",
    "is_new_merchant", "is_new_device", "is_new_city",
    "hour_bucket_share", "txn_10m", "txn_1h", "txn_24h", "secs_since_last",
]


def _prior_in_window(ts: np.ndarray, window: np.timedelta64) -> np.ndarray:
    """For each row (sorted by time): how many EARLIER rows fall within `window` before it.
    Earlier rows with the same timestamp count; later rows never do."""
    return np.arange(len(ts)) - np.searchsorted(ts, ts - window, side="left")


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    d["timestamp"] = pd.to_datetime(d["timestamp"])
    d = d.sort_values(["user_id", "timestamp", "txn_id"], kind="mergesort").reset_index(drop=True)
    g = d.groupby("user_id", sort=False)
    d["_amt"] = d["amount"].where(d["txn_type"] == "debit")      # credits (income) never enter spend statistics

    f = pd.DataFrame({"txn_id": d["txn_id"]})
    f["n_prior"] = g.cumcount()
    f["is_debit"] = (d["txn_type"] == "debit").astype(int)
    f["hour"] = d["timestamp"].dt.hour
    f["is_night"] = (f["hour"] < 6).astype(int)
    f["day_of_week"] = d["timestamp"].dt.dayofweek
    f["amount"] = d["amount"]

    mean_u = d.groupby("user_id")["_amt"].transform(lambda s: s.shift().expanding(5).mean())
    std_u = d.groupby("user_id")["_amt"].transform(lambda s: s.shift().expanding(5).std())
    f["amount_z_user"] = (d["amount"] - mean_u) / std_u.where(std_u > 0)
    mean_c = d.groupby(["user_id", "category"])["_amt"].transform(lambda s: s.shift().expanding(3).mean())
    f["amount_ratio_cat"] = d["amount"] / mean_c.where(mean_c > 0)

    prev_bal = g["balance"].shift()
    f["amt_to_prev_balance"] = d["amount"] / prev_bal.where(prev_bal > 0)

    for col, name in [("merchant", "is_new_merchant"), ("device", "is_new_device"), ("location", "is_new_city")]:
        f[name] = (d.groupby(["user_id", col]).cumcount() == 0).astype(int)
    bucket = d["timestamp"].dt.hour // 4
    same_bucket = d.assign(_b=bucket).groupby(["user_id", "_b"]).cumcount()
    f["hour_bucket_share"] = same_bucket / f["n_prior"].where(f["n_prior"] > 0)

    for name, w in [("txn_10m", np.timedelta64(10, "m")), ("txn_1h", np.timedelta64(1, "h")), ("txn_24h", np.timedelta64(24, "h"))]:
        f[name] = g["timestamp"].transform(lambda s, w=w: _prior_in_window(s.to_numpy(), w))
    f["secs_since_last"] = g["timestamp"].diff().dt.total_seconds()

    f["user_id"], f["timestamp"] = d["user_id"], d["timestamp"]
    return f
