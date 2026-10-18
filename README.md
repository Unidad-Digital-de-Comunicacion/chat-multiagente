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

Servicios expuestos: Core (Django+DRF) en `:8001`, Admin Panel (React) en
`:3000`, Channel Gateway en `:8002`, Conversation Engine en `:8003`,
Analytics en `:8005` (Conversation Engine y Analytics son stubs de
Fase 0 — sólo `/health`). Webchat (`:8006`) es opcional:
`docker compose --profile webchat up`.

Para tener datos de prueba (organización, usuarios, equipos y un árbol de
menú de 2 niveles), correr una vez:

```bash
docker compose run --rm --entrypoint python core manage.py seed_ucd_demo
```

Estado del código: **Fase 0** (esqueleto + contenedores) y **Fase 1**
(organizaciones, usuarios/grupos de permisos, equipos, login con
recuperación de usuario/contraseña por DNI y bloqueo por IP, perfil personal
con avatar recortable) implementadas, más buena parte de **Fase 2**
(horarios/días excepcionales, árbol de menú, mensajes predeterminados del
bot con modo de atención con/sin menú, catálogo de etiquetas de conversación
y configuración de canales de mensajería con chequeo real de salud contra
la Graph API de Meta, con su UI en el Admin Panel — vista previa tipo chat,
editor de formato/emojis, calendario de feriados, selector rápido de rango
horario), más una sección "Plataforma" del Admin Panel sólo para el
superusuario real (organizaciones con sus límites de uso, usuarios de todas
las organizaciones, tokens para la comunicación entre los propios
microservicios del proyecto, estadísticas de uso y salud general de las
APIs externas, y manuales/referencia autogenerada de la API interna vía
Swagger/Redoc) — `encargados_difusion`/`analistas_datos`/`operadores` no
tienen ninguna pantalla en el Admin Panel de Core, es sólo su API de
autenticación. Ver sección 9 (convenciones/seguridad) y sección 10 (estado
por fase) del documento de contexto para el detalle y lo que sigue —
incluida la parte de etiquetas/observaciones/chat interno que queda
explícitamente para la Fase 4/5 (Conversation Engine/Operators Desk), y la
conexión real de cada canal (Embedded Signup, webhooks, envío) que es
Channel Gateway, Fase 3.


Pasa a Version 0.0.2
