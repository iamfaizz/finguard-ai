# Explanation findings (CP-8)

**Method.** SHAP TreeExplainer on the XGBoost model (artifacts/fraud_v2.json). For each flagged transaction, the top three features that push the score up AND whose actual values make the sentence true become plain-English reasons (src/explain.py). Overlapping features (amount ratio and z-score, 10-minute and 1-hour counts) show only the strongest one.

1. **Coverage.** At the chosen threshold the model catches 19 of the 29 test-set frauds. All 19 are listed with their facts and reasons in explanation_cases.csv. 18 have at least one reason; 1 falls back to a generic sentence because no reason qualified.
2. **Verification.** scripts/verify_explanations.py checks every stated reason against the facts in the same row: 26 reasons, 0 mismatches. Unit tests (tests/test_explain.py) show that a reason appears only for a feature with a positive contribution and a qualifying value, and never repeats the same idea.
3. **SHAP summary.** figures/shap_summary.png is regenerated for dataset v2 (the dataset-v1 version is in data_v1/).
4. **Limit.** Reasons explain why the model flagged a transaction, not that it is fraud. 10 of 12 legitimate large payments (hard negatives) also receive truthful reasons such as "12.8x your usual spend". The app should call these transactions unusual and offer an "It was me" button.
