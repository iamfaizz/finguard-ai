from projecttt import create_app, VERSION
app = create_app()

@app.get("/health")
def health():
    return {"status": "ok", "version": VERSION}
