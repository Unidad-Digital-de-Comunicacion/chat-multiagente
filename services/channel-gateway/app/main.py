from fastapi import FastAPI

from .messages import router as messages_router
from .webhooks import router as webhooks_router

app = FastAPI(title="Channel Gateway Service")
app.include_router(webhooks_router)
app.include_router(messages_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
