# chat-multiagente

Chat Multiagente Multicanal — plataforma multi-tenant de atención por chat
(WhatsApp/Messenger/Instagram + web) con bot de menú, derivación a
operadores y paneles de administración y atención.

Arquitectura, restricciones de stack y plan de fases: **[docs/CONTEXTO_PROYECTO.md](docs/CONTEXTO_PROYECTO.md)**.

## Levantar el entorno de desarrollo

```bash
cp .env.example .env   # completar secretos locales
docker compose up --build
```

Servicios expuestos: Core (Django+DRF) en `:8001`, Channel Gateway en `:8002`,
Conversation Engine en `:8003`, Operators Desk en `:8004`, Analytics en
`:8005` (los últimos cuatro son stubs de Fase 0 — sólo `/health`). Webchat
(`:8006`) es opcional: `docker compose --profile webchat up`.

Estado del código: **Fase 0** (esqueleto + contenedores) y **Fase 1**
(organizaciones, usuarios/roles, equipos, horarios/días excepcionales y
árbol de menú en Core) implementadas. Ver sección 10 del documento de
contexto para lo que sigue.
