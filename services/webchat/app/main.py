from fastapi import FastAPI

app = FastAPI(title="Webchat Service (stub — Fase 9)")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
