# Contexto del proyecto — Plataforma de Chat Multiagente y Multicanal

> **Cómo usar este documento:** este archivo es el contexto de referencia para ir construyendo el
> proyecto por partes. Cada vez que se aborde una fase nueva (sección 10), releer el bloque de esa
> fase junto con las secciones 2 a 9. No implementar nada de la sección 11 (fuera de alcance) salvo
> que se pida explícitamente. Ante una ambigüedad no cubierta acá, preferir la opción más simple
> que respete la sección 1 (restricciones) antes de preguntar.

## 1. Restricciones no negociables

- **Stack cerrado**: Python (Django y FastAPI), PostgreSQL, React (TypeScript) y Java (Android).
  No agregar Node.js como runtime de backend, ni Kafka/RabbitMQ, ni Redis, ni Elasticsearch, ni
  almacenamiento tipo S3, ni ningún otro framework/lenguaje. Docker/docker-compose se usan solo
  como empaquetado, no cuentan como "tecnología nueva".
- **Multi-tenant desde el día 1**: toda tabla de negocio lleva `organization_id` (o lo hereda por
  FK) y todo query se filtra por la organización del usuario autenticado. No se construye nada
  single-tenant "para simplificar" — es más barato hacerlo bien desde el modelo que migrarlo después.
- **PostgreSQL como única base de datos**: una instancia, un esquema por microservicio
  (`core`, `channel_gateway`, `conversation_engine`, `operators_desk`, `analytics`, `webchat`).
- **Sin integraciones de terceros tipo chatealo.io/Chatwoot**: la conexión con WhatsApp/Messenger/
  Instagram es directa contra la API de Meta (Embedded Signup + Graph API + webhooks propios).
- **Un contenedor por microservicio**, orquestados con `docker-compose`. Cada servicio es un
  proyecto independiente con su propio `Dockerfile`, dependencias y esquema de base de datos.
- **Reutilización de código existente**: el motor de menú (árbol) y de horarios hábiles se porta
  desde el repo propio `github.com/garzamorada/chatbot` (Django, ~60 tests), adaptándolo a
  multi-tenant. Ver sección 5.

## 2. Arquitectura general

6 microservicios backend + 2 frontends web (React) + 1 app móvil (Java, fuera del docker-compose).

```
                    ┌──────────────────┐        ┌──────────────────┐
                    │  Admin Panel     │        │ Operators Desk    │
                    │  (React)         │        │ Web (React)       │
                    └────────┬─────────┘        └─────────┬─────────┘
                             │                              │
        ┌────────────────────────────────────────────────────────────┐
        │                                                              │
   ┌────▼─────┐   ┌───────────────┐   ┌──────────────────┐  ┌────────▼────────┐
   │   CORE   │◄──┤ CHANNEL       │   │ CONVERSATION      │  │ OPERATORS DESK   │
   │ (Django) │   │ GATEWAY       │──►│ ENGINE            │◄─┤ SERVICE          │
   │          │   │ (FastAPI)     │   │ (FastAPI + WS)    │  │ (FastAPI + WS)   │
   └────┬─────┘   └───────┬───────┘   └─────────┬─────────┘  └────────┬────────┘
        │                 │                     │                      │
        │                 ▼                     │                      │
        │           Meta Graph API              │                      │
        │        (WhatsApp / Messenger /        │                      │
        │             Instagram)                │                      │
        │                                        │                      │
   ┌────▼─────┐                          ┌───────▼──────┐      ┌────────▼────────┐
   │ ANALYTICS│                          │  App Móvil   │      │  WEBCHAT SERVICE │
   │ (FastAPI,│                          │  Operador    │      │  (FastAPI + WS)  │
   │ read-only│                          │  (Android/   │      │  OPCIONAL /      │
   │  sobre   │                          │   Java)      │      │  fast-follow     │
   │  Core)   │                          └──────────────┘      └──────────────────┘
   └──────────┘

                     Todos los servicios ──► PostgreSQL (1 instancia, 1 esquema c/u)
```

