# Operators Desk Web

Primera versión de `services/operators-desk/web` — el panel de escritorio
para que un operador atienda chats de WhatsApp/Messenger/Instagram
derivados por el bot. React + TypeScript + Vite, puerto 3001.

**Contexto importante:** esto fue armado originalmente por M Rozen,
Business Analyst sin experiencia previa en React, que se guio con:

- `docs/requerimientos-operators-desk-web.md` (qué construir)
- `docs/operators-desk-api-contract.md` (contrato de API exacto)
- El código ya existente de `frontend/admin-panel` (para copiar patrones:
  `AuthContext`, `api/client.ts`, `MessageEditor`, etc.)

**Actualización (2026-09-30):** revisado línea por línea contra el código
real de Core/Conversation Engine (no sólo contra los docs) e integrado a
`docker-compose.yml`/`docker-compose.override.yml`. Probado de punta a
punta en un navegador real, con datos reales (`agente1@ucd.demo`): login,
bandeja, tomar, hilo de mensajes completo, las 4 pestañas, y un evento
real recibido por WebSocket en tiempo real. Un solo bug encontrado y
corregido: `useOperatorSocket` reintentaba el refresh del JWT al recibir
el código 4401 mandando el body vacío a `/api/auth/refresh/` en vez del
`refresh` token real (ahora usa `refreshAccessToken` exportado de
`api/client.ts`, la misma función que ya usaba el resto de la app). El
resto de "Qué NO está" más abajo sigue vigente tal cual estaba.

## Cómo correrlo

Con el resto del stack (recomendado, ya wireado a `docker-compose.yml`):

```bash
docker compose up --build core conversation-engine operators-desk-web
docker compose run --rm --entrypoint python core manage.py seed_ucd_demo
```

Suelto, contra un backend ya levantado en otro lado:

```bash
cd services/operators-desk/web
npm install
npm run dev
```

Lee `VITE_CORE_API_URL`/`VITE_CONVERSATION_ENGINE_URL` del entorno (default
`http://localhost:8001`/`:8003` si no están seteadas — ver `docker-compose.yml`
para cómo se pasan en cada modo).

## Qué está armado

- **Login** (`/login`) con manejo de 401 (credenciales inválidas) y 429
  con `blocked_until` (bloqueo por fuerza bruta).
- **Cambio de contraseña obligatorio** (`must_change_password`) antes de
  dejar entrar a la bandeja.
- **Bandeja compartida** (`/bandeja/sin-asignar`, `/bandeja/mias`), con
  filtro de equipo del lado del cliente, polling cada 12s y refresco por
  WebSocket.
- **Vista de una conversación** (`/conversaciones/:id`): hilo de mensajes
  (con el marcado `**negrita**`/`_cursiva_`/`~tachado~`/`` `mono` ``
  renderizado), notas internas, observaciones y etiquetas — en pestañas
  separadas.
- **Acciones**: tomar, responder (reutilizando el `MessageEditor` del
  Admin Panel), derivar (con observación obligatoria), cerrar (con
  confirmación), aplicar/quitar etiquetas (con observación obligatoria
  para `resuelto`/`rechazado`/`en_pausa`).
- **Renovación del lock** cada 90s mientras la conversación tomada por mí
  sigue en pantalla.
- **WebSocket** (`src/hooks/useOperatorSocket.ts`) contra Conversation
  Engine, con reconexión con backoff exponencial y manejo del código 4401
  (intenta refrescar el JWT antes de reintentar). Siempre con polling de
  respaldo por si el socket no está conectado.

## Qué NO está (a propósito, o por falta de tiempo/conocimiento)

Todo esto queda para que el resto del equipo lo revise y complete:

- **Nada de esto se probó contra un backend real** (ver arriba). Puede
  haber nombres de campo mal, shapes de request/response que no coinciden
  exactamente, o cosas que directamente no anduvieron nunca.
- **Multi-conversación en paralelo** (§3.6 del documento de
  requerimientos): hoy sólo se puede tener una conversación abierta a la
  vez. Un layout de pestañas/columnas para 2-3 en simultáneo, con borrador
  de respuesta persistente por pestaña, queda pendiente.
- **Notificación de escritorio del navegador** ante `mensaje_nuevo` de una
  conversación que no está en foco (§3.5) — no implementado.
- **Edición de perfil completa** (nombre/apellido/DNI/avatar recortable):
  `MyProfilePage` sólo muestra los datos y linkea a cambiar contraseña.
  `frontend/admin-panel/src/pages/MyProfilePage.tsx` y su `AvatarCropper`
  sirven de referencia si hace falta.
- El **WebSocket se abre una vez por pantalla** (uno en la bandeja, otro en
  cada conversación abierta) en vez de compartir una sola conexión global
  vía contexto — funciona, pero es medio redundante; se podría mejorar con
  un `SocketProvider` a nivel de `App.tsx`.
- **Estilos**: `src/index.css` es una hoja liviana escrita de cero, no el
  design system de 1500+ líneas de `frontend/admin-panel`. Si quieren
  unificar la identidad visual entre los dos frontends, hay que rehacer
  esto tomando esos estilos como base.
- Sin tests (el Admin Panel tampoco parece tener demasiados, pero por las
  dudas se aclara).
- Sin el linter `oxlint` configurado (el Admin Panel lo tiene con un plugin
  propio, `anti-slop`, que no se copió acá).

## Estructura

Calcada de `frontend/admin-panel` para que sea fácil de seguir para
cualquiera del equipo que ya conozca ese proyecto:

```
src/
  api/client.ts          fetch con manejo de JWT (access/refresh) y errores
  auth/AuthContext.tsx   sesión, login/logout, perfil (Me)
  auth/permissions.ts    helper hasPerm (no se usa mucho todavía)
  components/            Layout, ErrorBoundary, MessageEditor, MessageFormat
  hooks/useOperatorSocket.ts   WebSocket con reconexión
  pages/                 LoginPage, ChangePasswordPage, InboxPage,
                         ConversationPage, MyProfilePage
  routes/ProtectedRoute.tsx
  types.ts               tipos según el contrato de API
```
