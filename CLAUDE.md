# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Multi-tenant chat platform (WhatsApp/Messenger/Instagram + web) with a menu
bot, hand-off to human operators, and admin/operator panels. Full
architecture, phase plan, and rationale for every non-obvious decision live
in **[docs/CONTEXTO_PROYECTO.md](docs/CONTEXTO_PROYECTO.md)** — read the
relevant phase section (§10) plus §2–9 before working on a new area; it is
kept up to date with what's actually implemented (not just planned) and is
more authoritative than this file for anything it covers in detail.

**Non-negotiable stack constraints** (§1 of that doc): Python (Django +
FastAPI), PostgreSQL, React/TypeScript, Java (Android) only. No Node.js
backend runtime, no Kafka/RabbitMQ, no Redis, no Elasticsearch, no S3-style
storage. Everything is multi-tenant from the start — every business table
carries (or inherits via FK) `organization_id`, every query is scoped to the
authenticated user's organization. Don't add a new technology or build
something single-tenant "to simplify".

## Architecture

6 backend microservices (one Postgres schema each, single Postgres
instance) + 2 React frontends + 1 Android app (not dockerized). **Core
decides, everything else executes**: all business logic (menu tree,
business hours, roles, team routing) lives in Django `services/core`; the
FastAPI services are I/O executors (webhooks, WebSockets, read-only
aggregations) that ask Core "what do I do with this?" and have no business
source of truth of their own.

| Service | Path | Stack | Port | Status |
|---|---|---|---|---|
| Core | `services/core` | Django + DRF | 8001 | Implemented — source of truth for all business logic |
| Channel Gateway | `services/channel-gateway` | FastAPI | 8002 | Implemented — WhatsApp/Messenger/Instagram webhooks, outbound sends, native selection widgets |
| Conversation Engine | `services/conversation-engine` | FastAPI + WS | 8003 | Partial — real-time delivery only (`WS /ws/operador/{token}`), in-memory connections, single process |
| Analytics | `services/analytics` | FastAPI, read-only | 8005 | Phase 0 stub (`/health` only) |
| Webchat | `services/webchat` | FastAPI + WS | 8006 | First version built (session handshake, inbound/outbound messages, visitor WebSocket, embeddable `widget.js`), reviewed and wired into Core (`IsInboundChannelService`, `conversations.webchat_client`); opt-in via `--profile webchat` |
| Admin Panel | `frontend/admin-panel` | React + TS | 3000 | Active |
| Operators Desk Web | `services/operators-desk/web` | React + TS | 3001 | Implemented and in production, published at `operadores.udcchat.com.ar` — talks directly to Core, not to any BFF |
| Android operator app | `UDCOperadorAPP` | Java, Gradle | — | Functional — login, inbox, conversation thread, take/derive/tag/close with observations, internal notes; no refresh token yet |

Note: the FastAPI stub that used to sit at `services/operators-desk` (port 8004, meant as a BFF
for Operators Desk Web) was removed from the repo and from `docker-compose.yml` (2026-10) — it
never had a real consumer; Operators Desk Web always talked straight to Core. Don't recreate it
without an explicit ask.

Core's menu tree (`MenuOpcion`), business hours (`HorarioAtencion`/
`DiaExcepcional`), and conversation logging are **ported** from
`github.com/garzamorada/chatbot` (adapted to multi-tenant) — when touching
that code, prefer diffing against the original naming/behavior rather than
redesigning it (§5 of the context doc explains what was kept vs. dropped).

Two cross-cutting rules that apply to any new channel/service work:
- **Native selection widgets, not numbered text, when the channel supports
  it** (§4.1.1): Core returns a structured `opciones` list; each Channel
  Gateway-type service is responsible for turning that into its channel's
  native list/buttons/quick-replies, falling back to plain numbered text
  only outside the channel's limits. Core never encodes a channel's UI format.
- **Neutral markup only in Core** (§4.1.2): `**bold**`, `_italic_`,
  `~strike~`, `` `mono` `` — never a channel's literal syntax. Each channel
  adapter translates (or discards) it. A shared pure function/module (no
  state, no I/O) is the intended shape if this gets duplicated.

## Commands

### Environment
```bash
cp .env.example .env   # fill in local secrets
docker compose up --build
```
`docker-compose.override.yml` is merged automatically in dev (hot-reload
volumes, 1 gunicorn worker with `--reload`, Vite dev server for admin-panel).