### 2.1 Principio de responsabilidad por servicio

- **Core decide, los demás ejecutan.** Toda la lógica de negocio (menú, horarios, roles, límites
  de conexión, a qué equipo deriva una conversación) vive en Core (Django). Los servicios FastAPI
  son ejecutores de I/O: le preguntan a Core "¿qué hago con esto?" y ejecutan la respuesta.
- **FastAPI = I/O asíncrono de alto rendimiento**: webhooks de Meta, WebSockets en tiempo real,
  agregaciones de solo lectura. Ningún servicio FastAPI tiene su propia fuente de verdad del
  negocio (organización, usuarios, menú, horarios) — todo eso se consulta a Core vía REST.

## 3. Detalle de los 6 microservicios

| # | Servicio | Carpeta | Stack | Puerto | Rol |
|---|----------|---------|-------|--------|-----|
| 1 | **Core Platform Service** | `services/core` | Django + DRF + PostgreSQL | 8001 | Organizaciones, usuarios, roles (Admin/Difusión/Operador/Data Manager), equipos, horarios hábiles (portado), menú árbol (portado), lógica del bot, suscripciones/límite de conexiones, historial, etiquetas, datos transaccionales. Fuente de verdad de todo. |
| 2 | **Channel Gateway Service** | `services/channel-gateway` | FastAPI + PostgreSQL | 8002 | Embedded Signup de WhatsApp, recepción/verificación de webhooks de Meta, envío de mensajes salientes. Sin lógica de negocio propia. (Messenger/Instagram: mismo servicio, fast-follow). |
| 3 | **Conversation Engine** | `services/conversation-engine` | FastAPI + WebSockets + PostgreSQL | 8003 | Post-derivación: asigna operador (round-robin) dentro del equipo indicado por Core, entrega mensajes en tiempo real vía WebSocket, controla el límite de conexiones simultáneas (`OperatorSession`). |
| 4 | **Operators Desk Service** | `services/operators-desk` | FastAPI + WebSockets + PostgreSQL | 8004 | Backend a medida (BFF) para el **Operators Desk Web** (React): bandeja de chats asignados, hilo de conversación, acciones rápidas (responder/derivar/etiquetar/cerrar). Es la contraparte web de lo que la app Android resuelve en mobile — reutiliza Core (historial/datos) y Conversation Engine (tiempo real/asignación) en vez de duplicar su lógica. |
| 5 | **Analytics Service** | `services/analytics` | FastAPI + PostgreSQL (solo lectura) | 8005 | Agregaciones y reportes para el rol Data Manager: volumen de conversaciones por canal/equipo/operador, tiempos de respuesta, uso del menú (abandono por nodo). Se conecta a los esquemas de Core/Conversation Engine con un usuario de base de datos **read-only**; no escribe nunca. |
| 6 | **Webchat Service** *(opcional / fast-follow)* | `services/webchat` | FastAPI + WebSockets + PostgreSQL | 8006 | Backend del widget de chat embebible en un sitio web propio del cliente, como canal adicional a WhatsApp/Messenger/Instagram. Sigue el mismo contrato de mensaje normalizado que Channel Gateway. **No construir hasta que se pida explícitamente** — dejar la carpeta con un stub (`/health`) y el compose con `profiles: ["webchat"]`. |

### 3.2 Frontends y app móvil (no son "microservicios" pero forman parte del repo)

| Proyecto | Carpeta | Stack | Puerto | Consume |
|---|---|---|---|---|
| Admin Panel | `frontend/admin-panel` | React + TypeScript | 3000 | Core (todo lo administrativo) + Analytics (reportes) + enlaces SSO a las pantallas Django portadas (menú/horarios, ver sección 5). |
| Operators Desk Web | `frontend/operators-desk-web` | React + TypeScript | 3001 | Operators Desk Service (bandeja/hilo/acciones) vía REST + WebSocket. |
| App Operador Android | `mobile/android-operator-app` | Java (Android SDK, MVVM) | — (no dockerizado) | Mismos endpoints que Operators Desk Service (es el mismo contrato de API para ambos clientes: web y mobile). |

