# PaySim benchmark findings (CP-5)

**Setup.** Only TRANSFER and CASH_OUT rows. Time-based split: train steps 1-450 (2,626,155 rows, 5,057 frauds, 0.193%), validation 451-600 (100,704 rows, 1,556 frauds, 1.545%), test 601-743 (43,550 rows, 1,600 frauds, 3.674%). Alert thresholds are chosen on the validation set by cost (a missed fraud costs 5 times a false alert). The do-nothing PR-AUC on test equals the fraud rate, 0.037.

| Model | PR-AUC | Precision | Recall | Missed | False alarms | Cost (5xFN + FP) |
|---|---|---|---|---|---|---|
| Rule: isFlaggedFraud | n/a | 1.000 | 0.005 | 1,592 | 0 | 7,960 |
| Rule: amount > 200,000 | n/a | 0.057 | 0.668 | 532 | 17,661 | 20,321 |
| Logistic Regression (A) | 0.711 | 0.688 | 0.802 | 317 | 582 | 2,167 |
| Isolation Forest (A) | 0.502 | 0.607 | 0.436 | 902 | 452 | 4,962 |
| XGBoost (A, deployable features) | 0.9968 | 0.964 | 0.9975 | 4 | 60 | 80 |
| XGBoost (B, adds post-transaction balances) | 1.0000 | 0.993 | 1.000 | 0 | 11 | 11 |

1. **Ordering.** Rules < Isolation Forest (unsupervised) < Logistic Regression < XGBoost. XGBoost (A) costs 80 against 2,167 for Logistic Regression, so it is the model we carry forward.
2. **Simulator rule is useless.** isFlaggedFraud has perfect precision but catches 8 of 1,600 frauds. The amount rule catches 67% but raises 17,661 false alarms (precision 5.7%, barely above the 3.7% base rate).
3. **Leakage.** Adding post-transaction balances (set B) gives PR-AUC 1.0000 after only 13 trees (183 for set A). These columns are not known at authorisation time, so set B is not deployable and is reported only to show how much leakage inflates a score.
4. **Why set A is also very high.** drains_account (0.462) and amt_to_oldbal (0.367) hold 83% of feature importance. Removing hour changes PR-AUC from 0.9968 to 0.9956. Removing hour and both drain features still gives 0.9706, because amount and oldbalanceOrg let the trees rebuild the same comparison. PaySim fraud is essentially "empty the sender's account", so 0.997 reflects the simplicity of the simulation and must not be presented as expected real-world performance.
5. **Limitations.** The fraud rate rises over time (0.19% to 3.7%), which flatters precision on the test set and means the validation-chosen threshold is not perfectly tuned for test. PaySim is synthetic and has no per-user history. The headline model for FinGuard is the one trained on the synthetic UPI data (Phase 3), where per-user behaviour features exist.