Seed demo data (org, users, teams, 2-level menu tree) — idempotent:
```bash
docker compose run --rm --entrypoint python core manage.py seed_ucd_demo
```

### Core (Django) tests
```bash
docker compose run --rm --entrypoint python core manage.py test
```
Run a single app/test: `manage.py test menu`, `manage.py test menu.tests.MenuOpcionTests.test_x`.
Tests that touch `ScopedRateThrottle`/login-lockout must clear the cache by
hand in `setUp()` (`django.core.cache.cache.clear()`) — Django's cache does
not reset between tests like the DB does.

### Admin Panel (React)
```bash
cd frontend/admin-panel
npm install
npm run dev      # standalone, outside docker compose
npm run build    # tsc -b && vite build
```

### Other backend services (FastAPI stubs)
Each has its own `requirements.txt`/`Dockerfile`; run via
`docker compose up <service-name>` — there is no app logic yet beyond
`GET /health`, so there's nothing to unit test until a phase builds one out.

## Core (Django) conventions

- **Auth**: Core issues RS256 JWTs (`djangorestframework-simplejwt`) with
  `org_id` and `groups` (a list, not a singular `role`) in the payload. Keys
  are generated on container start if missing (`entrypoint.sh` →
  `manage.py generate_jwt_keys`); FastAPI services validate against
  `/api/auth/jwks/`.
- **No `role` field** — authorization is entirely Django groups
  (`user.groups`, M2M — a user can be in more than one). The 5 groups and
  their exact permissions are defined in one place,
  [services/core/users/group_permissions.py](services/core/users/group_permissions.py)
  (`GROUP_PERMISSIONS`), consumed by both the `setup_groups` management
  command and the tests — change permissions there, not ad hoc.
  `encargados_difusion` and `analistas_datos` currently have **zero** Core
  permissions beyond authentication/profile — their screens live in
  services that don't exist yet (Analytics, campaigns). `operadores` does
  have real Core permissions (`conversations.view_/change_conversacion`,
  read-only `teams.view_team`/`tags.view_etiqueta`) — their screen is
  Operators Desk Web (`services/operators-desk/web`, in production) and
  the Android app, never the Admin Panel. Never add Admin Panel screens for
  `encargados_difusion`/`analistas_datos` without
  checking whether the owning service (Phase 4/5/7/9) has landed.
- **`common.permissions.StrictDjangoModelPermissions`**
  ([services/core/common/permissions.py](services/core/common/permissions.py)):
  extends DRF's `DjangoModelPermissions` so GET also requires `view_<model>`,
  not just writes. `@action`s that don't map 1:1 to CRUD (`tree`,
  `reordenar`, `grilla`) call `require_perm(request, "app.codename")` by hand.
- **`common.viewsets.OrganizationScopedModelViewSet`**: base for any
  org-scoped ViewSet — filters querysets by the authenticated user's
  `organization_id` automatically. A platform superuser (`is_superuser=True`
  + no `organization`) gets `PermissionDenied` from this base and from any
  hand-rolled queryset, via `common.permissions.require_organization` — they
  do **not** get an implicit "see everything" bypass (that bypass existed
  once and was deliberately removed; see §9/§10 Fase 2 in the context doc
  for the full list of views that had to be patched for it).
- **`common.permissions.IsPlatformSuperuser`**: the real gate for the
  Admin Panel's "Plataforma" section (`platform_admin` app — organizations,
  cross-org users, inter-service tokens, stats, external API health, API
  docs). Checks `request.user.is_superuser` (the real Django flag), not the
  `superusuarios` group — a group member without the real flag does not get
  platform-wide access, and vice versa the flag alone is what unlocks it
  regardless of group membership. This is the one deliberate exception to
  multi-tenant scoping in the whole system.
- **Encrypted/write-only secrets pattern**: `Canal.api_key` and
  `ServiceToken.token` are both write-only on their serializers — the API
  only ever returns a `*_configurada` bool + `*_preview` (last 4 chars) or,
  for freshly generated tokens/reset passwords, the plaintext exactly once
  in that single response. Follow this pattern for any new secret-like field.
