# Member D integration checkpoint (not final acceptance)
- Existing provisional d_* tables remain unchanged; Member C owns final models/migrations. Do not delete volumes.
- Advisor router is registered if present; its actual imports, ChatMessage schema, target_date and shared contracts must be aligned after PR 7 is available. No fake chat persistence is provided.
- Advisor Docker service still requires its actual Dockerfile and environment configuration; use the same JWT_SECRET as backend JWT_SECRET_KEY. Do not commit secrets.
- Forecast endpoint uses Member C's supplied contract. Income is not returned by C; adapter requires separately computed income. Fraud scoring contract is still unconfirmed.
- Vite proxy targets advisor:8003 inside Docker. Member B's actual AdvisorChat component still needs integration.
- V3 validation defaults to the V3 filename. Preserve V1/V2; missing amount/balance are genuine failures, not waived.
- Run from root: docker compose up -d --build db backend frontend; docker compose ps; then check /docs and frontend. Run adapter tests from backend with python -m pytest tests/test_ml_adapter.py. Run dataset tests from root with python -m pytest data/tests -q. V3 CSV must be supplied by C in data/synthetic.
- Full six-service health, cross-user authorization, E2E, performance, report chapters and backup demo video remain acceptance work. No Git push performed.
