from fastapi import FastAPI

app = FastAPI()


@app.get("/")
def root():
    """What this API is and where to go next."""
    return {"name": "Task API", "version": "1.0", "endpoints": ["/tasks"]}


@app.get("/health")
def health():
    """Liveness check. Returns ok as long as the server answers."""
    return {"status": "ok"}
