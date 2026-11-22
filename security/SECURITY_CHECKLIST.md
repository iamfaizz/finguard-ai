# Security checklist (Step 8.3) - owner: B, signed off by C (cross-check rotation)

Mark each row `pass` or `accepted-risk: <reason>` and attach evidence. CP-8.3 needs no open high-severity alerts.

| # | Check | How to test | Result | Evidence |
|---|-------|-------------|--------|----------|
| 1 | Broken object-level auth (user A reads user B's transaction/goal/chat) | Log in as 2 users; request B's ids with A's token -> 403/404 | | pytest name |
| 2 | Broken authentication | wrong password, expired JWT (15 min), tampered JWT, token for a deleted user | | |
| 3 | Excessive data exposure | API responses contain no password hash, no other users' fields | | |
| 4 | Rate limiting | 20 rapid `/chat` calls -> 429; 20 rapid logins -> 429 | | |
| 5 | Broken function-level auth | normal user cannot call admin/internal routes | | |
| 6 | Injection (SQL) | `' OR 1=1 --` in search/filter/CSV fields; ORM only, no string-built SQL | | |
| 7 | Prompt injection | advisor eval adversarial group all handled (reports/advisor/results.md) | | |
| 8 | LLM sees aggregates only | read tools.py + backend router: no raw rows, no names, no account numbers sent | | |
| 9 | Secrets | `gitleaks detect` clean; `.env` in .gitignore; only `.env.example` committed | | |
| 10 | Dependencies | `pip-audit` per service, `npm audit --omit=dev`; no high/critical open | | |
| 11 | Security misconfiguration | CORS = frontend origin only; only ports 80/443 public; Postgres + ML ports internal | | |
| 12 | Safe frontend rendering | chat markdown has no raw HTML (react-markdown without rehype-raw); links https only | | |
| 13 | File upload | >5 MB rejected, wrong type rejected, CSV formula cells (`=cmd|...`) not executed | | |
| 14 | Logging | logs contain no JWTs, no API keys, no full chat text | | |

Run the automated parts with `bash security/run_scans.sh`.