> Nota de diseño: **Operators Desk Service** y la **app Android** son dos clientes del mismo
> contrato de "atención de chats" (bandeja, hilo, derivar, etiquetar, cerrar, historial). El
> servicio FastAPI expone ese contrato una sola vez; el Admin Panel NO debe usarse para atender
> chats (es solo configuración/administración).

## 4. Modelo de datos por servicio (resumen de entidades)

### 4.1 `core` (Django)
- `Organization` (nombre, plan, límite de conexiones, estado)
- `User` (extiende el de Django: organization FK, rol: admin/difusion/operador/data_manager)
- `Team` (organization FK, nombre, miembros M2M a User)
- `HorarioAtencion` — **portado**, agregar `organization` FK (día, hora_inicio, hora_fin, activo)
- `DiaExcepcional` — **portado**, agregar `organization` FK opcional (feriado/asueto/horario_reducido; los feriados nacionales pueden ser catálogo compartido con `organization=None`)
- `MenuOpcion` — **portado** (árbol recursivo `parent`/hijos; tipos `SUBMENU/RESPUESTA/DERIVACION/VOLVER/INICIO/TERMINAR`), agregar `organization` FK (unicidad de `slug` por organización, no global) y, en tipo `DERIVACION`, FK obligatoria a `Team` en vez de un texto de etiqueta
- `Conversacion` — **portado**, agregar `organization` y `channel`; sacar referencias a `chatealo` (conversation_id/inbox_id propios de esa plataforma)
- `ConversacionLog` — **portado** tal cual (auditoría turno a turno)
- `Contact` (organization FK, canal, identificador externo — teléfono en WhatsApp)
- `Tag` (organization FK, nombre)
- `TransactionalData` (organization FK, contact/conversation FK, tipo, payload JSON)
- `Subscription` (organization FK — o campo embebido en Organization —, plan, límite de conexiones)
- Endpoint interno clave: `POST /api/core/bot/mensaje-entrante/` → recibe `{organization_id, channel, contact_externo_id, texto}`, devuelve `{acciones: [...]}` (enviar_texto, derivar_a_equipo, etc.), reutilizando la lógica portada de `MenuOpcion`/`Conversacion`.
  - Cuando la acción es `mostrar_menu`, además del texto plano numerado (fallback universal para cualquier canal) Core devuelve las opciones como lista estructurada `opciones: [{id, titulo}]`. **Core decide el contenido, nunca el formato de UI del canal** (sección 2.1): la traducción de esa lista a un widget de selección nativo vive en cada Channel Gateway, no acá.

### 4.1.1 Selección nativa por canal (no texto numerado si el canal lo permite)

Todo menú (y la opción "Hablar con un operador") debe ofrecerse como selección
nativa del canal siempre que sea posible; el texto plano numerado es sólo el
fallback para canales sin ese soporte o cuando la cantidad de opciones no
entra en los límites del widget nativo:

| Canal | Widget nativo | Límites | Fallback |
|---|---|---|---|
| WhatsApp (Graph API) | `interactive.type=list` (4-10 opciones) o `interactive.type=button` (1-3) | Lista: máx. 10 filas, título de fila ≤24 car. Botones: máx. 3, título ≤20 car. | Fuera de esos rangos, texto plano numerado |
| Messenger | Quick replies o generic template con botones | Quick replies: máx. 13, texto ≤20 car. | Texto plano numerado |
| Instagram | Quick replies | Soporte más limitado que Messenger | Texto plano numerado |
| Telegram | Inline keyboard | Sin límite práctico (paginar si son muchas) | Texto plano numerado |
| Webchat (Fase 9) | Botones nativos del widget propio | Sin límite impuesto por una API externa | Texto plano numerado |
| Email | — | No tiene selección interactiva | Siempre texto plano numerado |

### 4.1.2 Formato de texto (negrita/cursiva) por canal

