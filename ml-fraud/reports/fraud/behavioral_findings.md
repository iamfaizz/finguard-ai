# Behavioral dataset v2 results (CP-7)

**Setup.** synthetic_transactions_behavioral_v2.csv (23,890 rows, 120 users). Same rows and labels as v1; only the 150 velocity timestamps changed (bursts of 2-4 transactions, random 5-90 second gaps). Features from src/features.py (velocity counts include earlier transactions with the same timestamp), first 20 transactions per user dropped. Time-based split: train 12,894 rows / 98 frauds (0.760%), validation 4,298 / 36 (0.838%), test 4,298 / 29 (0.675%, 2026-07-31 to 2026-10-31). Thresholds chosen on validation (a missed fraud costs 5x a false alarm). Do-nothing PR-AUC on test = 0.0067. Results on dataset v1 are kept in reports/fraud/data_v1/.

| Model | PR-AUC | Precision | Recall | Missed | False alarms | Cost |
|---|---:|---:|---:|---:|---:|---:|
| Rule: amount z-score > 3 | n/a | 0.037 | 0.241 | 22 | 181 | 291 |
| Logistic Regression | 0.187 | 0.242 | 0.517 | 14 | 47 | 117 |
| XGBoost | 0.265 | 0.244 | 0.655 | 10 | 59 | 109 |

1. **Ordering.** XGBoost has the highest PR-AUC (0.265, about 39x the base rate) ahead of Logistic Regression (0.187, about 28x) and the rule. Its cost is lower (109 vs 117), but the gap is under two missed frauds; with 29 test frauds, PR-AUC is the comparison to trust.
2. **Effect of the data change (v1 to v2).** XGBoost PR-AUC 0.283 to 0.265, frauds caught 20 to 19, Logistic Regression PR-AUC 0.196 to 0.187, velocity recall on labelled fraud 0.50 to 0.43. A one-fraud difference on a 29-fraud test set: the model did not rely heavily on the fixed 120-second spacing of v1.
3. **Patterns detected** (XGBoost, flagged share of all injected events / recall on labelled fraud): new_city 1.00 / 1.00, new_device 1.00 / 1.00, new_merchant_high_amount 1.00 / 1.00, odd_hour 1.00 / n.a. (no labelled examples in test), amount_anomaly 0.80 / 0.75, cash_out 0.67 / 0.67 (3 events), velocity 0.67 / 0.43 (6 of 14). The first transaction of a burst has no earlier burst transactions, yet 66% of first rows are labelled fraud, so those cannot be detected from behaviour.
4. **Label noise caps precision.** About 41% of injected events carry a normal label and look identical to labelled fraud. The model flags 93% of unlabelled injected events versus 66% of labelled fraud (19 of 29). Of the 59 false alarms, about 28 are unlabelled injected anomalies, 10 are hard negatives and about 21 are ordinary transactions. Counting the 28 as fraud would lift precision from 0.24 to about 0.60.
5. **Hard negatives are indistinguishable.** 10 of 12 hard negatives were flagged. They have a higher amount ratio than real amount anomalies and no other distinguishing signal; 39 of 47 are exactly 15,000.00 (a generator artifact).
6. **Feature importance** (top): is_new_device 0.137, txn_1h 0.129, is_new_city 0.114, amount_ratio_cat 0.103, secs_since_last 0.090, is_night 0.087, hour_bucket_share 0.075, hour 0.062.
7. **Limitations.** Synthetic data, 29 test frauds, one time split, noisy labels, 79% of balances negative. Scores are far below PaySim (PR-AUC 0.997) because PaySim fraud is a single trivial pattern; they reflect the data's label noise and size as much as model quality.
