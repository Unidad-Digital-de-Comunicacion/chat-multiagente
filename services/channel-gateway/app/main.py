from fastapi import FastAPI

app = FastAPI(title="Channel Gateway Service")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