Todos los textos que administra Core (`mensaje_bienvenida`, saludos, texto de
`RESPUESTA`, mensajes de derivación/despedida, etc.) se cargan con un marcado
neutro, el mismo en cualquier canal:

- `**texto**` → negrita
- `_texto_` → cursiva
- `~texto~` → tachado
- `` `texto` `` → monoespaciado

**Core nunca guarda ni genera sintaxis de un canal en particular.** Igual que
con la selección nativa (4.1.1), cada Channel Gateway-type service traduce
ese marcado neutro al formato real de su canal antes de enviar — o lo
descarta si el canal no soporta texto enriquecido:

| Canal | Traducción | Notas |
|---|---|---|
| WhatsApp | `**t**`→`*t*`, `_t_`, `~t~`, `` `t` `` → ```` ```t``` ```` | Mismos símbolos que WhatsApp salvo negrita (asterisco simple) |
| Telegram | `*t*`, `_t_`, `~t~`, `` `t` `` (MarkdownV2) | Escapar los caracteres especiales de MarkdownV2 al traducir |
| Webchat | se deja el marcado tal cual (o se convierte a HTML) | el widget lo renderiza del lado del cliente |
| Email | `<b>`, `<i>`, `<s>`, `<code>` | HTML soportado |
| Messenger / Instagram | se descarta todo el marcado, sólo el texto interior | sin soporte de texto enriquecido |

La función de traducción es pura (texto neutro → texto del canal), sin
estado ni I/O: conviene un módulo compartido (ej. `text_formatting.py`) que
cada servicio importe, en vez de reimplementarla en Channel Gateway,
Operators Desk Web, etc.
- Endpoint interno: `GET /api/core/teams/{id}/horario-habil/` → `{en_horario: bool, proxima_apertura: datetime|null}` (envuelve `esta_en_horario`/`proxima_apertura` portados).

### 4.2 `channel_gateway` (FastAPI)
- `Channel` (organization_id, tipo=whatsapp, phone_number_id, waba_id, token cifrado, estado)
- `MensajeSaliente` (log simple de envíos, para reintentos/diagnóstico)
- Endpoints: `POST /webhooks/meta/{channel_uuid}` (verificación de firma + normalización), `POST /channels/whatsapp/embedded-signup/callback`, `POST /messages/send`.

### 4.3 `conversation_engine` (FastAPI + WS)
- `OperatorSession` (organization_id, user_id, canal=web|app, conectado_desde, estado)
- `AsignacionChat` (conversation_id de Core, team_id, operator_id, estado, timestamps)
- Endpoints: `WS /ws/operador/{token}`, `POST /asignaciones/derivar`, `POST /asignaciones/reasignar`, `GET /organizations/{id}/conexiones-activas`.

### 4.4 `operators_desk` (FastAPI + WS)
- No tiene tablas propias de negocio (es un BFF): compone datos de Core (historial, tags, datos
  transaccionales) y de Conversation Engine (asignación, tiempo real) en las formas que necesita
  la UI del desk. Si hace falta cache de lectura, usar una tabla de solo-lectura simple en su
  propio esquema, nunca duplicar la escritura.
- Endpoints: `GET /bandeja`, `GET /conversaciones/{id}/hilo`, `POST /conversaciones/{id}/responder`,
  `POST /conversaciones/{id}/derivar`, `POST /conversaciones/{id}/etiquetar`, `POST /conversaciones/{id}/cerrar`,
  `WS /ws/desk/{token}`.

### 4.5 `analytics` (FastAPI, solo lectura)
- Sin modelos propios de escritura. Conexión de solo lectura a los esquemas `core` y
  `conversation_engine`. Endpoints: `GET /reportes/volumen`, `GET /reportes/tiempos-respuesta`,
  `GET /reportes/uso-menu`, `GET /export/historial.csv`.

### 4.6 `webchat` (opcional)
- `WebchatSession` (organization_id, visitor_id, estado) — mismo patrón que `Channel`/`Contact` de
  Channel Gateway, pero para visitantes anónimos de un sitio web. No implementar hasta que se pida.

