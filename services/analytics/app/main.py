from fastapi import FastAPI

from .observabilidad import MiddlewareRequestId, configurar_logging

configurar_logging("analytics")

app = FastAPI(title="Analytics Service")
app.add_middleware(MiddlewareRequestId)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
