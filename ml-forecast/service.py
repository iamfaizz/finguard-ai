"""HTTP wrapper for the existing Forecast API; leaves projecttt.py unchanged."""
from projecttt import create_app

app = create_app()


@app.get("/health")
def health():
    return {"status": "ok", "service": "ml-forecast", "version": "0.2.0-role-c"}