## 5. Reutilización del repo `garzamorada/chatbot`

Repo: https://github.com/garzamorada/chatbot (Django 5.1 + MySQL, single-tenant, dependiente de
chatealo.io). Se porta la lógica de negocio, se descarta la dependencia de chatealo.

| Archivo/modelo original | Acción |
|---|---|
| `chatbot/models.py` → `MenuOpcion`, `HorarioAtencion`, `DiaExcepcional`, `Conversacion`, `ConversacionLog` | Portar a `services/core`, agregar `organization` FK, correr y adaptar los tests existentes (`chatbot/tests.py`, ~60 tests) |
| `chatbot/horarios.py` (`esta_en_horario`, `proxima_apertura`, `mensaje_fuera_de_horario`, `sincronizar_feriados`) | Portar tal cual, es lógica pura de fechas — solo agregar filtro por organización en las queries a `HorarioAtencion`/`DiaExcepcional` |
| `chatbot/defaults.py` (textos por defecto + variables `{nombre}`/`{area}`) | Portar tal cual |
| `chatbot/feriados_client.py` | Portar tal cual (llamada HTTP a API pública de feriados AR, no agrega tecnología) |
| `chatbot/chatealo_client.py`, `chatbot/firma.py`, modelo `InboxChatealo` | **Descartar** — se reemplazan por el cliente de la Graph API de Meta y la verificación de firma `X-Hub-Signature-256` en `services/channel-gateway` |
| Editor visual drag-and-drop del árbol de menú (Django templates + Bootstrap) | Portar tal cual a `services/core` (vistas Django clásicas, no DRF), filtrando por organización; se enlaza desde el Admin Panel (React) vía SSO/redirect con el mismo JWT/sesión |
| Grilla semanal de horarios + carga de excepciones (Django templates) | Ídem — se reutiliza la UI, se enlaza desde el Admin Panel |
| Permisos Django (`gestionar_menu_chatbot`, `gestionar_horarios_chatbot`, etc.) | Portar como base de los permisos de los roles Admin/Difusión sobre menú y horarios |
| Base de datos MySQL | Migrar a PostgreSQL (cambios de tipos menores: `TextField`, `JSONField`, etc. son compatibles) |

## 6. Estructura de carpetas (monorepo)

```
chat-platform/
├── docker-compose.yml
├── docker-compose.override.yml        # overrides de desarrollo (hot-reload, volúmenes)
├── .env.example
├── services/
│   ├── core/                          # Django
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   ├── manage.py
│   │   └── config/ organizations/ users/ teams/ business_hours/ menu/ conversations/ tags/ transactional_data/ subscriptions/ bot/
│   ├── channel-gateway/                # FastAPI
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── app/ (main.py, meta_client.py, webhooks.py, models.py, schemas.py)
│   ├── conversation-engine/            # FastAPI + WS
│   ├── operators-desk/                 # FastAPI + WS
│   ├── analytics/                      # FastAPI (solo lectura)
│   └── webchat/                        # FastAPI + WS — stub, profile "webchat"
├── frontend/
│   ├── admin-panel/                    # React + TS
│   └── operators-desk-web/             # React + TS
├── mobile/
│   └── android-operator-app/           # Java (no se dockeriza)
└── docs/
    └── CONTEXTO_PROYECTO.md            # este archivo
```

Convención por servicio FastAPI: `app/main.py` (arranque + routers), `app/core_client.py` (cliente
HTTP tipado hacia Core), `app/deps.py` (validación de JWT emitido por Core), `app/models.py`
(SQLAlchemy, solo si el servicio tiene tablas propias), `app/schemas.py` (Pydantic).

## 7. `docker-compose.yml` (esqueleto de referencia)

