from pathlib import Path
import os
import pandas as pd
import pytest

DATA = Path(__file__).resolve().parents[1] / "synthetic" / os.getenv("FINGUARD_DATASET", "synthetic_transactions_behavioral_v3.csv")

# Member C confirmed current dataset taxonomy.
CATEGORIES = {"cash", "entertainment", "food", "grocery", "healthcare", "income", "shopping", "transfer", "travel", "utilities"}


@pytest.fixture(scope="module")
def df():
    return pd.read_csv(DATA)


def test_no_missing_values(df):
    assert not df.drop(columns=["fraud_reason"]).isnull().any().any()


def test_unique_transactions(df):
    assert df["txn_id"].is_unique


def test_positive_amount(df):
    assert (df["amount"] > 0).all()


def test_valid_timestamps(df):
    assert pd.to_datetime(df["timestamp"], errors="coerce").notna().all()


def test_timestamp_order(df):
    dates = pd.to_datetime(df["timestamp"])
    assert dates.groupby(df["user_id"]).apply(
        lambda x: x.is_monotonic_increasing
    ).all()


def test_categories(df):
    assert df["category"].str.lower().str.strip().isin(CATEGORIES).all()


def test_fraud_labels(df):
    assert df["fraud_label"].isin([0, 1]).all()


def test_user_fraud_rate(df):
    assert (df.groupby("user_id")["fraud_label"].mean() <= 0.05).all()

def test_dataset_schema(df):
    import pandera.pandas as pa
    schema = pa.DataFrameSchema({
        'txn_id': pa.Column(str, unique=True),
        'user_id': pa.Column(str),
        'timestamp': pa.Column(str),
        'amount': pa.Column(float, pa.Check.gt(0)),
        'balance': pa.Column(float),
        'fraud_label': pa.Column(int, pa.Check.isin([0, 1])),
        'fraud_reason': pa.Column(str, nullable=True),
    })
    schema.validate(df, lazy=True)
