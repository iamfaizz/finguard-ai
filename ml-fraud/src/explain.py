"""Turn SHAP contributions into plain-English reasons. A reason is shown only if the feature pushed the
score UP and the feature's actual value makes the sentence true (no invented claims)."""
import numpy as np
import pandas as pd

def _gap(v):
    if v < 1:
        return "Made in the same second as your previous transaction"
    if v < 90:
        return f"Only {v:.0f} seconds since your previous transaction"
    return f"Only {v / 60:.0f} minutes since your previous transaction"


# feature -> (condition on the value, sentence builder)
TEMPLATES = {
    "amount_ratio_cat": (lambda v: v >= 2, lambda v: f"The amount is {v:.1f}x your usual spend in this category"),
    "amount_z_user": (lambda v: v >= 2, lambda v: f"The amount is {v:.1f} standard deviations above your normal spending"),
    "is_new_device": (lambda v: v == 1, lambda v: "This is the first time you have used this device"),
    "is_new_city": (lambda v: v == 1, lambda v: "This is the first time you have transacted from this city"),
    "is_new_merchant": (lambda v: v == 1, lambda v: "This is the first time you have paid this merchant"),
    "is_night": (lambda v: v == 1, lambda v: "The payment was made between midnight and 6 AM"),
    "txn_10m": (lambda v: v >= 2, lambda v: f"{int(v)} other transactions in the last 10 minutes"),
    "txn_1h": (lambda v: v >= 3, lambda v: f"{int(v)} other transactions in the last hour"),
    "secs_since_last": (lambda v: v < 600, lambda v: _gap(v)),
    "amt_to_prev_balance": (lambda v: v >= 0.5, lambda v: f"The amount is {v:.0%} of your balance before this payment"),
    "hour_bucket_share": (lambda v: v < 0.1, lambda v: f"Only {v:.0%} of your earlier transactions happened at this time of day"),
}
FALLBACK = "This transaction is unusual compared with your normal behaviour"
# features that say the same thing: show only the strongest one of each group
GROUPS = {"amount_ratio_cat": "amount", "amount_z_user": "amount", "txn_10m": "velocity", "txn_1h": "velocity"}


def top_reasons(shap_row, row: pd.Series, feature_names, k: int = 3) -> list[str]:
    """Up to k reasons, strongest first, for one transaction."""
    reasons, used = [], set()
    for i in np.argsort(-np.asarray(shap_row)):
        if shap_row[i] <= 0 or len(reasons) == k:
            break
        name = feature_names[i]
        group = GROUPS.get(name, name)
        if name not in TEMPLATES or group in used:
            continue
        value = row[name]
        if pd.isna(value):
            continue
        ok, sentence = TEMPLATES[name]
        if ok(value):
            reasons.append(sentence(value))
            used.add(group)
    return reasons