```yaml
version: "3.9"

x-fastapi-common: &fastapi-common
  environment:
    - CORE_BASE_URL=http://core:8001
    - JWT_PUBLIC_KEY_URL=http://core:8001/api/auth/jwks/
  depends_on:
    - db
    - core

services:
  db:
    image: postgres:16
    environment:
      - POSTGRES_USER=${POSTGRES_USER}
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
      - POSTGRES_DB=${POSTGRES_DB}
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./services/db/init-schemas.sql:/docker-entrypoint-initdb.d/init-schemas.sql
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
      interval: 5s
      timeout: 5s
      retries: 10

  core:
    build: ./services/core
    environment:
      - DJANGO_SECRET_KEY=${DJANGO_SECRET_KEY}
      - DB_HOST=db
      - DB_NAME=core
      - DB_USER=${POSTGRES_USER}
      - DB_PASSWORD=${POSTGRES_PASSWORD}
    ports:
      - "8001:8000"
    depends_on:
      db:
        condition: service_healthy

  channel-gateway:
    build: ./services/channel-gateway
    <<: *fastapi-common
    environment:
      - DB_HOST=db
      - DB_NAME=channel_gateway
      - META_APP_ID=${META_APP_ID}
      - META_APP_SECRET=${META_APP_SECRET}
    ports:
      - "8002:8000"

  conversation-engine:
    build: ./services/conversation-engine
    <<: *fastapi-common
    environment:
      - DB_HOST=db
      - DB_NAME=conversation_engine
    ports:
      - "8003:8000"

  operators-desk:
    build: ./services/operators-desk
    <<: *fastapi-common
    environment:
      - DB_HOST=db
      - DB_NAME=operators_desk
      - CONVERSATION_ENGINE_URL=http://conversation-engine:8000
    ports:
      - "8004:8000"

  analytics:
    build: ./services/analytics
    <<: *fastapi-common
    environment:
      - DB_HOST=db
      - DB_NAME_CORE_READONLY=core
      - DB_USER_READONLY=${POSTGRES_READONLY_USER}
      - DB_PASSWORD_READONLY=${POSTGRES_READONLY_PASSWORD}
    ports:
      - "8005:8000"

  webchat:
    build: ./services/webchat
    <<: *fastapi-common
    environment:
      - DB_HOST=db
      - DB_NAME=webchat
    ports:
      - "8006:8000"
    profiles: ["webchat"]      # no arranca por defecto: docker compose --profile webchat up

  admin-panel:
    build: ./frontend/admin-panel
    environment:
      - VITE_CORE_API_URL=http://localhost:8001
      - VITE_ANALYTICS_API_URL=http://localhost:8005
    ports:
      - "3000:80"
    depends_on:
      - core

  operators-desk-web:
    build: ./frontend/operators-desk-web
    environment:
      - VITE_OPERATORS_DESK_API_URL=http://localhost:8004
    ports:
      - "3001:80"
    depends_on:
      - operators-desk

volumes:
  pgdata:
```

`services/db/init-schemas.sql` crea los esquemas al arrancar el contenedor por primera vez:

```sql
CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS channel_gateway;
CREATE SCHEMA IF NOT EXISTS conversation_engine;
CREATE SCHEMA IF NOT EXISTS operators_desk;
CREATE SCHEMA IF NOT EXISTS analytics;
CREATE SCHEMA IF NOT EXISTS webchat;
-- usuario de solo lectura para el servicio analytics
CREATE ROLE readonly_user WITH LOGIN PASSWORD '...';
GRANT USAGE ON SCHEMA core, conversation_engine TO readonly_user;
GRANT SELECT ON ALL TABLES IN SCHEMA core, conversation_engine TO readonly_user;
```

### 7.1 `Dockerfile` — plantilla Django (`services/core`)

```dockerfile
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]
```

### 7.2 `Dockerfile` — plantilla FastAPI (resto de servicios)

```dockerfile
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 7.3 `Dockerfile` — plantilla React (build + nginx)

```dockerfile
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json .
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
```

## 8. Variables de entorno (`.env.example`)

```
# Postgres
POSTGRES_USER=chatplatform
POSTGRES_PASSWORD=changeme
POSTGRES_DB=chatplatform
POSTGRES_READONLY_USER=readonly_user
POSTGRES_READONLY_PASSWORD=changeme_ro

