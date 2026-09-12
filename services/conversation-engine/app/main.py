from fastapi import FastAPI

app = FastAPI(title="Conversation Engine Service")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
