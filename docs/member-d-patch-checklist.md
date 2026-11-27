# Member D integration checkpoint
This patch preserves the provisional d_* tables. Startup adds nullable target_date without deleting data; existing undated goals return 409 for advisor planning until updated. Reconcile with C's final Alembic schema. JWT_SECRET is mapped to JWT_SECRET_KEY in backend only; advisor service must use the same value when merged. B's router is adapted, not a replacement for B's service.

## Verify locally
- docker compose up -d --build db backend
- docker compose ps
- docker compose exec backend python -m pytest tests -v
- Open http://localhost:8000/docs; verify five advisor routes; test authenticated chat save and cross-user isolation.
- Frontend npm install/build, Playwright; verify goal date input and advisor page after teammate merge.
- Data tests: V3 absent in supplied archive; do not substitute V1 silently. Obtain cleaned V3 and split metadata; validate nulls, categories, timestamps, fraud rates, split separation.
- A fraud scoring service and B advisor service absent; C projecttt.py present but service packaging/health and final DB schema pending. Full six-service compose, live forecast/fraud/chat, cache invalidation, performance and security gates remain unverified.
- Demo script/backup video, report chapters 3/8/10, SHAP 1–7, fresh-clone review, commit/PR pending.