# Django (core)
DJANGO_SECRET_KEY=changeme
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,core

# Meta / WhatsApp (channel-gateway)
META_APP_ID=
META_APP_SECRET=
META_WEBHOOK_VERIFY_TOKEN=
```

Nunca commitear `.env` real — solo `.env.example`. Los tokens de canal (por organización) se
guardan cifrados en la base de `channel-gateway`, no en variables de entorno.

## 9. Convenciones transversales

- **Autenticación**: Core (Django) emite JWT (`djangorestframework-simplejwt`) con `org_id` y
  `rol` en el payload. Todos los servicios FastAPI validan ese mismo JWT (clave pública o
  compartida vía `JWT_PUBLIC_KEY_URL`/secreto compartido — definir uno al implementar Fase 1).
- **Scoping multi-tenant**: cada request autenticado trae `org_id` en el token; todo query
  filtra por ese `org_id`. En Django, usar un manager/mixin (`OrganizationScopedQuerySet`) para no
  repetir el filtro a mano en cada vista.
- **Contratos entre servicios**: OpenAPI autogenerado (DRF + FastAPI). Antes de que un servicio
  FastAPI consuma un endpoint de Core que no existe todavía, crearlo primero en Core (Core nunca
  debe ser bloqueado por otro servicio).
- **Testing**: cada servicio con su propia suite (`pytest`/`pytest-django`). Los tests portados de
  `garzamorada/chatbot` se migran junto con el código como red de seguridad del refactor
  multi-tenant — no se descartan.
- **Migraciones de base**: Django usa sus migraciones nativas contra el esquema `core`. Los
  servicios FastAPI con tablas propias usan Alembic contra su propio esquema.
- **Nombres**: en código, inglés (`Organization`, `Team`, `MenuOption`) aunque el dominio y los
  nombres portados del repo original estén en español (`MenuOpcion`, `HorarioAtencion`) — decidir
  al portar si se traducen los nombres de modelos o se conservan tal cual para minimizar riesgo de
  romper la lógica ya probada. Recomendado: **conservar los nombres originales en español** en el
  módulo portado (`services/core/menu/models.py` con `MenuOpcion`, etc.) para poder diffear contra
  el repo fuente fácilmente; usar inglés en los módulos nuevos (`organizations`, `teams`, `bot`).

## 10. Plan de construcción por fases (para ir por partes)

Cada fase debe cerrar con: contenedores levantando con `docker-compose up`, healthchecks en verde,
y los tests del servicio tocado en verde. No avanzar a la fase siguiente sin esto.

### Fase 0 — Esqueleto y compose
- Crear la estructura de carpetas de la sección 6.
- `docker-compose.yml` con los 6 servicios + `db` + los 2 frontends (webchat con `profiles`).
- Cada servicio backend responde `GET /health` con `200 {"status": "ok"}`.
- `services/db/init-schemas.sql` crea los 6 esquemas.

### Fase 1 — Core: organizaciones, usuarios, roles, equipos
- Modelos `Organization`, `User` (rol), `Team` en `services/core`.
- Login JWT (`POST /api/auth/login/`) con `org_id`/`rol` en el payload.
- Endpoints DRF de alta/edición de usuarios y equipos, con permisos por rol (solo Admin gestiona).
- Admin Panel (React): pantalla de login + ABM de usuarios/equipos.

### Fase 2 — Portar menú y horarios (multi-tenant)
- Traer `MenuOpcion`, `HorarioAtencion`, `DiaExcepcional`, `Conversacion`, `ConversacionLog`,
  `horarios.py`, `defaults.py`, `feriados_client.py` desde `garzamorada/chatbot` a `services/core`.
- Agregar `organization` FK donde corresponda (sección 5) y FK a `Team` en nodos `DERIVACION`.
- Migrar y adaptar los tests existentes del repo — deben seguir pasando.
- Portar el editor visual del árbol y la grilla de horarios (templates Django), filtrados por
  organización. Enlazarlos desde el Admin Panel (SSO/redirect con el mismo JWT/sesión).
- Endpoint `GET /api/core/teams/{id}/horario-habil/`.

### Fase 3 — Channel Gateway + integración WhatsApp
- Embedded Signup, recepción y verificación de webhooks (`X-Hub-Signature-256`), envío de
  mensajes salientes contra la Graph API de Meta.
- Endpoint `POST /api/core/bot/mensaje-entrante/` en Core (usa el árbol de menú portado en Fase 2
  para decidir la respuesta) — Channel Gateway lo consume por cada mensaje entrante.
- Los menús se mandan a WhatsApp como `interactive` (list/button, ver sección 4.1.1), nunca como
  texto numerado plano salvo que se salga de los límites de la Graph API — la traducción
  `opciones` → `interactive` vive en Channel Gateway, no en Core.
- El marcado neutro de negrita/cursiva/tachado/monoespaciado (sección 4.1.2) se traduce a la
  sintaxis real de WhatsApp al armar cada mensaje saliente.

### Fase 4 — Conversation Engine (post-derivación)
- `OperatorSession`, asignación round-robin dentro del `Team` indicado por el nodo `DERIVACION`.
- WebSocket para entrega en tiempo real.
- Límite de conexiones simultáneas por organización (consultando el plan en Core).

### Fase 5 — Operators Desk Service + Operators Desk Web
- BFF que compone Core (historial/tags/datos transaccionales) + Conversation Engine (asignación/
  tiempo real) para la bandeja y el hilo de conversación.
- Frontend React: bandeja, hilo, responder/derivar/etiquetar/cerrar.

### Fase 6 — App móvil Android
- Mismo contrato de API que Operators Desk Service (sección 3.2): login, bandeja, hilo, acciones.

### Fase 7 — Analytics Service
- Usuario de solo lectura contra los esquemas `core`/`conversation_engine`.
- Reportes de volumen, tiempos de respuesta, uso de menú; export CSV.
- Sección de reportes en el Admin Panel para el rol Data Manager.

### Fase 8 — QA end-to-end, hardening y despliegue
- Caso de prueba de aislamiento multi-tenant (un usuario de la Organización A no debe poder leer
  nada de la Organización B, en ningún servicio).
- Prueba de carga básica sobre Conversation Engine (latencia de WebSocket).
- Revisión de que ningún servicio quedó con lógica de negocio que debería estar en Core.

### Fase 9 (fast-follow, no iniciar sin pedido explícito)
- Messenger e Instagram en Channel Gateway.
- Webchat Service completo (hoy es un stub).
- Push notifications en background (FCM) para la app Android.
- Editor de menú con capturas de datos / autorespuesta por palabra clave libre.

## 11. Explícitamente fuera de alcance ahora

No implementar salvo pedido explícito: Messenger, Instagram, Webchat Service (más allá del stub),
bus de eventos (Kafka/RabbitMQ), cache distribuida (Redis), búsqueda con Elasticsearch,
almacenamiento tipo S3, notificaciones push en background, editor de menú con nodos de captura de
datos o autorespuesta libre, versionado histórico de menús, panel de auditoría dedicado (más allá
de `ConversacionLog`), API Gateway dedicado.

## 12. Preguntas abiertas a resolver antes o durante la Fase 1

- Mecanismo exacto de validación de JWT entre servicios: ¿secreto compartido (HS256, más simple)
  o clave pública/privada (RS256, más seguro pero un endpoint más en Core)? Definir en Fase 0.
- ¿El usuario de PostgreSQL de cada servicio tiene su propio esquema con permisos acotados
  (`SET search_path`) o se usan bases lógicamente separadas dentro de la misma instancia? Definir
  en Fase 0 junto con `init-schemas.sql`.
- ¿Operators Desk Web y Admin Panel son dos proyectos React separados (como está en la sección 6)
  o un único proyecto con rutas/roles distintos? Se recomienda separados para no mezclar permisos
  de configuración con permisos de atención, pero es una decisión abierta de bajo costo de cambiar.
