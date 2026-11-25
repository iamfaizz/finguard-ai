# Behavioral dataset results (CP-7)

**Setup.** synthetic_transactions_behavioral.csv (23,890 rows, 120 users). Features from src/features.py, first 20 transactions per user dropped. Time-based split: train 12,894 rows / 98 frauds (0.760%), validation 4,298 / 36 (0.838%), test 4,298 / 29 (0.675%, 2026-07-31 to 2026-10-31). Thresholds chosen on validation (missed fraud costs 5x a false alarm). Do-nothing PR-AUC on test = 0.0067.

| Model | PR-AUC | Precision | Recall | Missed | False alarms | Cost |
|---|---|---|---|---|---|---|
| Rule: amount z-score > 3 | n/a | 0.037 | 0.241 | 22 | 181 | 291 |
| Logistic Regression | 0.159 | 0.246 | 0.586 | 12 | 52 | 112 |
| XGBoost | 0.248 | 0.304 | 0.724 | 8 | 48 | 88 |

1. **Ordering.** XGBoost has the highest PR-AUC (about 37x the base rate) and the lowest cost, ahead of Logistic Regression and the rule. The test window has only 29 frauds (recall 21/29 = 72%, roughly 55-88% interval), so the ordering is suggestive, not statistically established.
2. **Patterns detected** (XGBoost, flagged share of all injected events): new_device 1.00, new_merchant_high_amount 1.00, odd_hour 1.00 (no labelled examples in test), amount_anomaly 0.80, velocity 0.80, new_city 0.50, cash_out 0.67. Recall on labelled fraud: new_device 1.00, new_merchant_high_amount 1.00, amount_anomaly 0.75, new_city 0.75, cash_out 0.67, velocity 0.64. Early rows of a velocity burst have no earlier transactions in the window and cannot be detected.
3. **Label noise caps precision.** About 41% of injected events carry a normal label and look identical to labelled fraud. The model flags 83% of unlabelled injected events versus 72% of labelled fraud. Of the 48 false alarms, about 25 are unlabelled injected anomalies, 11 are hard negatives and only about 12 are ordinary transactions. Counting the 25 as fraud would lift precision from 0.30 to about 0.67.
4. **Hard negatives are indistinguishable.** 11 of 12 hard negatives were flagged. In the data they have a higher amount ratio than real amount anomalies (12.7 vs 6.3) and no other distinguishing signal; most are exactly 15,000.00 (a generator artifact). No model can separate them without a feature such as recurrence, which the generator does not provide.
5. **Feature importance** (top): is_new_device 0.134, amount_ratio_cat 0.118, secs_since_last 0.115, is_new_city 0.111, txn_10m 0.105, hour_bucket_share 0.084.
6. **Limitations.** Synthetic data, 29 test frauds, one time split, noisy labels. Scores are far below PaySim (PR-AUC 0.997) because PaySim fraud is a single trivial pattern. These scores reflect the data's label noise and size as much as model quality.
