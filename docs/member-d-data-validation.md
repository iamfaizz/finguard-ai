# Member D - Dataset Validation

Dataset: synthetic_transactions_behavioral_v3.csv
Total rows: 23890

Validation results:
- Passed: 6
- Failed: 3
- Missing amount values: 3
- Missing balance values: 325

Dataset validation was executed successfully.
The original dataset contains missing values.
Cleaning and missing-value handling require agreement
with the ML team to preserve feature consistency.

The original dataset and validation rules were not modified.

## Cleaned Dataset Validation

- Original rows: 23890
- Cleaned rows: 23565
- Removed incomplete rows: 325
- Original fraud rows: 179
- Cleaned fraud rows: 177
- Validation: 8 passed, 1 failed

Missing-value and schema checks now pass.
The remaining failure is the per-user fraud rate limit.
Removing incomplete rows changes the fraud distribution.

Original dataset and validation rules remain unchanged.
Final cleaning strategy requires ML team approval.