- **Soft delete**: `common/soft_delete.py` (`marcar_eliminado`/
  `restaurar_eliminado`) — organizations and users are never hard-deleted by
  the API; `deleted_at` + `is_active=False`, excluded from listings unless
  `?incluir_eliminadas=1`/`?incluir_eliminados=1`, recoverable via a
  `restaurar` action. Deleting an org cascades to its users using the same
  `deleted_at` timestamp so restore only reactivates that exact batch.
- **Media files**: `avatar`/`avatar_thumbnail` and any future
  `ImageField`/`FileField` must be serialized as absolute URLs
  (`request.build_absolute_uri`), never `FieldFile.url` directly — the Admin
  Panel runs on a different origin/port. `MEDIA_ROOT` is `/mediafiles` (root
  of the container, NOT under `/app` — a host bind mount nested under the
  override's `./services/core:/app` leaves phantom dirs on Windows): named
  volume `media_files` in prod, `./data/media` on the host in dev (override).
  Uploaded files get a versioned name (`avatars/<pk>_<hash>.jpg`) because
  Cloudflare caches `/media/` for 4h. Behind the tunnel Django needs
  `SECURE_PROXY_SSL_HEADER` (set) for `https://` absolute URLs.
- **Logs & incidents** (`monitoring` app): every service writes JSON lines
  (`common/observabilidad.py` in Core, an identical `app/observabilidad.py`
  in each FastAPI service — keep the 4 copies in sync) to `./logs/<service>/`
  with size rotation (`concurrent-log-handler`, `keep_file_open=False` —
  required on the Windows bind mount). A `request_id` (`X-Request-ID` or
  Cloudflare's `Cf-Ray`) is propagated between services. `manage.py
  vigilar_incidentes` runs in a supervisord loop, turns ERROR lines / failed
  health checks / login brute force into `Incidente`s and mails
  `ALERTAS_EMAIL_DESTINO`; the Admin Panel shows them in Plataforma >
  Incidentes / Logs. Tests never write to the real log files.
- **API docs**: `drf-spectacular` (+ `drf-spectacular-sidecar`, to avoid a
  CDN dependency for Swagger/Redoc assets) generates the OpenAPI schema at
  `/api/core/plataforma/schema/`. The raw schema endpoint is intentionally
  `AllowAny` (Swagger/Redoc's browser-side `fetch()` can't attach the JWT) —
  only the Admin Panel *link* to it is gated to platform superusers, not the
  endpoint itself.
- **Naming**: new modules in English (`organizations`, `teams`, `bot`);
  code ported from `garzamorada/chatbot` keeps its original Spanish names
  (`MenuOpcion`, `HorarioAtencion`) to stay diffable against the source repo.

## Frontend (Admin Panel) conventions

- **Never gate UI on a role/group name.** `GET /api/core/users/me/` returns
  `permissions` (flat list from `user.get_all_permissions()`) and `groups`
  (label only); `src/auth/permissions.ts::hasPerm` is the only thing that
  should decide what renders. `isPlatformSuperuser(me)` mirrors
  `IsPlatformSuperuser` on the backend and swaps the entire nav
  (`PLATFORM_NAV_ITEMS` vs. the normal org-scoped `NAV_ITEMS`) — the two are
  never mixed, since `user.has_perm()` is always `True` for a real Django
  superuser and would otherwise leak org-scoped nav items to them.
- Prefer the built-in `MessageEditor` + `WhatsAppPreview` components for any
  new bot-message-configuration UI (menu, `bot_settings`) instead of a new
  bespoke editor — they already implement the neutral-markup toolbar and
  navigable chat preview pattern used across the panel.
- Vite dev server watch under Docker Desktop on Windows needs
  `server.watch.usePolling` (already set in `vite.config.ts`) — bind-mount
  changes aren't reliably picked up by chokidar otherwise; don't remove it.

## Available project skills

`.agents/skills/` has three project-specific skills worth invoking
proactively for their respective areas: `agent-memory-design` (session/
long-term memory tiers and isolation — currently forward-looking, no memory
subsystem exists yet), `chat-security-review` (webhook trust, inter-service
secrets, PII — use before shipping anything touching channel webhooks or
stored user data), and `multichannel-chat-ux-design` (conversation flow /
hand-off / channel-capability design). Note these describe the *target*
multi-channel platform in general terms (they mention Telegram/Slack/email);
cross-check against §3/§4 of the context doc for which channels are
actually in scope here (WhatsApp/Messenger/Instagram/Webchat).
