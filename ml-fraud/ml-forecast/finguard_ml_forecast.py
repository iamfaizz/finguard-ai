#!/usr/bin/env python3
"""FinGuard AI - Role C single-file implementation.

Modules: synthetic UPI data generation, rule-based categorization, 30-day spending
forecasting with Prophet/ETS/SARIMA optional models and fallbacks, rolling-origin
metrics, deterministic savings goal planner, and optional FastAPI endpoints.

Quick start:
  pip install pandas numpy
  python finguard_ml_forecast.py demo
Optional:
  pip install prophet statsmodels fastapi uvicorn
  python finguard_ml_forecast.py serve

This is a project/demo baseline, not a banking-grade model. Synthetic fraud labels
are for experimentation only; do not use the generated data to make real decisions.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import re
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

VERSION = "0.2.0-role-c"
CATEGORIES = ["Food", "Groceries", "Transport", "Shopping", "Bills and Utilities", "Rent",
              "Entertainment", "Health", "Education", "Travel", "Transfers", "Investments"]
DISCRETIONARY = {"Food", "Shopping", "Entertainment"}
LOW_HISTORY_DAYS = 60
FORECAST_HORIZON = 30

MERCHANTS = {
    "Food": ["Zomato", "Swiggy", "Dominos", "McDonalds", "Cafe Coffee Day", "Local Restaurant", "Street Food"],
    "Groceries": ["DMart", "BigBasket", "Blinkit", "Zepto", "Local Kirana", "Reliance Fresh"],
    "Transport": ["Uber", "Ola", "Rapido", "Indian Oil", "Metro", "Bus Ticket"],
    "Shopping": ["Amazon", "Flipkart", "Myntra", "Ajio", "Croma", "Local Clothing Store"],
    "Bills and Utilities": ["Electricity Board", "Jio", "Airtel", "Water Bill", "Broadband"],
    "Rent": ["House Rent", "PG Rent", "Landlord"],
    "Entertainment": ["Netflix", "Spotify", "BookMyShow", "Steam", "Prime Video"],
    "Health": ["Apollo Pharmacy", "Local Pharmacy", "Clinic", "Hospital"],
    "Education": ["College Fees", "Udemy", "Book Store", "Coaching Institute"],
    "Travel": ["IRCTC", "MakeMyTrip", "IndiGo", "Hotel Booking"],
    "Transfers": ["UPI Transfer", "Friend", "Family", "NEFT Transfer"],
    "Investments": ["Zerodha", "Groww", "Mutual Fund", "SIP"]
}
KEYWORDS = {
    "Food": ["zomato", "swiggy", "dominos", "mcdonald", "restaurant", "cafe", "food", "pizza", "burger", "eat"],
    "Groceries": ["dmart", "bigbasket", "blinkit", "zepto", "kirana", "grocery", "supermarket", "reliance fresh"],
    "Transport": ["uber", "ola", "rapido", "metro", "bus", "fuel", "petrol", "diesel", "cab", "parking"],
    "Shopping": ["amazon", "flipkart", "myntra", "ajio", "croma", "shopping", "clothing", "electronics"],
    "Bills and Utilities": ["electricity", "water bill", "jio", "airtel", "recharge", "broadband", "wifi", "utility"],
    "Rent": ["rent", "landlord", "pg rent", "lease"],
    "Entertainment": ["netflix", "spotify", "bookmyshow", "cinema", "movie", "steam", "prime video", "game"],
    "Health": ["pharmacy", "apollo pharmacy", "medical", "hospital", "clinic", "medicine", "health"],
    "Education": ["college", "university", "udemy", "coaching", "tuition", "book store", "education", "fees"],
    "Travel": ["irctc", "makemytrip", "indigo", "hotel", "flight", "travel", "railway"],
    "Transfers": ["upi transfer", "transfer", "neft", "imps", "sent to", "received from", "friend", "family"],
    "Investments": ["zerodha", "groww", "mutual fund", "sip", "investment", "stocks"]
}

# ----------------------------- Data generator -----------------------------
def generate_synthetic_transactions(n_users: int = 20, months: int = 18, seed: int = 42,
                                   fraud_rate: float = 0.0075, start_date: str = "2025-01-01") -> pd.DataFrame:
    """Generate deterministic, persona-based Indian UPI-like transactions and fraud labels."""
    if n_users < 1 or months < 12: raise ValueError("Use at least 1 user and 12 months of history")
    if not 0.005 <= fraud_rate <= 0.01: raise ValueError("fraud_rate must be between 0.5% and 1%")
    rng = np.random.default_rng(seed); py_rng = random.Random(seed)
    start = pd.Timestamp(start_date); end = start + pd.DateOffset(months=months) - pd.Timedelta(days=1)
    days = pd.date_range(start, end, freq="D")
    rows=[]; tx_id=1
    personas=["student", "salaried", "freelancer", "family"]
    incomes={"student":15000,"salaried":55000,"freelancer":42000,"family":80000}
    rent={"student":6500,"salaried":14000,"freelancer":10000,"family":18000}
    daytime={p: True for p in personas}
    user_meta={}
    for u in range(n_users):
        uid=f"user_{u+1:04d}"; persona=personas[u % len(personas)]
        user_meta[uid]={"persona":persona,"income":incomes[persona],"rent":rent[persona],"daytime":daytime[persona]}
        usual_location=f"city_{u%6}"; usual_device=f"device_{u%8}"
        for d in days:
            # salary/earnings near month start; freelancers have irregular credits
            if d.day in (1,2) and persona != "freelancer":
                amt=max(1000,rng.normal(incomes[persona], incomes[persona]*.06))
                rows.append(_row(tx_id,uid,d,"Transfers","Salary Credit",amt,"credit",False,"",usual_device,usual_location)); tx_id+=1
            elif persona=="freelancer" and rng.random()<.045:
                amt=max(1000,rng.normal(incomes[persona], incomes[persona]*.25))
                rows.append(_row(tx_id,uid,d,"Transfers","Client Payment",amt,"credit",False,"",usual_device,usual_location)); tx_id+=1
            if d.day==5:
                rows.append(_row(tx_id,uid,d,"Rent",py_rng.choice(MERCHANTS["Rent"]),rent[persona],"debit",False,"",usual_device,usual_location)); tx_id+=1
            if d.day in (10,25):
                rows.append(_row(tx_id,uid,d,"Bills and Utilities",py_rng.choice(MERCHANTS["Bills and Utilities"]),rng.uniform(450,2200),"debit",False,"",usual_device,usual_location)); tx_id+=1
            # Weekend and festival spending uplift; month-end slight dip.
            n=int(rng.poisson(1.5 if d.weekday()<5 else 2.4))
            if d.month in (10,11): n+=int(rng.poisson(.8))
            if d.day>=27: n=max(0,n-1)
            cats=["Food","Groceries","Transport","Shopping","Entertainment","Health","Education","Travel","Transfers","Investments"]
            probs=[.27,.16,.14,.10,.08,.05,.05,.04,.07,.04]
            for _ in range(n):
                cat=str(rng.choice(cats,p=probs)); merchant=py_rng.choice(MERCHANTS[cat])
                base={"Food":260,"Groceries":600,"Transport":180,"Shopping":1100,"Entertainment":500,"Health":700,"Education":900,"Travel":1800,"Transfers":700,"Investments":1500}[cat]
                amount=max(20,float(rng.lognormal(np.log(base),.55)))
                hour=int(rng.choice([8,9,12,13,17,18,19,20,21],p=[.08,.08,.12,.10,.10,.13,.15,.13,.11]))
                minute=int(rng.integers(0,60)); ts=pd.Timestamp(d)+pd.Timedelta(hours=hour,minutes=minute)
                rows.append(_row(tx_id,uid,ts,cat,merchant,amount,"debit",False,"",usual_device,usual_location)); tx_id+=1
        # Hard-negative legitimate high purchases, including rent and festival shopping.
        if rng.random()<.7:
            d=py_rng.choice(days); rows.append(_row(tx_id,uid,pd.Timestamp(d)+pd.Timedelta(hours=14),"Shopping","Festival Phone Purchase",rng.uniform(18000,65000),"debit",False,"hard_negative_large_purchase",usual_device,usual_location)); tx_id+=1
    df=pd.DataFrame(rows)
    # Inject six fraud patterns. Fraud rate is controlled approximately by selecting target count.
    n_fraud=max(1,round(len(df)*fraud_rate)); eligible=df.index[df.type.eq("debit")].to_list()
    if len(eligible)<n_fraud: n_fraud=len(eligible)
    chosen=rng.choice(eligible,size=n_fraud,replace=False)
    patterns=["amount_spike","odd_hour","new_merchant_high_value","velocity_burst","new_device_location","mule_flow"]
    for i,idx in enumerate(chosen):
        pattern=patterns[i%len(patterns)]; df.loc[idx,"is_fraud"]=True; df.loc[idx,"fraud_pattern"]=pattern
        if pattern=="amount_spike": df.loc[idx,"amount"]*=rng.uniform(5.2,9.0)
        elif pattern=="odd_hour": df.loc[idx,"timestamp"]=pd.Timestamp(df.loc[idx,"timestamp"]).normalize()+pd.Timedelta(hours=int(rng.integers(1,4)))
        elif pattern=="new_merchant_high_value": df.loc[idx,"merchant"]="Unknown Merchant"; df.loc[idx,"amount"]*=rng.uniform(4,8)
        elif pattern=="velocity_burst": df.loc[idx,"timestamp"]=pd.Timestamp(df.loc[idx,"timestamp"])+pd.Timedelta(minutes=int(rng.integers(0,5)))
        elif pattern=="new_device_location": df.loc[idx,"device_id"]="new_device"; df.loc[idx,"location"]="new_location"
        elif pattern=="mule_flow": df.loc[idx,"category"]="Transfers"; df.loc[idx,"amount"]*=rng.uniform(3,7)
    df=df.sort_values(["user_id","timestamp","transaction_id"]).reset_index(drop=True)
    df["timestamp"]=pd.to_datetime(df.timestamp)
    # Deterministic output order/schema.
    return df

def generator_stats(df):
    return {"rows": int(len(df)), "users": int(df.user_id.nunique()),
            "fraud_rate": float(df.is_fraud.mean()),
            "fraud_by_pattern": df.loc[df.is_fraud, "fraud_pattern"].value_counts().to_dict(),
            "history_days_per_user": df.groupby("user_id").timestamp.apply(lambda x: int((x.max()-x.min()).days)).to_dict(),
            "categories": sorted(df.category.dropna().unique().tolist())}

def validate_transactions(df):
    required = {"transaction_id", "user_id", "timestamp", "amount", "category", "type", "is_fraud", "fraud_pattern"}
    errors=[]; missing=required-set(df.columns)
    if missing: errors.append(f"Missing columns: {sorted(missing)}")
    else:
        if df[list(required)].isna().any().any(): errors.append("Required fields contain nulls")
        if (df.amount <= 0).any(): errors.append("Amounts must be positive")
        if not set(df.category.dropna()).issubset(set(CATEGORIES)): errors.append("Unknown category")
        if not all(g.timestamp.is_monotonic_increasing for _,g in df.groupby("user_id")): errors.append("Transactions not sorted within user")
        if (df.groupby("user_id").is_fraud.mean() > .05).any(): errors.append("A user exceeds 5% fraud rate")
    return {"valid": not errors, "errors": errors}

def _row(tx_id, uid, timestamp, category, merchant, amount, tx_type, fraud, pattern, device, location):
    ts=pd.Timestamp(timestamp); narration=f"UPI/{str(merchant).upper().replace(' ','_')}/{tx_id:08d}@okaxis"
    return {"transaction_id":f"TX{tx_id:09d}","user_id":uid,"timestamp":ts,"date":ts.date().isoformat(),"hour":ts.hour,
            "merchant":merchant,"narration":narration,"category":category,"amount":round(float(amount),2),"type":tx_type,
            "is_fraud":bool(fraud),"fraud_pattern":pattern,"device_id":device,"location":location}

# ----------------------------- Categorizer -----------------------------
def categorize_transaction(narration: str, merchant: str = "", confidence_threshold: float=.60) -> dict:
    text=re.sub(r"[^a-z0-9 ]"," ",f"{narration} {merchant}".lower())
    scores=[]
    for category,words in KEYWORDS.items():
        hits=[w for w in words if w in text]
        if hits: scores.append((len(hits),max(map(len,hits)),category,hits[0]))
    if not scores: return {"category":"Uncategorized","confidence":0.0,"method":"fallback","matched_keyword":None}
    _,_,cat,kw=max(scores)
    # Transparent rule baseline confidence; ambiguous multiple-category matches are reduced.
    confidence=.85 if len(scores)==1 else .70
    if confidence < confidence_threshold: cat="Uncategorized"
    return {"category":cat,"confidence":confidence,"method":"keyword_rule","matched_keyword":kw}

def categorize_batch(records: Iterable[dict], confidence_threshold: float=.60) -> list[dict]:
    result=[]
    for r in records:
        c=categorize_transaction(str(r.get("narration",r.get("description",""))),str(r.get("merchant","")),confidence_threshold)
        result.append({**r,**c})
    return result

# ----------------------------- Forecasting -----------------------------
def _daily_series(transactions: pd.DataFrame, category: str|None=None, tx_type: str="debit") -> pd.Series:
    df=transactions.copy()
    if "type" in df: df=df[df.type.astype(str).str.lower()==tx_type]
    if category is not None and "category" in df: df=df[df.category==category]
    if df.empty: return pd.Series(dtype=float)
    date_col="timestamp" if "timestamp" in df else "date"
    df[date_col]=pd.to_datetime(df[date_col],errors="coerce")
    df=df.dropna(subset=[date_col]); df[date_col]=df[date_col].dt.normalize()
    s=df.groupby(date_col).amount.sum().sort_index()
    return s.asfreq("D",fill_value=0).astype(float)

def _metric_mae(actual, pred): return float(np.mean(np.abs(np.asarray(actual)-np.asarray(pred))))
def _metric_smape(actual,pred):
    a=np.asarray(actual,dtype=float); p=np.asarray(pred,dtype=float); den=np.abs(a)+np.abs(p)
    vals=np.divide(200*np.abs(a-p),den,out=np.zeros_like(den),where=den!=0)
    return float(np.mean(vals))

def _forecast_model(y: pd.Series, horizon: int, method: str) -> np.ndarray:
    vals=y.astype(float).to_numpy(); avg=float(np.mean(vals[-min(30,len(vals)):])) if len(vals) else 0.
    if method=="naive": return np.resize(vals[-min(30,len(vals)):],horizon) if len(vals) else np.zeros(horizon)
    if method=="moving_average": return np.repeat(avg,horizon)
    if method=="category_average": return np.repeat(float(np.mean(vals)) if len(vals) else 0.,horizon)
    if method=="ets":
        try:
            from statsmodels.tsa.holtwinters import ExponentialSmoothing
            seasonal="add" if len(vals)>=28 else None
            m=ExponentialSmoothing(y,trend="add" if len(vals)>=14 else None,seasonal=seasonal,seasonal_periods=7 if seasonal else None).fit()
            return np.maximum(0,np.asarray(m.forecast(horizon)))
        except Exception: return np.repeat(avg,horizon)
    if method=="sarima":
        try:
            from statsmodels.tsa.statespace.sarimax import SARIMAX
            seasonal=(1,0,0,7) if len(vals)>=60 else (0,0,0,0)
            m=SARIMAX(y,order=(1,0,0),seasonal_order=seasonal,enforce_stationarity=False,enforce_invertibility=False).fit(disp=False)
            return np.maximum(0,np.asarray(m.forecast(horizon)))
        except Exception: return np.repeat(avg,horizon)
    if method=="prophet":
        try:
            from prophet import Prophet
            frame=pd.DataFrame({"ds":y.index,"y":y.values})
            m=Prophet(weekly_seasonality=True,yearly_seasonality=len(y)>=365,daily_seasonality=False)
            m.add_seasonality(name="monthly", period=30.5, fourier_order=5)
            try: m.add_country_holidays(country_name="IN")
            except Exception: pass
            m.fit(frame); future=m.make_future_dataframe(periods=horizon,freq="D")
            return np.maximum(0,np.asarray(m.predict(future).tail(horizon).yhat))
        except Exception: return np.repeat(avg,horizon)
    raise ValueError(f"Unknown forecast model {method}")

def forecast_spending(transactions: pd.DataFrame, horizon: int=30) -> dict:
    if horizon<1: raise ValueError("horizon must be positive")
    if not {"amount","category"}.issubset(transactions.columns) or not ("date" in transactions or "timestamp" in transactions):
        raise ValueError("transactions require amount, category, and date or timestamp columns")
    if transactions.empty: raise ValueError("transactions are empty")
    if transactions.amount.isna().any() or (transactions.amount<0).any(): raise ValueError("amount must be non-negative and non-null")
    y=_daily_series(transactions); history=len(y); low=history<LOW_HISTORY_DAYS
    method="category_average" if low else "prophet"
    daily=_forecast_model(y,horizon,method)
    if not low:
        try:
            from prophet import Prophet  # noqa: F401
            model_status="Prophet attempted; fallback is used if fitting fails."
        except ImportError:
            method="moving_average_fallback (Prophet unavailable)"
            model_status="Prophet is not installed; moving-average fallback used."
    # Guide asks per-category estimates; sparse categories are forecast as a share of total.
    cats=transactions.category.dropna().unique().tolist(); cat_result={}
    hist_total=float(y.sum()) or 1.
    for cat in cats:
        cy=_daily_series(transactions,category=cat)
        share=float(cy.sum()/hist_total)
        cat_result[str(cat)]={"daily_forecast":np.round(daily*share,2).tolist(),"next_30_days_estimate":round(float(np.sum(daily*share)),2),"historical_share":round(share,4)}
    last=y.index[-1] if len(y) else pd.Timestamp.today().normalize()
    dates=pd.date_range(last+pd.Timedelta(days=1),periods=horizon,freq="D")
    return {"version":VERSION,"forecast_days":horizon,"history_days":history,"low_confidence":low,"method":method,
            "dates":[d.strftime("%Y-%m-%d") for d in dates],"daily_predicted_spending":np.round(np.maximum(0,daily),2).tolist(),
            "total_predicted_spending":round(float(np.sum(np.maximum(0,daily))),2),"category_forecasts":cat_result,
            "confidence_note":"Under 60 days: category-average fallback; low confidence." if low else model_status}

def rolling_origin_cv(transactions: pd.DataFrame, methods=("naive","moving_average","ets","sarima","prophet"),horizon=30,min_train_days=60,step=30):
    y=_daily_series(transactions); output={}
    for method in methods:
        scores=[]
        for cutoff in range(min_train_days,len(y)-horizon+1,step):
            train=y.iloc[:cutoff]; test=y.iloc[cutoff:cutoff+horizon]
            try: pred=_forecast_model(train,horizon,method)
            except Exception: continue
            scores.append({"mae":_metric_mae(test,pred),"smape":_metric_smape(test,pred)})
        output[method]={"folds":len(scores),"mae":round(float(np.mean([s["mae"] for s in scores])),2) if scores else None,
                       "smape":round(float(np.mean([s["smape"] for s in scores])),2) if scores else None}
    return output

# ----------------------------- Goal Planner -----------------------------
def plan_goal(target_amount: float,saved_amount: float,months_left: int,forecast_income: float,forecast_spending: float,
              category_forecasts: dict[str,float]|None=None,max_cut_fraction: float=.30) -> dict:
    vals=[target_amount,saved_amount,forecast_income,forecast_spending,max_cut_fraction]
    if any(not math.isfinite(float(v)) or float(v)<0 for v in vals): raise ValueError("Inputs must be finite and non-negative")
    if months_left<=0: raise ValueError("months_left must be positive")
    if max_cut_fraction>.30: raise ValueError("Cuts are capped at 30% per category")
    remaining=max(0.,target_amount-saved_amount); required=remaining/months_left
    surplus=forecast_income-forecast_spending; gap=max(0.,required-surplus)
    eligible={c:max(0.,float(v)) for c,v in (category_forecasts or {}).items() if c in DISCRETIONARY}
    total_eligible=sum(eligible.values()); cuts={}
    # Proportional cuts across eligible categories, each bounded by 30%; repeat to distribute rounding residual.
    if gap>0 and total_eligible>0:
        proposed=min(gap,total_eligible*max_cut_fraction)
        for c,amt in eligible.items():
            cuts[c]=min(amt*max_cut_fraction,proposed*amt/total_eligible)
    cuts={k:round(v,2) for k,v in cuts.items() if v>0}; totalcuts=round(sum(cuts.values()),2)
    adjusted=surplus+totalcuts; feasible=adjusted+1e-9>=required
    return {"goal":{"target_amount":round(target_amount,2),"saved_amount":round(saved_amount,2),"remaining_amount":round(remaining,2),"months_left":months_left,"required_monthly_savings":round(required,2)},
            "forecast":{"income":round(forecast_income,2),"spending":round(forecast_spending,2),"surplus":round(surplus,2),"adjusted_surplus":round(adjusted,2)},
            "recommended_cuts":cuts,"total_recommended_cuts":totalcuts,"monthly_gap_after_cuts":round(max(0.,required-adjusted),2),
            "status":"feasible" if feasible else "infeasible","infeasible":not feasible,
            "message":"Goal appears achievable using forecast surplus and suggested cuts." if feasible else "Goal is infeasible under current forecast and 30% category cut limits; consider a longer deadline or lower target."}

# ----------------------------- API (optional dependency) -----------------------------
def create_app():
    try: from fastapi import FastAPI, HTTPException
    except ImportError as e: raise RuntimeError("Install fastapi and uvicorn to serve the API") from e
    app=FastAPI(title="FinGuard ML Forecast",version=VERSION)
    @app.post("/categorize")
    def api_categorize(payload: dict):
        rows=payload.get("transactions")
        if rows is None: return categorize_transaction(payload.get("narration",""),payload.get("merchant",""))
        return {"results":categorize_batch(rows)}
    @app.post("/forecast")
    def api_forecast(payload: dict):
        try: return forecast_spending(pd.DataFrame(payload.get("transactions",[])),int(payload.get("horizon",30)))
        except Exception as e: raise HTTPException(status_code=400,detail=str(e))
    @app.post("/goal-plan")
    def api_goal(payload: dict):
        try: return plan_goal(**payload)
        except Exception as e: raise HTTPException(status_code=400,detail=str(e))
    return app

# ----------------------------- Demo / CLI -----------------------------
def generator_stats(tx):
    return {"rows":len(tx),"users":int(tx.user_id.nunique()),"fraud_rate":float(tx.is_fraud.mean()),
            "fraud_by_pattern":tx.loc[tx.is_fraud,"fraud_pattern"].value_counts().to_dict(),
            "history_days_per_user":tx.groupby("user_id").timestamp.apply(lambda x:int((x.max()-x.min()).days)).to_dict(),
            "categories":sorted(tx.category.dropna().unique().tolist())}

def validate_transactions(tx):
    required={"transaction_id","user_id","timestamp","amount","category","type","is_fraud","fraud_pattern"}
    errors=[]; missing=required-set(tx.columns)
    if missing: errors.append(f"Missing columns: {sorted(missing)}")
    else:
        if tx[list(required)].isna().any().any(): errors.append("Required fields contain nulls")
        if (tx.amount<=0).any(): errors.append("Amounts must be positive")
        if not set(tx.category.dropna()).issubset(set(CATEGORIES)): errors.append("Invalid categories")
        if not all(g.timestamp.is_monotonic_increasing for _,g in tx.groupby("user_id")): errors.append("Not sorted within user")
        if (tx.groupby("user_id").is_fraud.mean()>.05).any(): errors.append("User fraud rate exceeds 5%")
    return {"valid":not errors,"errors":errors}

def categorizer_smoke_test():
    cases=[
      ("UPI/ZOMATO/4821@okaxis","", "Food"),("SWIGGY ORDER","Swiggy","Food"),("DOMINOS PIZZA","Dominos","Food"),
      ("DMART BILL","DMart","Groceries"),("BIGBASKET","BigBasket","Groceries"),("LOCAL KIRANA","Kirana","Groceries"),
      ("UBER TRIP","Uber","Transport"),("OLA CAB","Ola","Transport"),("INDIAN OIL PETROL","Indian Oil","Transport"),
      ("AMAZON PAY","Amazon","Shopping"),("FLIPKART","Flipkart","Shopping"),("MYNTRA","Myntra","Shopping"),
      ("JIO RECHARGE","Jio","Bills and Utilities"),("ELECTRICITY BILL","Electricity Board","Bills and Utilities"),("AIRTEL BROADBAND","Airtel","Bills and Utilities"),
      ("PG RENT","PG Rent","Rent"),("HOUSE RENT","Landlord","Rent"),("LEASE PAYMENT","Lease","Rent"),
      ("NETFLIX","Netflix","Entertainment"),("BOOKMYSHOW","BookMyShow","Entertainment"),("SPOTIFY","Spotify","Entertainment"),
      ("APOLLO PHARMACY","Apollo Pharmacy","Health"),("CLINIC","Clinic","Health"),("MEDICINE","Medicine","Health"),
      ("COLLEGE FEES","College Fees","Education"),("UDEMY COURSE","Udemy","Education"),("COACHING","Coaching Institute","Education"),
      ("IRCTC TICKET","IRCTC","Travel"),("INDIGO FLIGHT","IndiGo","Travel"),("NEFT TRANSFER","NEFT Transfer","Transfers")]
    out=[]; correct=0
    for narration,merchant,expected in cases:
        got=categorize_transaction(narration,merchant)["category"]; ok=got==expected; correct+=int(ok)
        out.append({"narration":narration,"merchant":merchant,"expected":expected,"predicted":got,"correct":ok})
    return {"n":len(cases),"correct":correct,"accuracy":correct/len(cases),"failures":[x for x in out if not x["correct"]],"cases":out}

def demo(outdir="finguard_demo",seed=42):
    p=Path(outdir); p.mkdir(parents=True,exist_ok=True)
    tx=generate_synthetic_transactions(n_users=4,months=18,seed=seed)
    tx.to_csv(p/"synthetic_transactions.csv",index=False)
    try: tx.to_parquet(p/"synthetic_transactions.parquet",index=False); parquet_status="success"
    except Exception as e: parquet_status=f"unavailable: {type(e).__name__}"
    stats=generator_stats(tx); validation=validate_transactions(tx)
    (p/"generator_stats.json").write_text(json.dumps(stats,indent=2),encoding="utf-8")
    (p/"validation.json").write_text(json.dumps(validation,indent=2),encoding="utf-8")
    user=tx[tx.user_id=="user_0001"].copy(); forecast=forecast_spending(user)
    (p/"forecast_result.json").write_text(json.dumps(forecast,indent=2),encoding="utf-8")
    cv=rolling_origin_cv(user); (p/"cv_results.json").write_text(json.dumps(cv,indent=2),encoding="utf-8")
    pd.DataFrame([{"model":m,"folds":v["folds"],"MAE":v["mae"],"sMAPE":v["smape"]} for m,v in cv.items()]).to_csv(p/"model_comparison.csv",index=False)
    goal=plan_goal(50000,10000,6,55000,forecast["total_predicted_spending"],{k:v["next_30_days_estimate"] for k,v in forecast["category_forecasts"].items()})
    (p/"goal_plan.json").write_text(json.dumps(goal,indent=2),encoding="utf-8")
    try:
        import matplotlib.pyplot as plt
        plt.figure(figsize=(9,4)); plt.bar([r["model"] for r in [{"model":m,"mae":v["mae"]} for m,v in cv.items()]], [v["mae"] or 0 for v in cv.values()]); plt.ylabel("Rolling-origin MAE (INR)"); plt.title("Forecast baseline comparison"); plt.tight_layout(); plt.savefig(p/"model_comparison_mae.png",dpi=150); plt.close()
    except Exception: pass
    summary={"generator_stats":stats,"validation":validation,"forecast_total":forecast["total_predicted_spending"],"goal_status":goal["status"],"parquet":parquet_status,"forecast_note":forecast["confidence_note"]}
    (p/"demo_summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(json.dumps(summary,indent=2)); return summary

def self_test():
    # deterministic generation, categorization, forecast, planner caps and feasibility
    a=generate_synthetic_transactions(n_users=2,months=12,seed=7); b=generate_synthetic_transactions(n_users=2,months=12,seed=7)
    assert a.equals(b),"Seed reproducibility failed"
    assert set(a.category).issubset(set(CATEGORIES)),"Invalid category"
    assert set(a.category)==set(CATEGORIES),"Expected all 12 categories"
    assert .005 <= a.is_fraud.mean() <= .01,"Fraud rate outside guide range"
    assert validate_transactions(a)["valid"],"Data validation failed"
    assert set(a.loc[a.is_fraud,"fraud_pattern"].dropna())=={"amount_spike","odd_hour","new_merchant_high_value","velocity_burst","new_device_location","mule_flow"},"Fraud pattern missing"
    assert validate_transactions(a)["valid"], "Data validation failed"
    assert set(a.loc[a.is_fraud,"fraud_pattern"].dropna())=={"amount_spike","odd_hour","new_merchant_high_value","velocity_burst","new_device_location","mule_flow"}, "Fraud patterns missing"
    assert categorize_transaction("UPI/ZOMATO/123") ["category"]=="Food"
    assert categorize_transaction("UPI/UNKNOWN/123")["category"]=="Uncategorized"
    low=forecast_spending(a[a.user_id=="user_0001"].head(40)); assert low["low_confidence"]
    full=forecast_spending(a[a.user_id=="user_0001"]); assert full["forecast_days"]==30 and not full["low_confidence"]
    g=plan_goal(50000,0,6,50000,40000,{"Food":10000,"Shopping":5000,"Entertainment":2000})
    assert abs(g["goal"]["required_monthly_savings"]-8333.3333)<.01
    for cat,cut in g["recommended_cuts"].items(): assert cut<=.30*{"Food":10000,"Shopping":5000,"Entertainment":2000}[cat]+.01
    impossible=plan_goal(100000,0,1,1000,5000,{"Food":100,"Shopping":100,"Entertainment":100})
    assert impossible["infeasible"]
    print("Self-test PASSED (6 checks)")

def main():
    parser=argparse.ArgumentParser(description="FinGuard AI Role C: generator, categorizer, forecast, goal planner")
    parser.add_argument("command",choices=["demo","generate","serve","test"],nargs="?",default="demo")
    parser.add_argument("--out",default="finguard_demo"); parser.add_argument("--seed",type=int,default=42)
    args=parser.parse_args()
    if args.command=="demo": demo(args.out,args.seed)
    elif args.command=="generate":
        df=generate_synthetic_transactions(seed=args.seed); Path(args.out).mkdir(parents=True,exist_ok=True); df.to_csv(Path(args.out)/"synthetic_transactions.csv",index=False); print(f"Wrote {len(df)} rows")
    elif args.command=="test": self_test()
    elif args.command=="serve":
        try: import uvicorn
        except ImportError: raise SystemExit("Install fastapi and uvicorn: pip install fastapi uvicorn")
        uvicorn.run(create_app(),host="0.0.0.0",port=8000)

if __name__=="__main__": main()
