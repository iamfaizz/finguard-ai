# FinGuard AI service integration

## Service layout
- Backend: port 8000
- ML Fraud: port 8001 (copy the complete `ml-fraud/` directory from branch `a/ml-fraud-final`)
- ML Forecast: port 8002 (existing `ml-forecast/projecttt.py` remains unchanged)

## Run
From the repository root:
```bash
docker compose config
docker compose build
docker compose up -d
docker compose ps
```

## Health checks
```bash
curl http://localhost:8000/health
curl http://localhost:8001/health
curl http://localhost:8002/health
```

Forecast API routes are inherited from `projecttt.py`: POST `/categorize`, POST `/forecast`, POST `/goal-plan`.
Fraud API route: POST `/score`.

## Important integration boundary
Compose gives the backend these internal service URLs:
- `ML_FRAUD_URL=http://ml-fraud:8001`
- `ML_FORECAST_URL=http://ml-forecast:8002`

The current minimal backend does not yet implement proxy/client calls to these services. This commit establishes orchestration and service reachability only; it does not claim that backend routes already invoke the ML services. Backend integration routes and contract tests are a follow-up task.

The Fraud service model is loaded at startup. Its health check should pass only after the model is loaded.
