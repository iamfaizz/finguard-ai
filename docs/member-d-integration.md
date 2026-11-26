# Member D integration notes
This patch preserves the existing database and security helpers. It adds provisional `d_` tables because Member C's SQLAlchemy models and migrations were absent in the uploaded snapshot. Reconcile these tables before the shared schema is finalized; no migration or production readiness is claimed.

## Chapter 3 — Architecture (draft)
React communicates with FastAPI over HTTP on the local development stack. PostgreSQL stores user-owned transactions and goals. The pending-review worker calls categorization and fraud services with bounded retries. The forecast service snapshot exposes /categorize, /forecast and /goal-plan, but has no health endpoint or Dockerfile. Fraud scoring and advisor contracts are absent. The fraud adapter payload is provisional; feature computation, forecast cache invalidation and advisor/forecast proxy endpoints remain to be integrated. Do not send real bank data to this prototype.

## Chapter 8 — Backend/frontend (draft)
JWT access/refresh, Argon2 hashing, rate-limited authentication, user-scoped queries, decimal amounts, CSV size and row validation, deduplication, dashboard aggregates, goal CRUD and a protected React dashboard are implemented as draft code. Refresh tokens are stored in localStorage for this prototype; production needs a hardened session design. RBAC beyond user ownership, column mapping beyond the documented header, contract tests, security scans and latency measurements are pending. The retry worker is single-instance only and needs fair scheduling/locking for production. Fraud threshold 0.5 is provisional.

## Chapter 10 — Deployment (draft)
Run Docker Compose for PostgreSQL, backend and frontend. Preserve the local .env. ML/advisor containers must be supplied by their owners and then added to Compose with health checks. No six-service checkpoint has passed. The frontend uses Vite development server, not a production server.

## Demo script (planned)
1. Start stack and show health. 2. Register a synthetic demo account. 3. Upload a CSV with timestamp,amount,merchant,txn_type. 4. Show dashboard and duplicate rejection. 5. Once ML contracts are integrated, show flagged transaction and feedback, forecast and goal, and advisor response. 6. Stop fraud service and show pending review, restart and show scoring. Record backup video only after these flows actually pass.

## Pending evidence
Existing dataset has 3 missing amounts, 325 missing balances and category mismatch. Tests intentionally remain strict; ask A/C to reconcile. Actual train/test period files absent; no split test pass claimed. CI, full Playwright five-flow suite, three consecutive runs, teammate fresh-clone review, report evidence and backup video remain pending. No checkpoint tags should be created until verified.
