from fastapi import FastAPI

app = FastAPI(title="Analytics Service")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
