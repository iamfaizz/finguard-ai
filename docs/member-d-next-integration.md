# Integration handoff (supplement)

This supplement updates the dataset taxonomy and provides the frontend token helper requested by Member B. It does not replace database models, teammate code, or Compose configuration.

- Dataset: C confirms 3 missing amounts and 325 missing balances are defects. Strict checks remain enabled. Train/test separation requires confirmed split files.
- Advisor: B PR #7 supplies router, shared contracts and chat UI. Merge/review actual files before registering router. Use JWT_SECRET_KEY as the value for advisor JWT_SECRET; never commit the value. Advisor uses port 8003 and root build context. Add Chroma volume and shared network after service files arrive.
- Forecast: C reports total_predicted_spending, daily_predicted_spending, category_forecasts, method, low_confidence. Income is absent; do not invent it. Exact transaction payload and schema still pending.
- Fraud: endpoint, feature schema and port still pending. Existing pending_review state is not a successful fraud classification.
- Database: C migrations and actual models pending. Do not run destructive migrations against the existing volume.
- Remaining acceptance: auth isolation, CSV duplicate handling, full six-service health, five E2E flows, report chapters and demo video. No claim of full integration or passing tests.
