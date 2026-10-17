import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config import settings
from app.routes import session_routes, message_routes, websocket_routes

app = FastAPI(
    title="Webchat Service (Channel Gateway - Webchat)",
    description="Microservicio de pasarela para el canal Webchat. Conecta el widget web con Core.",
    version="1.0.0"
)

# Configuración de CORS para permitir la incrustación desde sitios de terceros
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registro de rutas de API
app.include_router(session_routes.router)
app.include_router(message_routes.router)
app.include_router(websocket_routes.router)

# Endpoint de healthcheck exigido por la infraestructura del monorepo
@app.get("/health", tags=["Health"])
def health_check():
    return {
        "status": "ok",
        "service": "webchat",
        "core_url": settings.CORE_URL
    }

# Montaje de archivos estáticos para servir el widget embebible (widget.js)
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Página de demostración/prueba del cliente
test_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "test_client.html")
@app.get("/demo", tags=["Demo"])
def demo_page():
    if os.path.exists(test_file):
        return FileResponse(test_file)
    return {"message": "test_client.html no encontrado"}
