import json
from contextlib import asynccontextmanager
from pathlib import Path

import numpy as np
import pandas as pd
import shap
import xgboost as xgb
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from src.explain import top_reasons


BASE_DIR = Path(__file__).resolve().parent.parent
ARTIFACT_DIR = BASE_DIR / "artifacts"
MODEL_PATH = ARTIFACT_DIR / "fraud_v2.json"
META_PATH = ARTIFACT_DIR / "fraud_v2_meta.json"

MEDIUM_THRESHOLD = 0.45


class FraudInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    n_prior: int = Field(ge=0)
    is_debit: int = Field(ge=0, le=1)
    hour: int = Field(ge=0, le=23)
    is_night: int = Field(ge=0, le=1)
    day_of_week: int = Field(ge=0, le=6)
    amount: float = Field(gt=0, allow_inf_nan=False)
    amount_z_user: float = Field(allow_inf_nan=False)
    amount_ratio_cat: float = Field(allow_inf_nan=False)
    amt_to_prev_balance: float = Field(allow_inf_nan=False)
    is_new_merchant: int = Field(ge=0, le=1)
    is_new_device: int = Field(ge=0, le=1)
    is_new_city: int = Field(ge=0, le=1)
    hour_bucket_share: float = Field(allow_inf_nan=False)
    txn_10m: int = Field(ge=0)
    txn_1h: int = Field(ge=0)
    txn_24h: int = Field(ge=0)
    secs_since_last: float = Field(ge=0, allow_inf_nan=False)


class FraudResponse(BaseModel):
    fraud_probability: float
    risk_level: str
    reasons: list[str]
    model_version: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not MODEL_PATH.exists() or not META_PATH.exists():
        raise RuntimeError("Fraud model or metadata file is missing")

    with open(META_PATH, "r") as file:
        metadata = json.load(file)

    app.state.features = metadata["features"]
    app.state.high_threshold = float(metadata["threshold"])
    app.state.model_version = metadata["model_version"]

    if len(app.state.features) != 17:
        raise RuntimeError("Expected exactly 17 model features")

    app.state.model = xgb.XGBClassifier()
    app.state.model.load_model(str(MODEL_PATH))

    app.state.explainer = shap.TreeExplainer(app.state.model)

    yield


app = FastAPI(
    title="FinGuard AI - Fraud Detection API",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "ml-fraud",
        "model_version": app.state.model_version,
    }


@app.post("/score", response_model=FraudResponse)
def score_transaction(payload: FraudInput):
    features = app.state.features

    row = payload.model_dump()
    X = pd.DataFrame(
        [[row[name] for name in features]],
        columns=features,
    )

    try:
        score = float(app.state.model.predict_proba(X)[0, 1])

        shap_values = app.state.explainer.shap_values(X)
        shap_values = np.asarray(shap_values)

        if shap_values.ndim == 3:
            shap_values = shap_values[0, :, 1]

        shap_row = shap_values.reshape(-1)

        reasons = top_reasons(
            shap_row,
            pd.Series(row),
            features,
            k=3,
        )

        if not reasons:
            reasons = [
                "No individual explanation met the current explanation rules"
            ]

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Fraud scoring failed: {str(exc)}",
        )

    if score >= app.state.high_threshold:
        risk_level = "HIGH"
    elif score >= MEDIUM_THRESHOLD:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"

    return FraudResponse(
        fraud_probability=score,
        risk_level=risk_level,
        reasons=reasons,
        model_version=app.state.model_version,
    )
