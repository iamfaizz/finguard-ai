import numpy as np
import pandas as pd
from src.explain import top_reasons

NAMES = ["amount_ratio_cat", "is_new_device", "is_new_city", "txn_10m", "hour", "amount_z_user"]


def row(**kw):
    base = dict(amount_ratio_cat=1.0, is_new_device=0, is_new_city=0, txn_10m=0, hour=12, amount_z_user=0.0)
    base.update(kw)
    return pd.Series(base)


def test_only_positive_contributions_strongest_first():
    r = row(amount_ratio_cat=6.4, is_new_device=1, is_new_city=1)
    out = top_reasons(np.array([0.9, 1.5, -0.7, 0, 0, 0]), r, NAMES)
    assert out == ["This is the first time you have used this device", "The amount is 6.4x your usual spend in this category"]


def test_never_states_something_untrue():
    r = row(amount_ratio_cat=1.2, is_new_device=0)           # big SHAP, but the facts do not support a reason
    assert top_reasons(np.array([2.0, 3.0, 0, 0, 0, 0]), r, NAMES) == []


def test_limit_k_and_skip_untemplated_and_nan():
    r = row(amount_ratio_cat=5, is_new_device=1, is_new_city=1, txn_10m=4, amount_z_user=np.nan)
    out = top_reasons(np.array([1, 2, 3, 4, 9, 8]), r, NAMES, k=3)   # 'hour' has no template, amount_z_user is NaN
    assert len(out) == 3 and out[0].startswith("4 other transactions")
