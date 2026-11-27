# ML service CI and contract checks

This contribution adds automated CI coverage for the two ML HTTP services already present in the Member D integration branch.

## Forecast service

The tests exercise the existing public API contract:
- `GET /health`
- `POST /categorize` for one transaction
- `POST /categorize` for a batch
- `POST /forecast`, including the low-history confidence flag and response shape
- `POST /goal-plan`, including the 30% per-category cut cap
- invalid forecast horizon handling

The tests intentionally use short synthetic histories and assert the low-confidence flag. They do not claim that a forecast is accurate or suitable for real financial decisions.

## Fraud service

The existing Fraud tests are now included in CI alongside the Forecast tests. They exercise model loading, input validation, scoring response shape, feature construction, and explanation logic.

## What CI does not prove

Passing unit/contract tests does not replace a clean Docker Compose run against PostgreSQL, end-to-end upload-to-score testing, performance testing, or review of the ML feature history policy. Those remain integration checks for the full team.
