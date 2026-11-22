# advisor (Member 2 / B)

RAG financial advisor. Flow: guard -> regex tool routing -> Chroma retrieval -> LLM explains -> SSE stream with citations.

## Run
```bash
cp .env.example .env            # add the advisor lines from advisor/env.snippet
docker compose up --build advisor
docker compose exec advisor python -m scripts.ingest                 # fill ChromaDB (once, and after doc edits)
docker compose exec advisor python -m scripts.ingest --check "what is Section 80C"   # CP-5.2
docker compose exec advisor pytest tests -q                          # needs requirements-dev.txt
python -m eval.run_eval                                               # CP-5.5 (free parts)
```
Local (no Docker): `cd advisor && pip install -r requirements-dev.txt && JWT_SECRET=dev CHROMA_PATH=./chroma_data uvicorn app.main:app --port 8003`.

## Contract points to agree with the others (PR comments!)
- **D**: compose build `context: .` + `dockerfile: advisor/Dockerfile`; port 8003; volume `chroma_data:/data/chroma`; same `JWT_SECRET`, `JWT_ALGORITHM`, user id in the `sub` claim; include `advisor_tools.router`; Caddy route `/advisor/*` -> advisor:8003 (SSE needs no buffering); `shared/__init__.py` must exist.
- **C**: `POST /forecast` response fields used in `_forecast()`; goal formula identical to the goal planner.
- **A**: nothing needed.
