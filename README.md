# FinGuard AI

An AI-powered platform for fraud detection, spending forecasts, and financial guidance.

B.Tech final-year project, G.L. Bajaj Institute of Technology & Management. Group GC_2026_012. Guide: Dr. Payal Garg.

## Team
Faiz Ahmad, Himanshu Patel, Faham Ahmad Khan, Harsh Yadav

## Modules
- `ml-fraud`: fraud detection and explainability
- `ml-forecast`: categorization, forecasting, goal planner
- `advisor`: RAG-based AI advisor
- `backend` and `frontend`: API gateway and dashboard

## Run locally with Docker Compose

Requirements: Docker Engine/Desktop with Docker Compose v2, enough RAM/disk for the Advisor's CPU embedding model, and Python 3 for the optional smoke checks.

1. Clone the repository and open its root folder.
2. Copy the sample environment file: `cp .env.example .env` (on Windows PowerShell: `Copy-Item .env.example .env`).
3. **Before starting**, replace `POSTGRES_PASSWORD` and `JWT_SECRET_KEY` in `.env` with different strong random secrets. Do not commit `.env`.
4. For the AI Advisor, configure an available provider. The default is `LLM_PROVIDER=claude` and requires `ANTHROPIC_API_KEY`. Alternatively, configure `LLM_PROVIDER=ollama` with a reachable local Ollama server and a downloaded `OLLAMA_MODEL`. The rest of the application can start without a working LLM provider, but actual advisor chat will not work until configured.
5. Start services: `docker compose up -d --build`. The initial Advisor build downloads a CPU embedding model and can take several minutes.
6. Inspect status: `docker compose ps`. Then run `python scripts/smoke_stack.py` to check the five HTTP services plus the database indirectly via backend startup.
7. Open the dashboard at **http://localhost:5173**; register a user. API documentation: **http://localhost:8000/docs**.

### Local endpoints

| Service | URL |
| --- | --- |
| Frontend | http://localhost:5173 |
| Backend API | http://localhost:8000/docs |
| Fraud API | http://localhost:8001/docs |
| Forecast API | http://localhost:8002/docs |
| Advisor API | http://localhost:8003/docs |

All HTTP ports are bound to `127.0.0.1` in Docker Compose, so they are for development on the same machine.

### Verify the data flow

Run `python scripts/smoke_stack.py --full` **only on a disposable development database**. This registers a synthetic account, calls the dashboard, uploads one synthetic transaction and checks transaction listing. It does **not** establish that the transaction has been scored; the backend may leave incomplete history in `pending_review`.

For a manual dashboard demo, upload `data/templates/transaction_upload_template.csv` after signing in. Some rows may remain pending if fraud features cannot be built from the available history. See `docs/final-integration-status.md`.

### Troubleshooting

- `docker compose config` validates Compose interpolation and catches missing environment variables.
- `docker compose ps` shows whether containers are healthy.
- `docker compose logs --tail=100 backend ml-forecast ml-fraud advisor frontend db` displays startup failures.
- If advisor chat fails, check the selected LLM provider, API key, model and connectivity; a healthy `/health` endpoint alone does not prove the LLM works.
- If the frontend is reachable but backend calls fail, ensure port 8000 is free and the backend is healthy.
- Do not use `docker compose down -v` unless you intentionally want to **delete local database and Chroma volumes**. Use `docker compose down` to stop services while retaining data.

## Validation scope

GitHub Actions tests backend, frontend build, Fraud and Forecast API contracts. This is not equivalent to an end-to-end test of all six containers and a real advisor response. Use the smoke script plus manual flows on a machine with Docker before declaring the full project runnable.
