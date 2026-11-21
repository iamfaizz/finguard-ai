# PaySim EDA findings (CP-4)

1. **Class imbalance:** 8,213 frauds in 6,362,620 rows (0.1291%, about 1 in 775). Accuracy is meaningless (always predicting "not fraud" scores 99.87%), so we report PR-AUC, recall at fixed precision and the confusion matrix.
2. **Where fraud occurs:** only TRANSFER (4,097 cases, 0.77%) and CASH_OUT (4,116 cases, 0.18%). CASH_IN, DEBIT and PAYMENT have zero fraud. The benchmark uses only TRANSFER and CASH_OUT (2,770,409 rows, about 0.30% fraud).
3. **Amount alone is weak:** fraud amounts are higher for CASH_OUT but overlap heavily for TRANSFER (see figures/amount_by_fraud.png).
4. **Fraud drains the account:** 97.55% of fraud rows empty the sender's balance, against 23.8% of legitimate rows. newbalanceOrig is only known after the transaction, so we use pre-transaction values such as amount / oldbalanceOrg instead.
5. **Leakage risks:** isFlaggedFraud (the simulator's own rule, flags only 16 of 8,213 frauds, dropped); newbalanceOrig, newbalanceDest and derived balance-error columns (post-transaction values, unavailable at scoring time, benchmark with and without them); nameOrig and nameDest (identifiers, dropped).
6. **No per-user history:** 99.85% of rows have a unique sender, so per-user behaviour features are impossible on PaySim. This is why the team builds a synthetic UPI generator (Step 2.2).
7. **Fraud clusters in the early hours:** the fraud rate is 16-22% in hours 3-5 and about 0.07% during the day (roughly 300x). Probably a simulation artifact (little legitimate traffic at night), so hour-of-day is a strong PaySim feature but must not be over-claimed as a real-world result.
