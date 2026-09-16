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
| 2 | **Channel Gateway Service** | `services/channel-gateway` | FastAPI + PostgreSQL | 8002 | Messenger e Instagram YA implementados: recepción/verificación de webhooks de Meta, envío de mensajes salientes vía Graph API. Sin lógica de negocio propia — pide `api_key`/`webhook_secret` a Core por canal (endpoint interno autenticado con `ServiceToken`, ver sección 9). WhatsApp (Embedded Signup + Cloud API) queda pendiente, es más complejo. |
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
- WhatsApp/Messenger/Instagram: **sin modelos propios** — no guarda su propia copia de `api_key`/
  `telefono_id`/`webhook_secret`, los pide a Core en cada request vía `GET /api/core/internal/
  canales/<uuid>/` (autenticado con `Authorization: Service-Token <token>`, ver sección 9 "Tokens
  de servicios internos"). El `<uuid>` es el mismo `Canal.uuid` de Core.
- Endpoints reales, hoy: `GET/POST /webhooks/{whatsapp|messenger|instagram}/{canal_uuid}` (handshake
  de verificación + recepción/verificación de firma + normalización), `POST /messages/send` (envío
  saliente contra la Graph API/Cloud API, usando la `api_key`/`telefono_id` de ese canal — protegido
  con `Service-Token`, ver más abajo). `POST /channels/whatsapp/embedded-signup/callback` (Embedded
  Signup) sigue pendiente.
  - **Meta sólo deja UNA Callback URL por app, no una por canal** — un detalle real del dashboard
    de Meta que el diseño original (tres URLs, una por tipo) no tenía en cuenta. En la práctica, si
    el Admin usa la URL de Messenger para las tres suscripciones (Página/Instagram/WhatsApp
    Business Account), un evento de Instagram real puede llegar a la URL "de Messenger". Por eso el
    tipo de la URL (`canal_tipo_url`) NUNCA se usa para rechazar un payload — el tipo real sale del
    campo `payload["object"]` (`"page"`/`"instagram"`/`"whatsapp_business_account"`), y si no
    coincide con el canal de la URL, se busca el canal "hermano" de la misma organización vía
    `GET /api/core/internal/canales/organizacion/<organization_id>/<tipo>/` (`channels.views.
    InternalCanalPorOrganizacionView`, mismo esquema de auth). El handshake `GET` no necesita esto
    (Meta no manda ningún indicador de tipo ahí) — sólo verifica el secreto del canal de la URL, sea
    cual sea. El Admin Panel (`ChannelsPage.tsx`, modal "Datos del webhook") avisa esto explícitamente:
    usar la misma URL/secreto para las tres suscripciones en el dashboard de Meta.
  - **Menú real, no un acuse de recibo fijo**: cada mensaje de texto normalizado (incluida una
    respuesta de lista/botón nativo de WhatsApp, normalizada al mismo `id` que si se hubiera tipeado
    el número) se manda a `POST /api/core/bot/mensaje-entrante/` (`core_client.
    enviar_mensaje_entrante`) — Core recorre el árbol de `MenuOpcion` de verdad (ver
    `conversations.menu_engine` en la sección 9) y devuelve las acciones (`enviar_texto`/
    `mostrar_menu`) para ejecutar. Si Core no contesta, no se manda nada — el mensaje ya quedó
    recibido y logueado del lado de Meta (200), no hace falta reintentar.
  - **Selección nativa por canal (sección 4.1.1)**: `meta_client.enviar_menu_por_canal` decide el
    widget según `canal.tipo` y la cantidad de opciones — WhatsApp con 1-3 opciones manda
    `interactive.type=button`, con 4-10 manda `interactive.type=list` (`body` = el texto CON el
    listado numerado, no sólo el saludo — las opciones tienen que verse como texto además del
    selector táctil), fuera de ese rango o para Messenger/Instagram (todavía sin su propia
    traducción a quick replies) cae al texto plano numerado que Core ya arma como fallback
    universal. Si el envío de una acción falla (ej. `api_key` vencida), sólo se loguea — Meta ya
    recibió su 200 igual, para no generar reintentos del mismo webhook.
  - **`POST /messages/send` requiere autenticación interna** (`app/internal_auth.py::
    requerir_servicio_interno`, header `Authorization: Service-Token <token>` contra el mismo
    `CORE_SERVICE_TOKEN` que este servicio ya usa para autenticarse CONTRA Core) — a diferencia de
    `/webhooks/*` (público a propósito, lo llama Meta), este endpoint sólo debería poder llamarlo
    OTRO servicio interno (Conversation Engine, Fase 4, todavía no existe). Se agregó después de
    notar que quedaba expuesto sin auth en el dominio público del túnel de Cloudflare
    (`webhooks.udcchat.com.ar` reenvía TODO el hostname a `channel-gateway:8000`, no sólo `/webhooks/
    *` — la regla de ingreso en el dashboard de Cloudflare debería restringirse a ese path si se
    quiere cerrar esto del todo; ver sección "Cloudflare Tunnel" más abajo).

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

- **Autenticación**: Core (Django) emite JWT (`djangorestframework-simplejwt`, RS256) con `org_id`
  y `grupos` (lista, no un `rol` singular) en el payload. Todos los servicios FastAPI validan ese
  mismo JWT contra la clave pública publicada en `/api/auth/jwks/`.
- **Scoping multi-tenant**: cada request autenticado trae `org_id` en el token; todo query
  filtra por ese `org_id`. En Django, `common.viewsets.OrganizationScopedModelViewSet` lo hace
  solo para no repetir el filtro a mano en cada vista.
- **Autorización (permisos)**: no hay un campo `role` en `User` — los permisos vienen enteramente
  de grupos de Django (`user.groups`, M2M: un usuario puede estar en más de uno a la vez). Cada
  ViewSet de Core usa `common.permissions.StrictDjangoModelPermissions` (una `DjangoModelPermissions`
  extendida para que GET también exija `view_<modelo>`, no sólo las escrituras), así "cada vista
  tiene su permiso correspondiente" sin excepciones; las `@action` que no mapean 1 a 1 a un CRUD
  (`tree`, `reordenar`, `grilla`) llaman a `common.permissions.require_perm(request, "app.codename")`
  a mano. Los 5 grupos y qué permiso Django tiene cada uno están en
  `services/core/users/group_permissions.py` (única fuente de verdad, la usan tanto el management
  command `setup_groups` como los tests):

  | Grupo | Alcance |
  |---|---|
  | `superusuarios` | Staff de plataforma (`/admin/` y, si además tiene `is_superuser=True` real de Django, la sección "Plataforma" del Admin Panel — ver `IsPlatformSuperuser`). Gestiona organizaciones (con sus límites de uso), las cuentas de cualquier organización, los tokens de comunicación entre los propios microservicios del proyecto, y ve estadísticas/salud generales del sistema. |
  | `administradores` | Sólo desde el Admin Panel (React). Gestiona usuarios, equipos y permisos (grupos) de su propia organización, y configura el chatbot (menú + horarios + mensajes + modo de atención con/sin menú), el catálogo de etiquetas de conversación (por organización y por equipo, colores incluidos) y la api key/estado/chequeo de salud de cada canal de mensajería. |
  | `encargados_difusion` | NINGÚN permiso sobre Core — Core es sólo su API de autenticación (login, recuperar usuario/contraseña, "mi perfil"); campañas de difusión, templates y listas, estadísticas de envíos son de su propio panel cuando exista esa app (Fase 7+), no del Admin Panel de Core. |
  | `analistas_datos` | NINGÚN permiso sobre Core — mismo motivo que `encargados_difusion`; reportes de conversaciones/agentes/contactos, exportar CSV, son de Analytics (Fase 7), no del Admin Panel de Core. |
  | `operadores` | NINGÚN permiso sobre Core — mismo motivo; sólo su perfil y recuperar usuario/contraseña. Ver/responder chats sin asignar o de sus equipos/a ellos mismos, aplicar/quitar etiquetas de una conversación, respuestas predefinidas, observaciones obligatorias al resolver/pausar y derivar son de Operators Desk, Fase 4/5, todavía no implementado (ver sección 11). |

  El frontend nunca decide qué mostrar/ocultar mirando un nombre de rol o de grupo: `GET
  /api/core/users/me/` devuelve `permissions` (la lista real de `user.get_all_permissions()`) y
  `groups` (para mostrar la etiqueta), y el Admin Panel arma la UI a partir de esa lista
  (`frontend/admin-panel/src/auth/permissions.ts::hasPerm`) — la fuente de verdad de "qué se
  puede hacer" es siempre el backend, nunca un `if (rol === "admin")` en React.
- **Seguridad del login** (`authentication` app):
  - **Bloqueo por IP**: 3 fallas de login seguidas desde la misma IP la bloquean 12hs
    (`authentication.models.LoginLockout`, un registro por IP — no por cuenta). La IP se lee de
    `X-Forwarded-For` (`authentication.utils.get_client_ip`), no de `REMOTE_ADDR`, porque nginx
    hace de proxy delante de gunicorn. Un login exitoso resetea el contador. `POST
    /api/auth/login/` devuelve 429 con `blocked_until` mientras dure el bloqueo. Como no depende
    de ninguna organización (una IP puede tocar cuentas de cualquier org), el desbloqueo se
    gestiona desde `/admin/` (grupo `superusuarios`, acción "Desbloquear" en `LoginLockoutAdmin`),
    no desde el Admin Panel de una organización puntual.
  - **Recuperar contraseña**: `POST /api/auth/password-reset/` (siempre responde el mismo mensaje
    genérico, exista o no la cuenta, para no filtrar qué emails están registrados) manda un link
    con un token de un solo uso (`PasswordResetTokenGenerator` de Django) a
    `{FRONTEND_URL}/restablecer-contrasena/<uid>/<token>`; `POST /api/auth/password-reset-confirm/`
    lo valida y cambia la contraseña. El email sale por `EMAIL_BACKEND` — en dev es el backend
    "console" (el link queda en `docker compose logs core`, no se manda de verdad); para producción
    hay que pasar a `EMAIL_BACKEND=...smtp.EmailBackend` y completar `EMAIL_HOST`/`EMAIL_HOST_USER`/etc.
  - **Recuperar usuario**: como acá el "usuario" es directamente el email (no hay un `username`
    separado), `User.dni` (opcional, único) es el dato que permite recuperarlo:
    `POST /api/auth/username-reset/` recibe un DNI y, si coincide con una cuenta, le manda **a esa
    cuenta** su propio email registrado (nunca lo devuelve en la respuesta) — mismo patrón
    anti-enumeración que el reset de contraseña, mensaje genérico siempre. `/olvide-usuario` en el
    Admin Panel es el formulario correspondiente.
  - **Perfil personal**: todo usuario edita sus propios `first_name`/`last_name`/`email`/`dni`/
    `avatar` con `PATCH /api/core/users/me/` (`MyProfileSerializer` — nunca toca grupos ni
    organización, eso sigue siendo sólo de un Admin vía `UserSerializer`). El avatar se sube ya
    recortado en cuadrado desde un editor de centrado/zoom sin librerías externas
    (`frontend/admin-panel/src/components/AvatarCropper.tsx`: arrastrar para centrar, control de
    zoom, recorte final con `<canvas>`); Core genera con Pillow una miniatura de 150x150
    (`User._regenerar_avatar_thumbnail`, campo `avatar_thumbnail`) para no bajar la imagen completa
    en listados (tabla de Usuarios, avatar del topbar) — la imagen grande sólo se pide en la propia
    página de perfil. Reemplazar el avatar borra el archivo anterior en vez de acumular huérfanos.
  - **Reset de contraseña por un Admin**: `POST /api/core/users/{id}/reset-password/`
    (`users.change_user`, scopeado a la propia organización igual que cualquier otro detalle del
    ViewSet) genera una contraseña temporal aleatoria y la devuelve **una sola vez** en la
    respuesta — no se guarda en texto plano en ningún lado — para que el Admin se la pase al
    usuario por otro medio. Marca `User.must_change_password=True`; el Admin Panel lo obliga a
    pasar por `/cambiar-contrasena` (`POST /api/core/users/me/cambiar-password/`, pide la actual)
    antes de dejarlo usar el resto del panel (`ProtectedRoute` redirige si `me.must_change_password`).
- **Archivos servidos por Core (`/media/`)**: `avatar`/`avatar_thumbnail` (y cualquier `ImageField`/
  `FileField` futuro) se devuelven como **URL absoluta** (`request.build_absolute_uri`), nunca la
  ruta relativa de `FieldFile.url` — el Admin Panel corre en otro origen/puerto que Core
  (`VITE_CORE_API_URL`), así que una ruta relativa se resolvería contra el propio Admin Panel y
  rompería la imagen. Ojo con nginx delante de gunicorn: `proxy_set_header Host $host;` **no**
  incluye el puerto (a diferencia de `$http_host`), así que Django terminaba viendo el request como
  si hubiera llegado a `localhost` sin puerto y armaba URLs rotas (`http://localhost/media/...` en
  vez de `http://localhost:8001/media/...`) — arreglado en `services/core/docker/nginx.conf` usando
  `$http_host`. `MEDIA_URL` también tiene que tener `/` inicial (`"/media/"`, no `"media/"`) para que
  `build_absolute_uri` resuelva contra la raíz del host y no contra el path del request actual.
  Aparte, `/app/mediafiles` (avatares subidos por usuarios) tiene que estar en un volumen nombrado
  (`media_files:` en `docker-compose.yml`), no sólo en la capa escribible del contenedor — a
  diferencia de `/app/staticfiles` (se regenera solo con `collectstatic` en cada arranque,
  `entrypoint.sh`), un avatar subido no se puede regenerar si se pierde al recrear el contenedor.
- **Contratos entre servicios**: OpenAPI autogenerado (DRF + FastAPI). Antes de que un servicio
  FastAPI consuma un endpoint de Core que no existe todavía, crearlo primero en Core (Core nunca
  debe ser bloqueado por otro servicio).
- **Testing**: cada servicio con su propia suite (`pytest`/`pytest-django`). Los tests portados de
  `garzamorada/chatbot` se migran junto con el código como red de seguridad del refactor
  multi-tenant — no se descartan. La suite de Core ya cubre aislamiento multi-tenant, permisos por
  grupo, el árbol de menú, horarios/días excepcionales y el login (incluido el bloqueo por IP y el
  reset de contraseña) — correrla con `docker compose run --rm --entrypoint python core manage.py test`.
  Ojo al testear cosas basadas en throttling (`ScopedRateThrottle`): el cache de Django no se
  resetea entre tests como la base de datos, así que hay que limpiarlo a mano
  (`django.core.cache.cache.clear()`) en el `setUp` de esos tests o un test contamina al siguiente.
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

**Implementado** (con algunos cambios respecto al enunciado original, ver sección 9):
- `role` terminó siendo grupos de Django (M2M, sección 9) en vez de un campo único — un usuario
  puede estar en más de un grupo. Los 5 grupos y sus permisos: `users/group_permissions.py`.
- Login: además del camino feliz, tiene bloqueo por IP (3 fallas → 12hs), recuperar contraseña por
  email (token de un solo uso), pantalla informativa de "recuperar usuario", reset de contraseña
  por un Admin (contraseña temporal + `must_change_password` obligatorio en el próximo ingreso) —
  todo detallado en la sección 9.
- Admin Panel: ABM de usuarios con selector de grupos (checkboxes, no un `<select>` de un solo
  rol) y botón "Resetear contraseña"; ABM de equipos.
- Organización de demo **UCD** (`python manage.py seed_ucd_demo`, idempotente): 3 equipos, un
  usuario por cada uno de los primeros 3 grupos y 5 agentes repartidos en los equipos — útil para
  probar el sistema de permisos de punta a punta sin cargar datos a mano.

### Fase 2 — Portar menú y horarios (multi-tenant)
- Traer `MenuOpcion`, `HorarioAtencion`, `DiaExcepcional`, `Conversacion`, `ConversacionLog`,
  `horarios.py`, `defaults.py`, `feriados_client.py` desde `garzamorada/chatbot` a `services/core`.
- Agregar `organization` FK donde corresponda (sección 5) y FK a `Team` en nodos `DERIVACION`.
- Migrar y adaptar los tests existentes del repo — deben seguir pasando.
- Portar el editor visual del árbol y la grilla de horarios (templates Django), filtrados por
  organización. Enlazarlos desde el Admin Panel (SSO/redirect con el mismo JWT/sesión).
- Endpoint `GET /api/core/teams/{id}/horario-habil/`.

**Implementado** — el editor visual del árbol y la grilla de horarios se rehicieron en React (no
son templates Django con SSO, esa idea se descartó a favor de una sola UI en el Admin Panel):
- **Menú**: árbol con reordenar/reparentar por drag-and-drop (mismo concepto que
  `chatbot_menu.js`/`_menu_tree.html` del repo origen), acción `reordenar` en el back. Cada
  opción de tipo Respuesta se edita con `MessageEditor` (barra de negrita/itálica/tachado/
  monoespaciado + selector de emojis + botones para insertar variables — mismo concepto que
  `chatbot_wa_editor.js` del repo origen, sintaxis neutra de la sección 4.1.2 en vez de la
  literal de WhatsApp). A la derecha del árbol y en cada modal de edición hay una vista previa
  tipo chat (`components/WhatsAppPreview.tsx`, mockup genérico de teléfono + burbujas): la del
  costado es **navegable** (clickeás una opción como lo haría un contacto real, entra a
  submenús, muestra la respuesta/derivación/despedida).
- **Horarios semanal**: grilla pintable por click-y-arrastre igual que `lista_horarios.html`,
  más un panel a la derecha con la vista previa de los 7 días (resumen de rangos horarios) —
  clickear un día ahí resalta su columna en la grilla. Además del pintado por click-y-arrastre
  (bueno para horarios irregulares), hay un selector rápido de rango (día + desde + hasta +
  "Marcar horario"/"Marcar cerrado") para no tener que arrastrar celda por celda en tramos largos y
  regulares — combinable con "Copiar Lunes a Martes-Viernes".
- **Días excepcionales**: en vez de un rango desde/hasta, se edita **un día específico** por vez
  (input de fecha o clickeando el almanaque a la derecha); el tipo de día es una botonera
  (Normal/Horario reducido/Feriado/Asueto) en vez de un `<select>`. El catálogo compartido de
  feriados nacionales se sincroniza solo al entrar a la sección (año actual + siguiente,
  `POST /api/core/dias-excepcionales/sincronizar-feriados/`) — antes había que correr el
  management command a mano. Si el día seleccionado ya es un feriado del catálogo compartido, el
  editor lo muestra (tipo + qué se celebra) con una nota de que guardar crea una excepción propia
  de la organización para esa fecha. Debajo del almanaque, listado de próximos días no laborables.
  El horario reducido de un día puntual tiene el mismo selector rápido de rango que la grilla
  semanal (desde/hasta + Marcar horario/Marcar cerrado).
- **Mensajes predeterminados** (`bot_settings` app, nueva — no estaba en el enunciado original de
  esta fase pero es parte natural de "configurar el chatbot"): un `BotMessages` por organización
  con los 8 textos configurables (bienvenida, saludos, despedida, derivación, cierre por
  inactividad, saludo del operador al tomar la conversación) + 2 parámetros numéricos. Mismos
  `MessageEditor` + vista previa tipo chat que el menú. El campo `mensaje_operador_toma` es un
  caso particular: a diferencia de todos los demás, ahí `{nombre}` es el nombre del **operador**
  (no el del contacto) — default: "Hola, mi nombre es {nombre}. ¿En qué puedo ayudarte hoy?". Es
  sólo la configuración del texto; sugerírselo al operador al marcar una conversación como
  "tomada" (o mandarlo solo) es Operators Desk, Fase 4/5 — todavía no implementado, igual que el
  resto del flujo de conversaciones.
- **Catálogo de etiquetas de conversación** (`tags` app, nueva — sólo la parte de configuración;
  ver el resto de la consigna, deferido, en la Fase 4/5 de abajo): modelo `Etiqueta` con
  `organization` obligatoria. Dos orígenes automáticos, ninguno editable a mano por un Admin más
  allá del color: las 7 etiquetas de estado que pide la consigna (`pendiente`, `asignada`,
  `tomada`, `en_proceso`, `en_pausa`, `rechazado`, `resuelto`, `es_sistema=True`, identificadas por
  `codigo`) y **una etiqueta por cada equipo** ("cada equipo es una etiqueta" — `team` es un
  `OneToOneField` a `Team`, el nombre se sincroniza solo si renombrás el equipo y se borra sola en
  cascada si borrás el equipo); ambas se autogeneran/sincronizan la primera vez que se lista el
  catálogo (`defaults.asegurar_etiquetas_sistema` / `asegurar_etiquetas_equipo`) y no se pueden
  borrar ni renombrar, sólo recolorear. Todas las demás etiquetas las arma un Admin a mano y son
  siempre **generales** (`team=None`) — no existe la opción de asignarles un equipo, `team` es de
  sólo lectura en `EtiquetaSerializer`. Permisos: `tags.add_/change_/delete_/view_etiqueta` para
  administradores — `operadores` ya no tiene ningún permiso sobre Core (ver sección 9), aplicar
  etiquetas es Operators Desk (Fase 4/5), su propio panel, no el Admin Panel de Core. `?team=<id>`
  filtra el catálogo por equipo. El color se valida como hexadecimal
  (`#RRGGBB`). Admin Panel: página "Etiquetas" (`frontend/admin-panel/src/pages/TagsPage.tsx`) con
  dos grupos — generales y de equipo, edición 100% en línea (sin modal: cada fila es su propio
  formulario, un encabezado de columnas por grupo en vez de repetir la etiqueta de cada campo por
  fila), selector de color con swatch + hex a mano, y color de fuente (blanco/negro) con vista
  previa en la propia letra. **Colores por default del proyecto para una etiqueta nueva**:
  `color="#3454D1"` (el primario de la marca) y `color_texto="#FFFFFF"` — mismo valor en los 3
  lugares donde se puede crear una etiqueta sin elegir color a mano: `Etiqueta.color`/`color_texto`
  (alta directa por API/admin/shell), `tags/defaults.py::COLOR_EQUIPO_DEFAULT` (etiquetas de equipo
  autogeneradas) y el estado inicial de `TagCreateRow` en el Admin Panel — si se cambia la
  preferencia, actualizar los tres para que no queden inconsistentes entre sí.
- **Modo de atención (`bot_settings.BotMessages.menu_activo`)**: booleano, default `True`. Apagado
  = no se usa el árbol de menú (ni sus saludos de sección `saludo_inicial`/`saludo_area` ni la
  derivación por opción elegida `derivacion_texto`/`derivacion_mensaje`/`mensaje_cierre_inactividad`)
  — pero no es "nada": hay un estado intermedio. El contacto sigue recibiendo el mensaje de
  bienvenida (`mensaje_bienvenida`) y, sin nada en el medio, la conversación queda directamente en
  la bandeja sin asignar para que cualquier operador la tome; al cerrarla se sigue mandando el
  mensaje de despedida (`mensaje_despedida`); y el saludo del operador al tomar la conversación
  (`mensaje_operador_toma`) se usa siempre, tenga el menú activado o no — estos tres campos viven
  fuera del bloque atenuado en el form. Sólo la configuración por ahora (botonera "Usar menú del
  bot"/"Directo a operadores" arriba de todo en `/mensajes`, con los campos propios del menú
  agrupados aparte y atenuados cuando está apagado, más la vista previa mostrando siempre
  bienvenida → [menú o nota de "bandeja sin asignar"] → saludo del operador → despedida) —
  aplicarlo de verdad (que Channel Gateway/Conversation Engine salgan del flujo del bot) es
  Fase 3/4, todavía no implementado.
- **Canales de mensajería** (`channels` app, nueva — la app se llama `channels` pero el modelo es
  `Canal`, cuidado con el módulo de terceros `django-channels` si algún día se instala, no debería
  chocar porque no está en requirements pero mantenerlo en mente): api key y estado (activo/
  inactivo) de los 4 canales que documenta la sección 3 (WhatsApp/Messenger/Instagram/Webchat), MÁS
  `uuid` y `webhook_secret` (nuevos, ver más abajo). Un `Canal` por `(organization, tipo)` se
  autogenera al listar (`defaults.asegurar_canales`) — no se crean ni se borran por API (ningún
  grupo tiene `add_canal`/`delete_canal` a propósito, `StrictDjangoModelPermissions` los bloquea
  con 403), sólo se edita `api_key`/`activo` de los 4 que ya existen. `api_key` es write-only: la
  API nunca la devuelve, sólo `api_key_configurada` (bool) y `api_key_preview` (últimos 4
  caracteres, ej. `"••••3f9a"`) — alcanza para confirmar que se cargó la correcta sin volver a
  mostrarla. La copia cifrada en reposo (encriptar `api_key` en la propia base, no sólo ocultarla de
  la respuesta de la API) sigue pendiente.
  - **Webhook por canal (`uuid` + `webhook_secret`, Messenger/Instagram/WhatsApp — no Webchat, ver
    `Canal.TIPOS_CON_WEBHOOK_META`)**: a diferencia de `api_key` (una credencial que el Admin trae
    de afuera), estas dos las genera CORE al crear el canal (`channels.defaults.asegurar_canales`,
    `secrets.token_urlsafe(24)`) — Channel Gateway sólo las lee, nunca las crea, mismo criterio que
    `ServiceToken`. `uuid` (no el `id` autoincremental, para no exponer un correlativo adivinable en
    una URL pública) arma la URL de entrada del webhook en Channel Gateway:
    `CanalSerializer.webhook_url` = `f"{CHANNEL_GATEWAY_PUBLIC_URL}/webhooks/{tipo.lower()}/{uuid}/"`
    (`CHANNEL_GATEWAY_PUBLIC_URL`, nuevo setting en `config/settings.py`, default
    `http://localhost:8002` en dev). `webhook_secret` SÍ se devuelve completo por la API (única
    excepción al patrón preview/masked de acá arriba) — el Admin lo tiene que poder copiar entero
    para pegarlo en la configuración del webhook de la app de Meta; se puede rotar con
    `POST /api/core/canales/{id}/regenerar-webhook-secret/` (mismo criterio que
    `ServiceTokenViewSet.generar`, invalida el anterior). Frontend: botón "Datos del webhook" en
    `ChannelsPage.tsx` (`WebhookModal`) para Messenger/Instagram/WhatsApp, con copiar URL/secreto y
    regenerar.
    - **`http://localhost:8002` no es alcanzable por Meta** — para que `webhook_url` sirva de
      verdad hace falta un dominio propio con HTTPS público apuntando a `channel-gateway:8000`. El
      servicio `cloudflared` en `docker-compose.yml` (imagen oficial `cloudflare/cloudflared`,
      perfil `tunnel` — no arranca por defecto, `docker compose --profile tunnel up -d cloudflared`)
      resuelve esto sin IP pública ni abrir puertos: túnel "remotely-managed" de Cloudflare, un solo
      `CLOUDFLARE_TUNNEL_TOKEN` en `.env` (se crea en el dashboard de Cloudflare Zero Trust, Networks
      > Tunnels), el ruteo hostname → servicio se configura ahí mismo (Public Hostname → `http://
      channel-gateway:8000`), no en este repo. Una vez armado, actualizar `CHANNEL_GATEWAY_PUBLIC_
      URL` al dominio real para que `webhook_url` deje de mostrar localhost.
  - **Chequeo de salud real** (`POST /api/core/canales/{id}/verificar/`, `channels/health.py`): no
    es un simulacro — para WhatsApp/Messenger/Instagram (los 3 sobre la Graph API de Meta) pega de
    verdad a Meta y guarda el resultado (`ultimo_chequeo_at/ok/detalle`). **WhatsApp y Messenger/
    Instagram usan nodo y autenticación DISTINTOS** (bug real, confirmado en producción
    2026-09-16: dos canales 100% funcionales — mandaban/recibían mensajes sin problema — aparecían
    "sin conexión" acá por chequearse mal, no por estar realmente caídos):
    - **WhatsApp**: un token de System User de la Cloud API casi nunca puede resolver `/me` (Meta
      responde `"Unsupported get request..."` aunque el token mande mensajes perfecto por
      `/<phone_number_id>/messages`). Se verifica contra el propio `phone_number_id`
      (`Canal.telefono_id`) con el token en el header `Authorization: Bearer` — mismo nodo y
      autenticación que el envío real (`channel-gateway/app/meta_client.py`).
    - **Messenger/Instagram**: un Page Access Token con sólo `pages_messaging` (lo mínimo que hace
      falta para mandar mensajes) tampoco puede leer `/me` (Meta pide `pages_read_engagement`, un
      permiso que ese token no tiene por qué tener). Se verifica con `/debug_token`, autenticado
      con las credenciales de la APP (`META_APP_ID`/`META_APP_SECRET`) en vez del token del canal
      — el mecanismo que la propia Graph API documenta para validar un token sin depender de sus
      permisos puntuales (`is_valid`/`scopes`/`expires_at`).

    Ninguno de los dos valida permisos de envío más allá de lo mínimo que ya exige el nodo/
    mecanismo consultado — el envío/recepción real de mensajes (Messenger/Instagram) es Channel
    Gateway (sección 4.2), no esto. Webchat no tiene un servidor de terceros que consultar (sería
    el propio Webchat Service, Fase 9, sin construir) — el chequeo ahí devuelve
    `ultimo_chequeo_ok=None` ("No aplica") en vez de intentar una conexión que no existe. Esta
    action tiene su propio `get_permissions()` (sólo pide `IsAuthenticated` + `require_perm`
    manual a `channels.change_canal`) porque `StrictDjangoModelPermissions` mapea POST →
    `add_canal`, que nadie tiene — sin ese override, hasta un Admin real quedaría bloqueado con 403
    al intentar verificar. En los tests, `requests.get` va siempre mockeado
    (`channels.tests.CanalVerificarWhatsappTests`/`CanalVerificarMessengerTests`) — la suite nunca
    pega de verdad a Meta.
- **Sección "Plataforma" del Admin Panel** (sólo el superusuario real de plataforma — ver
  `IsPlatformSuperuser` más abajo): organizaciones (con sus límites de uso), usuarios de TODAS las
  organizaciones, tokens para la comunicación ENTRE los propios microservicios del proyecto,
  estadísticas de uso de Core y salud general de las APIs externas, y manuales/referencia de la API
  interna. Nada de esto es org-scoped — a propósito es la excepción multi-tenant del sistema.
  - **`common.permissions.IsPlatformSuperuser`**: el gate real de todo lo de acá abajo. Los
    permisos Django estándar (`organizations.view_organization`, `users.view_user`, etc.) NO
    alcanzan para esto porque `administradores` tiene exactamente esos mismos permisos para su
    propia organización — no hay forma de que un único código de permiso ("puede ver
    organizaciones") signifique "todas" para un grupo y "la mía" para otro. La distinción real es
    `request.user.is_superuser` (el flag real de Django, no el grupo "superusuarios") + sin
    `organization` — la MISMA cuenta que, por ese mismo motivo (sin `organization`), queda afuera
    de `OrganizationScopedModelViewSet` (ver más abajo, "Endurecimiento"): un superusuario real es
    a la vez "adentro" de `IsPlatformSuperuser` (gestiona toda la plataforma) y "afuera" de
    cualquier organización puntual (no gestiona la de ninguna en particular), nunca las dos cosas
    mezcladas para el mismo recurso. El grupo "superusuarios" sigue existiendo y sigue teniendo sus
    permisos Django estándar (por si algún día hace falta un
    staff sin `is_superuser=True` real) pero las vistas de "Plataforma" no los consultan en
    absoluto — sólo miran el flag. Por eso `seed_ucd_demo` ahora crea/actualiza
    `superusuario@ucd.demo` con `is_staff=True` **e** `is_superuser=True` (antes sólo
    `is_staff=True`, deliberadamente) — `_get_or_create_user` se ajustó para sincronizar esos flags
    también en una cuenta de demo que ya existía, no sólo al crearla, porque `get_or_create` con
    `defaults` no toca un registro preexistente.
  - **Organizaciones** (`organizations.PlatformOrganizationViewSet`, ruta
    `/api/core/plataforma/organizaciones/`): alta/edición de nombre/slug/plan y sus 3 límites de
    uso, todos `PositiveIntegerField` con **default `0` = sin límite**: `connection_limit` (ya
    existía como "límite de conexiones simultáneas de operadores", pasó de default `5` a default
    `0` con esta semántica explícita), `user_limit` (nuevo) y `monthly_conversation_limit` (nuevo).
    Ninguno de los 3 se aplica todavía de verdad (0 usuarios rechazados, 0 conversaciones
    cortadas) — son sólo el tope configurado, a la espera de Conversation Engine (Fase 4) y de que
    la creación de usuarios chequee el límite. `OrganizationSerializer` (el que usa
    `MyOrganizationView`, self service de cada Admin) sigue siendo de sólo lectura para estos
    campos — sólo `PlatformOrganizationSerializer` los expone editables.
  - **Usuarios de todas las organizaciones** (`users.PlatformUserViewSet`, ruta
    `/api/core/plataforma/usuarios/`, filtro `?organization=<id>` o `?organization=null` para las
    cuentas de plataforma): mismo ABM que `UserViewSet` (que cada Admin usa para la propia) pero sin
    scoping y con `organization` editable en el body — el superusuario elige a qué organización
    pertenece cada usuario. `PlatformUserSerializer` extiende `UserSerializer` agregando
    `organization_name` (sólo lectura, evita que el Admin Panel tenga que cruzar con el listado de
    organizaciones nada más que para mostrar el nombre en una tabla). El Admin Panel
    (`PlatformUsersPage.tsx`) NO usa un filtro de organización sobre una tabla plana — pide el
    listado completo sin filtro y lo agrupa en el cliente (`agruparPorOrganizacion`), una sección
    por organización (encabezado + su propia tabla) más una última sección "cuentas de plataforma"
    si hay alguna sin organización; una caja de búsqueda por email/nombre filtra dentro de esas
    mismas secciones agrupadas, nunca las deshace.
  - **Soft delete de organizaciones y usuarios** (`common/soft_delete.py`: `marcar_eliminado`/
    `restaurar_eliminado`, dos funciones de 3 líneas — ambos modelos ya tenían `is_active`, pero
    hacía falta un campo APARTE, `deleted_at`, para distinguir "el Admin lo apagó a mano" de "está
    eliminado" y poder excluirlo de los listados por default). `DELETE` en
    `PlatformOrganizationViewSet`/`PlatformUserViewSet`/`UserViewSet` (el org-scoped, de cada
    Admin) nunca borra la fila: marca `deleted_at` + `is_active=False` — recuperable con la action
    `restaurar` (POST) de cada uno. `?incluir_eliminadas=1` (organizaciones) / `?incluir_eliminados=1`
    (usuarios, en ambos ViewSets) trae de vuelta los eliminados en el listado; por default quedan
    afuera. Eliminar una organización eliminá TAMBIÉN a todos sus usuarios (el pedido original: "con
    sus usuarios") — usando el MISMO timestamp de `deleted_at` para la organización y para cada
    usuario cascadeado, así `restaurar` la organización puede reactivar exactamente a los que se
    eliminaron junto con ella (`filter(deleted_at=organization.deleted_at)`) sin reactivar a uno que
    ya estaba eliminado de antes por su cuenta. No se relajó el `unique=True` de `email`/`dni`/
    `slug` — un usuario/organización eliminado sigue "ocupando" su email/slug hasta que se
    restaure (decisión deliberada por simplicidad, no un descuido). El Admin Panel agrega en las 3
    pantallas (`PlatformOrganizationsPage`, `PlatformUsersPage`, `UsersPage`) un checkbox "Ver
    eliminados/as" y, para una fila eliminada, un botón "Restaurar" en vez de Editar/Eliminar.
  - **Endurecimiento: el superusuario NO gestiona la configuración de ninguna organización en
    particular** (equipos, horarios, árbol de menú, mensajes del bot, etiquetas, canales — sólo
    organizaciones/usuarios/tokens/estadísticas/salud, que son de toda la plataforma a la vez).
    Antes, `common.viewsets.OrganizationScopedModelViewSet.get_queryset()` tenía a propósito un
    bypass "`is_superuser=True` real + sin organización → ve TODO sin filtrar" — pensado
    originalmente para otro caso de uso, pero en la práctica dejaba a un superusuario real
    gestionar (leer Y escribir) los datos de CUALQUIER organización a través de
    `TeamViewSet`/`MenuOpcionViewSet`/`BotMessagesView`/`EtiquetaViewSet`/`CanalViewSet`/etc., ya
    que `request.user.has_perm(...)` también le da `True` automáticamente a cualquier permiso
    Django para un `is_superuser=True` real (comportamiento del propio Django, no algo que se
    pueda apagar). Se sacó el bypass: ahora, sin `organization_id`, `get_queryset`/`perform_create`
    tiran `PermissionDenied` (403) — ni siquiera un superusuario real es la excepción. Varias vistas
    NO pasan por esa base (arman su propio queryset con `request.user.organization_id` a mano) y
    tenían el mismo problema de otra forma — algunas ni siquiera devolvían datos de otra
    organización pero sí rompían con un 500 al intentar escribir con `organization_id=None` contra
    un campo que no admite NULL: `bot_settings.BotMessagesView.get_object` (500 real, reproducido y
    corregido), `organizations.MyOrganizationView.get_object` (`Organization.objects.get(pk=None)`
    también rompía con 500), `menu.MenuOpcionViewSet.reordenar`,
    `business_hours.HorarioAtencionViewSet.grilla`, `business_hours.DiaExcepcionalViewSet` (tanto
    `get_queryset`, que antes devolvía sólo el catálogo compartido de feriados en vez de bloquear
    del todo, como su acción `grilla`), y `business_hours.TeamHorarioHabilView` (tenía su propia
    excepción explícita para `is_superuser`, también se sacó). Todas usan ahora
    `common.permissions.require_organization(request)` — mismo criterio que
    `OrganizationScopedModelViewSet`, para una vista/acción que arma su propio queryset a mano en
    vez de pasar por esa base — que corta con un 403 limpio ("Este recurso es de una organización —
    no aplica a una cuenta de plataforma") apenas se llama, antes de tocar la base. Test de
    regresión por cada uno de estos puntos (`teams`/`channels`/`bot_settings`/`organizations`/
    `menu`/`business_hours` `tests.py`, buscar `superusuario_de_plataforma`).
  - **Tokens de servicios internos** (`platform_admin` app, nueva; modelo `ServiceToken`, ruta
    `/api/core/plataforma/tokens-servicios/`): NO es la api key de un canal externo (eso sigue
    siendo `channels.Canal.api_key`, cosa completamente distinta) — es con qué se va a autenticar
    cada uno de los OTROS microservicios de este mismo proyecto (Channel Gateway, Conversation
    Engine, Operators Desk, Analytics, Webchat) contra la API de Core. Un `ServiceToken` por
    servicio, autogenerados los 5 al listar (`defaults.asegurar_service_tokens`, mismo patrón lazy
    que `channels.defaults.asegurar_canales` pero sin `organization` — esto es un único set para
    toda la plataforma, no por tenant). `token` es write-only (mismo patrón enmascarado que
    `Canal.api_key`: `token_configurado` + `token_preview`); la action `generar` (POST) genera uno
    seguro al azar (`secrets.token_urlsafe(32)`) y lo devuelve en texto plano UNA sola vez en esa
    respuesta, igual que `UserViewSet.reset_password`. `CHANNEL_GATEWAY` es el primer servicio que
    lo usa de verdad (los otros 4 siguen siendo sólo configuración, stubs de Fase 0): `platform_
    admin.service_auth.ServiceTokenAuthentication` (agregada a `DEFAULT_AUTHENTICATION_CLASSES`,
    junto a `JWTAuthentication` — reacciona sólo al esquema `Authorization: Service-Token <token>`,
    nunca a `Bearer`, así que no interfiere con el login de usuarios) valida el token contra este
    modelo (`token` cargado + `activo=True`) y deja el `ServiceToken` ya resuelto en `request.auth`
    (no hay `User` de Django detrás, `request.user` queda anónimo); `IsChannelGatewayService`
    exige además que sea justo el de ese servicio. Único consumidor hoy:
    `channels.views.InternalCanalConfigView` (`GET /api/core/internal/canales/<uuid>/`), el único
    lugar donde `api_key`/`webhook_secret` de un `Canal` salen de Core en texto plano.
  - **Estadísticas** (`GET /api/core/plataforma/estadisticas/`): conteos reales de lo que Core
    gestiona hoy (organizaciones, usuarios, equipos, canales configurados/activos, desglose por
    organización) — no hay conversaciones que contar todavía, eso es Conversation Engine.
  - **Salud de las APIs externas, vista global** (`GET /api/core/plataforma/salud-canales/`): el
    último resultado guardado de `channels.health.verificar_conexion` de TODOS los canales de TODAS
    las organizaciones a la vez — de sólo lectura, no dispara un chequeo nuevo (eso sigue siendo una
    acción de configuración de cada organización en `channels.CanalViewSet.verificar`, que un Admin
    dispara desde su propia pantalla de Canales).
  - **Manuales y referencia de la API interna** (`GET /api/core/plataforma/manual/` descarga
    `platform_admin/manual/manual-admin-panel.pdf`, copiado a mano dentro del código del servicio
    para que viaje con la imagen de Core sin depender de un volumen — si el manual se actualiza, hay
    que volver a copiar el PDF ahí y reconstruir la imagen). Además, `drf-spectacular` genera un
    esquema OpenAPI real de la API de Core a partir de los serializers/vistas (`SPECTACULAR_SETTINGS`
    en `config/settings.py`) con Swagger/Redoc en `/api/core/plataforma/schema/swagger|redoc/`.
    `PlatformSchemaView` (`/schema/`) es `AllowAny` A PROPÓSITO — no `IsPlatformSuperuser` como el
    resto de "Plataforma" (versión anterior, cambiada tras un bug real: Swagger UI/Redoc piden el
    esquema con un `fetch()` propio del navegador apenas cargan, SIN el header `Authorization` —
    ni JS tiene forma de saber del JWT, que vive en el `localStorage` del Admin Panel, otro origen
    — así que exigir auth ahí hacía que ESE primer fetch diera 401 y el visor nunca llegara a
    levantar ("Failed to load API definition"/"Something went wrong"), antes incluso de poder
    ofrecer un botón "Authorize" para pegar un token). Sólo expone la FORMA de la API (paths/
    params/campos) — nunca datos reales, que siguen exigiendo autenticación de verdad en cada
    endpoint real. Lo que sigue acotado al superusuario es el link en el menú del Admin Panel
    (`Layout.tsx`), no el propio endpoint. El botón "Copiar mi token de acceso" en
    `/plataforma/manuales` quedó igual, por si alguna vez hace falta autenticar una llamada real
    de "Probarlo" (`Try it out`) contra un endpoint protegido desde el propio Swagger UI. No cubre
    Channel Gateway/Conversation Engine/Operators Desk/Analytics/Webchat, sólo la API de Core.
    - **`drf-spectacular-sidecar`**: por default, Swagger/Redoc cargan su JS/CSS/fuentes desde
      `cdn.jsdelivr.net` — en un entorno sin salida a esa CDN (o con ella bloqueada) la página
      quedaba completamente en blanco, sin ningún error visible más que un 404/timeout silencioso
      en la pestaña Network del navegador (reportado como "no funciona la Referencia de la API").
      `drf-spectacular-sidecar` empaqueta el `swagger-ui-dist`/`redoc` como estáticos de Django
      (`SWAGGER_UI_DIST`/`SWAGGER_UI_FAVICON_HREF`/`REDOC_DIST = "SIDECAR"`) — nginx los sirve desde
      `/static/` como cualquier otro estático (`collectstatic` del entrypoint los junta solo), sin
      depender de ninguna CDN. Redoc sigue cargando la tipografía (Montserrat/Roboto) desde Google
      Fonts — no se resolvió, es sólo cosmético (la página funciona igual sin esas fuentes).
  - **Frontend**: `Layout.tsx` reemplaza COMPLETAMENTE la navegación normal (`NAV_ITEMS`, ahora
    filtrada por `hasPerm` ítem por ítem) por una lista aparte (`PLATFORM_NAV_ITEMS`) cuando
    `isPlatformSuperuser(me)` — nunca las dos mezcladas, para que el superusuario no vea ruido de
    opciones de organización (Equipos/Horarios/Mensajes/Etiquetas/Canales/Usuarios de una
    organización) que no le aplican, aun cuando por `is_superuser=True` de Django técnicamente
    "tendría" cualquier permiso (`user.has_perm()` de Django siempre da `True` para un superusuario
    real, así que un `hasPerm` a secas NO alcanzaba para ocultar esas pantallas — hace falta la
    condición explícita). `auth/permissions.ts::isPlatformSuperuser` espeja
    `common.permissions.IsPlatformSuperuser` del back. La landing ("/") también depende de esto:
    `App.tsx::Home` manda al superusuario a `/plataforma/organizaciones` en vez de `/menu` (no
    tiene permiso para ver el menú de ninguna organización en particular).
    - **Bug real, ya corregido: `LoginPage.tsx` tenía `navigate("/menu")` hardcodeado** en el
      submit del formulario (y `"/menu"` como fallback si ya había sesión) — bypasseaba
      completamente el criterio de `App.tsx::Home` de acá arriba. El superusuario terminaba
      SIEMPRE en `/menu` después de loguearse (una pantalla a la que ya no tiene acceso, ver
      "Endurecimiento" más abajo), con errores 403 sin capturar en consola y la página colgada —
      exactamente el reporte de "no funciona nada". `AuthContext.login()` ahora devuelve el `Me`
      recién cargado (antes no devolvía nada — el `me` del contexto capturado en el closure de
      `LoginPage` seguía viejo hasta el siguiente render, un closure stale clásico) para que
      `LoginPage` pueda decidir el destino con el dato correcto en la mano, con la misma función
      `landingPorDefecto` (mismo criterio que `Home`) en los dos lugares.
    - **Gotcha de Docker Desktop en Windows: el watcher de Vite (chokidar) no siempre detecta los
      cambios del bind mount** (`docker-compose.override.yml` monta `./frontend/admin-panel:/app`)
      — Vite se queda sirviendo el bundle viejo después de guardar un archivo, sin ningún error
      visible, hasta reiniciar el contenedor a mano. Se agregó `server.watch.usePolling` +
      `interval` en `vite.config.ts` (permanente, no un workaround puntual) — sin esto, cualquier
      cambio de código corre el riesgo de no reflejarse en el navegador hasta un restart manual.

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
- **WebSocket de entrega en tiempo real: implementado**, con un alcance recortado a propósito
  respecto de lo que documentaban estos párrafos originalmente — `services/conversation-engine`
  (FastAPI) es HOY sólo la capa de entrega (`WS /ws/operador/{token}`, mismo JWT de Core), sin
  ninguna tabla propia de negocio. Core le avisa (`conversations.conversation_engine_client.
  notificar_evento`, mejor esfuerzo vía `POST /internal/eventos/`, `Service-Token` del servicio
  `CONVERSATION_ENGINE`) cada vez que pasa algo relevante para la bandeja, y este servicio lo
  reenvía por organización a los sockets conectados (`app/connections.py`, registro EN MEMORIA de
  un solo proceso — no sobrevive un restart ni escala a más de un worker todavía). Contrato completo
  de los 3 tipos de evento (`mensaje_nuevo`/`conversacion_actualizada`/`nota_interna_nueva`) en
  §7 de [`docs/operators-desk-api-contract.md`](operators-desk-api-contract.md).
- **`OperatorSession`/`AsignacionChat` como tablas persistidas: NO implementado, a propósito** — la
  asignación real (`team`/`operador`/lock de 2 minutos) sigue viviendo enteramente en
  `Conversacion` de Core (Fase 5 más abajo), duplicarla acá sería una segunda fuente de verdad sin
  necesidad. `GET /organizations/{id}/conexiones-activas` sí existe, pero cuenta conexiones del
  proceso actual (en memoria), no una tabla.
- Límite de conexiones simultáneas por organización (consultando el plan en Core): no implementado.
- **Chat interno entre operadores, sin atar a una conversación puntual** (mensajería 1:1 arbitraria
  entre operadores, pedido explícito, todavía no implementado): lo que SÍ existe es
  `conversations.ConversacionNotaInterna` (Fase 5 más abajo), un recorte deliberado acotado a una
  conversación puntual — no reemplaza esto, que sigue siendo un chat operador-a-operador aparte, sin
  `Conversacion`/`Contacto` de por medio, para cuando se pida explícitamente.
- **Escalar a más de un worker/instancia**: no implementado — el registro de conexiones de
  `app/connections.py` es un dict en memoria de un solo proceso (`uvicorn` sin `--workers`, ver su
  Dockerfile). El día que haga falta más de una instancia, mover ese registro a algo compartido
  entre procesos (Postgres LISTEN/NOTIFY — restricción no negociable del proyecto: nada de
  Redis/Kafka), no antes de que el volumen real lo justifique.

### Fase 5 — Operators Desk Service + Operators Desk Web
- Lo que esta fase pedía (bandeja, hilo, responder/derivar/etiquetar/cerrar, observaciones
  obligatorias al resolver/rechazar/pausar) está **implementado directo en Core**
  (`conversations.views.ConversacionViewSet`), no como el BFF/Conversation Engine con WebSocket que
  documentaban estos párrafos originalmente — mismo pivot pragmático que el resto de `conversations`
  (bandeja/tomar/responder/cerrar, ver `users.group_permissions`). Contrato completo, con ejemplos
  de request/response, para quien construya un cliente (Operators Desk Web o la app Android):
  [`docs/operators-desk-api-contract.md`](operators-desk-api-contract.md).
  - **Etiquetas sobre una conversación**: `conversations.ConversacionEtiqueta` (conversación ×
    `tags.Etiqueta`, quién la aplicó y cuándo) — `GET/POST/DELETE .../conversaciones/{id}/etiquetas/`.
    Las de sistema (pendiente/asignada/tomada/en_proceso/en_pausa/rechazado/resuelto) son
    mutuamente excluyentes entre sí; las generales y de equipo son libremente acumulables.
  - **Observaciones**: `conversations.ConversacionObservacion`, opcionales en cualquier momento
    (`GET/POST .../observaciones/`) pero **obligatorias** (texto no vacío) al aplicar la etiqueta de
    sistema resuelto/rechazado/en_pausa — el back rechaza esa transición sin observación.
  - **Notas internas entre operadores**: `conversations.ConversacionNotaInterna` — recorte deliberado
    del "chat interno" que documentaba la Fase 4 más abajo: acá está ACOTADO a una conversación
    puntual y es sólo REST con polling (`GET/POST .../notas-internas/`), no el WebSocket 1:1
    arbitrario entre operadores que se pensó para Conversation Engine (ver esa fase, sigue sin
    implementar).
  - Lo que sigue faltando de verdad: reconexión automática del WebSocket de Conversation Engine
    (hoy es 100% responsabilidad del cliente, ver §7.1 del contrato), asignación round-robin
    explícita vía API (hoy sólo la dispara una derivación de menú), y notificaciones push a la app
    Android (**no implementado, no construir sin pedido explícito** — sección 11 — pero ver la
    sección "Notificaciones push (roadmap)" del contrato de API para el enfoque que se evaluó).

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
- Webchat Service completo (hoy es un stub).
- Push notifications en background (FCM) para la app Android.
- Editor de menú con capturas de datos / autorespuesta por palabra clave libre.

## 11. Explícitamente fuera de alcance ahora

No implementar salvo pedido explícito: WhatsApp en Channel Gateway (Messenger/Instagram ya están,
ver sección 9/Fase 3), Webchat Service (más allá del stub),
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
