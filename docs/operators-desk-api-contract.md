# Contrato de API — Operators Desk (app Android + Operators Desk Web)

Contrato REST + WebSocket que consume cualquier cliente operador: la app
Android (`UDCOperadorAPP`) hoy, y `frontend/operators-desk-web` (React)
cuando se construya — **es a propósito el mismo contrato para los dos**
(sección 3.2 de [`CONTEXTO_PROYECTO.md`](CONTEXTO_PROYECTO.md)), no lo
dupliques ni lo adaptes por cliente. Dos servicios backend intervienen,
pero para el cliente es transparente cuál es cuál:

- **Core** (`services/core`, Django): TODA la lectura/escritura real —
  login, equipos, etiquetas, conversaciones y sus actions (§1 a §5). Es la
  única fuente de verdad de negocio.
- **Conversation Engine** (`services/conversation-engine`, FastAPI): SÓLO
  el WebSocket de entrega en tiempo real (§7) — un aviso de "algo cambió,
  andá a buscarlo a Core", nunca datos de negocio en sí. No tiene login
  propio: usa el mismo JWT que ya tenés de Core.

## Documentación interactiva (Swagger/Redoc) — sin login

Las dos siguen el código solas, así que ante una duda de shape exacto
(nombre de campo, tipo, si algo es nullable) son más confiables que este
documento si llegaran a desactualizarse entre sí. Ninguna de las dos pide
login para ABRIRSE — podés pasarle estos links a cualquiera sin darle
ninguna cuenta:

| | Swagger | Redoc | Esquema crudo (JSON) |
|---|---|---|---|
| **Core** (dev) | `http://localhost:8001/api/core/plataforma/schema/swagger/` | `http://localhost:8001/api/core/plataforma/schema/redoc/` | `http://localhost:8001/api/core/plataforma/schema/` |
| **Conversation Engine** (dev) | `http://localhost:8003/docs` | `http://localhost:8003/redoc` | `http://localhost:8003/openapi.json` |
| **Conversation Engine** (udcchat.com.ar) | `https://realtime.udcchat.com.ar/docs` | `https://realtime.udcchat.com.ar/redoc` | `https://realtime.udcchat.com.ar/openapi.json` |

`realtime.udcchat.com.ar` es el mismo dominio que expone el WebSocket de
§7 (`wss://realtime.udcchat.com.ar/ws/operador/{token}`) — Cloudflare
sirve Swagger/Redoc/WS los tres sobre el mismo "Public Hostname", sólo
cambia el esquema. Los mismos links (más el manual del Admin Panel y este
documento) están un clic más cómodo desde adentro del Admin Panel:
**Plataforma → Manuales y API** (necesita cuenta de superusuario de
plataforma — si no tenés una, usá las URLs de la tabla directo).

**Importante — el esquema de Core cubre TODA su API** (organizaciones,
canales, menú, horarios, usuarios...), no sólo lo que un operador usa;
este documento es el subconjunto curado con ejemplos. **El esquema de
Conversation Engine NO incluye `WS /ws/operador/{token}`** — OpenAPI no
tiene forma de documentar un WebSocket — ese contrato está únicamente acá,
§7.

## 0. Principio arquitectónico — leer antes que nada

**El cliente operador habla únicamente con `services/core` (Django). Nunca
con WhatsApp/Messenger/Instagram, nunca con la Graph API de Meta, nunca con
`services/channel-gateway`.** Core es quien decide todo el negocio y quien
ya le habla a Channel Gateway del otro lado para efectivamente entregar un
mensaje al contacto (`conversations.channel_gateway_client.
enviar_mensaje_saliente`, disparado por `POST .../responder/` — ver más
abajo). El cliente operador ve el canal (`canal`: `"WHATSAPP"` /
`"MESSENGER"` / `"INSTAGRAM"` / `"WEBCHAT"`) sólo como un dato informativo
para mostrar un ícono — nunca arma ni interpreta nada específico de esa
API externa. Si en algún momento este contrato pareciera pedirte hablar
con algo que no sea Core, es un error de este documento, no una excepción
real: consultá antes de implementarlo así.

Motivo de diseño (sección 2.1 de `CONTEXTO_PROYECTO.md`): **Core decide,
todo lo demás ejecuta**. Un cliente operador que dependiera de las reglas
de un canal externo se rompería cada vez que Meta cambia algo, y ni
Operators Desk Web ni la app Android tendrían por qué enterarse de eso.

## 1. Autenticación

Login humano — no confundir con el `Service-Token` que usan los
microservicios entre sí (eso no aplica acá).

### `POST /api/auth/login/`

```json
// Request
{ "email": "operador@organizacion.test", "password": "..." }

// 200 OK
{ "access": "<jwt, RS256, 30 min>", "refresh": "<jwt, 7 días>" }
```

- Sin JWT previo (`AllowAny`). Throttle propio: 10/min.
- **Bloqueo por fuerza bruta**: a la 3ª falla seguida desde la misma IP,
  429 con `{"detail": "...", "blocked_until": "<datetime ISO>"}` durante
  12hs — independiente del throttle, es una penalización de negocio.
- 401 si el usuario/contraseña no matchean (`{"detail": "..."}`).
- El JWT es RS256 y trae, además de lo estándar de SimpleJWT, estos claims
  propios (`authentication.serializers.CustomTokenObtainPairSerializer`):
  `org_id` (int), `grupos` (lista de strings, ej. `["operadores"]` — un
  usuario puede estar en más de uno), `email`. **No hace falta decodificar
  el JWT en el cliente para nada de esto**: `GET /api/core/users/me/` (más
  abajo) te da exactamente lo mismo ya resuelto, en un formato más cómodo.
- Guardá `access` Y `refresh` (la app Android de hoy sólo guarda `access`
  — hay que agregar el refresh, el access vence en 30 minutos).

### `POST /api/auth/refresh/`

```json
// Request
{ "refresh": "<jwt>" }
// 200 OK
{ "access": "<jwt nuevo>" }
```

`refresh` NO rota (`ROTATE_REFRESH_TOKENS=False`) — el mismo refresh sirve
hasta que vence a los 7 días; ahí hay que loguear de nuevo.

### Todas las demás requests

Header `Authorization: Bearer <access>`. 401 si falta/venció/es inválido.

### `GET /api/core/users/me/`

Perfil del operador logueado + el contrato de autorización real (nunca
decidas qué mostrar mirando el nombre del grupo — mirá `permissions`):

```json
{
  "id": 42, "email": "operador@organizacion.test",
  "first_name": "Ana", "last_name": "Gómez", "dni": "30111222",
  "avatar": "http://.../media/avatars/42.jpg", "avatar_thumbnail": "http://.../media/avatars/42_thumb.jpg",
  "groups": ["operadores"],
  "permissions": ["conversations.view_conversacion", "conversations.change_conversacion", "teams.view_team", "tags.view_etiqueta"],
  "organization_id": 7, "is_staff": false, "is_superuser": false,
  "must_change_password": false
}
```

`must_change_password=true` → mostrar el flujo de cambio de contraseña
obligatorio antes de dejar entrar a la bandeja (pasó porque un admin le
reseteó la contraseña).

- `PATCH /api/core/users/me/` — editar nombre/apellido/DNI/avatar (nunca
  grupos ni organización). `avatar` va como `multipart/form-data`.
- `POST /api/core/users/me/cambiar-password/` — `{"current_password", "new_password"}`.
- `POST /api/auth/password-reset/` — `{"email"}`, siempre responde 200 genérico.
- `POST /api/auth/username-reset/` — `{"dni"}`, le manda el email registrado a esa cuenta.

## 2. Equipos (sólo lectura)

### `GET /api/core/teams/`

Necesario para armar el selector de "a qué equipo derivo" (§4.6). Paginado
(ver §7).

```json
{
  "count": 2, "next": null, "previous": null,
  "results": [
    { "id": 3, "name": "Ventas", "members": [42, 51], "is_active": true, "created_at": "2026-01-10T12:00:00Z" }
  ]
}
```

Un operador SIEMPRE recibe sólo los equipos de su propia organización
(scoping automático por JWT, nunca hace falta ni se puede mandar
`organization_id`). No puede crear/editar/borrar equipos (403).

## 3. Catálogo de etiquetas (sólo lectura)

### `GET /api/core/etiquetas/?team=<id opcional>`

El catálogo completo de la organización — 7 de sistema (autogeneradas la
primera vez que se lista, no se pueden borrar) + una por equipo + las que
arme un Admin a mano. Es de acá de donde sale el `id` que se manda en
`POST .../etiquetas/` (§4.6) y el color para pintar cada chip.

```json
{
  "count": 9, "next": null, "previous": null,
  "results": [
    { "id": 101, "team": null, "codigo": "pendiente", "nombre": "Pendiente", "color": "#9CA3AF", "color_texto": "#FFFFFF", "es_sistema": true, "orden": 0, "created_at": "...", "updated_at": "..." },
    { "id": 102, "team": null, "codigo": "asignada", "nombre": "Asignada", "color": "#60A5FA", "color_texto": "#FFFFFF", "es_sistema": true, "orden": 1, "created_at": "...", "updated_at": "..." },
    { "id": 103, "team": null, "codigo": "tomada", "nombre": "Tomada", "color": "#818CF8", "color_texto": "#FFFFFF", "es_sistema": true, "orden": 2, "created_at": "...", "updated_at": "..." },
    { "id": 104, "team": null, "codigo": "en_proceso", "nombre": "En proceso", "color": "#F59E0B", "color_texto": "#FFFFFF", "es_sistema": true, "orden": 3, "created_at": "...", "updated_at": "..." },
    { "id": 105, "team": null, "codigo": "en_pausa", "nombre": "En pausa", "color": "#FBBF24", "color_texto": "#FFFFFF", "es_sistema": true, "orden": 4, "created_at": "...", "updated_at": "..." },
    { "id": 106, "team": null, "codigo": "rechazado", "nombre": "Rechazado", "color": "#EF4444", "color_texto": "#FFFFFF", "es_sistema": true, "orden": 5, "created_at": "...", "updated_at": "..." },
    { "id": 107, "team": null, "codigo": "resuelto", "nombre": "Resuelto", "color": "#22C55E", "color_texto": "#FFFFFF", "es_sistema": true, "orden": 6, "created_at": "...", "updated_at": "..." },
    { "id": 108, "team": 3, "codigo": "", "nombre": "Ventas", "color": "#3454D1", "color_texto": "#FFFFFF", "es_sistema": false, "orden": 0, "created_at": "...", "updated_at": "..." },
    { "id": 109, "team": null, "codigo": "", "nombre": "VIP", "color": "#000000", "color_texto": "#FFFFFF", "es_sistema": false, "orden": 0, "created_at": "...", "updated_at": "..." }
  ]
}
```

Las 3 primeras filas (pendiente/asignada/tomada) **nunca las aplicás a
mano** — Core las aplica solo (actualización 2026-10: antes `estado_
operativo` en §4.1 era sólo un dato calculado, ahora además queda una fila
real de `ConversacionEtiqueta` por cada paso, con quién/cuándo) en estos 3
momentos: al crearse la conversación (pendiente), al derivarse a un
equipo — por el árbol de menú o a mano, §4.7 — (asignada), y al tomarla,
§4.3 (tomada). Si ves una de estas 3 en `GET .../etiquetas/`, es
informativo (para el historial/auditoría), no algo que tu UI tenga que
aplicar o esperar aplicar por su cuenta. El resto del catálogo
(en_proceso/en_pausa/rechazado/resuelto/de equipo/generales) sí son
decisión del operador — ver §4.8 más abajo.

Un operador no puede crear/editar/borrar etiquetas (eso es sólo de
`administradores`, desde el Admin Panel — 403 si se intenta).

## 4. Conversaciones

Todo lo de acá abajo está bajo `/api/core/conversaciones/` (DRF
`ConversacionViewSet` — sin alta/edición libre por diseño: una conversación
nace sólo cuando entra un mensaje real, y sólo cambia a través de estas
acciones puntuales, nunca un `PATCH` arbitrario).

### 4.1 `GET /api/core/conversaciones/?bandeja=<sin_asignar|mias>`

Bandeja. Sin el query param devuelve TODAS las de la organización (poco
útil para un operador en la práctica — usá siempre uno de los dos
filtros):

- `?bandeja=sin_asignar` — abiertas sin operador asignado, MÁS las que
  tenían un lock (`bloqueada_hasta`) ya vencido (ver §4.3): cualquier
  operador las puede reclamar.
- `?bandeja=mias` — abiertas, asignadas al operador logueado.

```json
{
  "count": 3, "next": null, "previous": null,
  "results": [
    {
      "id": 501,
      "contact": { "id": 88, "canal": "WHATSAPP", "identificador_externo": "5493511234567", "nombre": "" },
      "canal": "WHATSAPP", "canal_display": "WhatsApp",
      "operador": null, "operador_email": null,
      "team": 3, "team_nombre": "Ventas",
      "menu_finalizado": true,
      "bloqueada_hasta": null,
      "estado": "ABIERTA",
      "estado_operativo": "asignada",
      "iniciada_at": "2026-09-16T14:02:00Z",
      "cerrada_at": null,
      "updated_at": "2026-09-16T14:05:00Z"
    }
  ]
}
```

`estado_operativo` (string, calculado — no lo mandés vos, es sólo de
lectura) resume en qué paso del ciclo de vida está sin que tengas que
combinar `estado`/`team`/`operador` a mano:

| Valor | Cuándo |
|---|---|
| `"pendiente"` | `estado=ABIERTA`, sin `team` ni `operador` — recién entró, ni el menú la derivó todavía. |
| `"asignada"` | `estado=ABIERTA`, con `team` pero sin `operador` — está en la bandeja de un equipo, nadie la tomó. |
| `"tomada"` | `estado=ABIERTA`, con `operador` — alguien la está atendiendo. |
| `"cerrada"` | `estado=CERRADA`. |

Filtrar/ordenar por equipo, prioridad, etc. del lado del cliente sobre
`results` (la API no tiene hoy más filtros que `bandeja` — si hace falta
uno nuevo, pedilo en vez de tratar de simularlo del lado del cliente con
múltiples pedidos).

### 4.2 `GET /api/core/conversaciones/{id}/`

Detalle — mismo shape que un elemento de la lista de arriba.

### 4.3 `POST /api/core/conversaciones/{id}/tomar/`

Reclama la conversación para el operador logueado (funciona tanto para
tomar una sin asignar como para reclamar una cuyo lock de 2 minutos ya
venció). Devuelve la conversación actualizada (mismo shape que §4.1/4.2).

- **403 si la conversación todavía está "pendiente" (sin `team`, no
  derivada a ningún equipo)** y el usuario no tiene el permiso
  `conversations.tomar_sin_derivar` (pedido explícito 2026-10 — un
  operador común sólo puede tomar conversaciones ya derivadas; esperá a
  que el árbol de menú la derive sola, o pedile a un Admin que la derive
  a mano primero, §4.7). `administradores` tiene este permiso por
  default, un operador común no.
- 400 si otro operador la tiene tomada con el lock todavía vigente
  (`{"detail": ["Esta conversación está tomada por otro operador."]}`).
- El lock se renueva a 2 minutos en cada `tomar`/`responder` — si el
  cliente muestra "conversación tomada por vos", conviene re-llamar
  `tomar` (o `responder`) periódicamente mientras la pantalla siga
  abierta, para no perder la conversación por inactividad de red.

### 4.4 `GET /api/core/conversaciones/{id}/mensajes/`

El hilo COMPLETO con el contacto (lo que escribió el contacto + lo que
mandó el bot + lo que respondió el operador) — no confundir con
`notas-internas` (§4.8), que nunca sale hacia el contacto.

```json
[
  { "id": 9001, "remitente": "CONTACTO", "texto": "Hola, quería consultar", "creado_at": "2026-09-16T14:02:00Z" },
  { "id": 9002, "remitente": "SISTEMA", "texto": "¡Hola! Bienvenido...", "creado_at": "2026-09-16T14:02:01Z" },
  { "id": 9003, "remitente": "OPERADOR", "texto": "Hola, ¿en qué te ayudo?", "creado_at": "2026-09-16T14:05:00Z" }
]
```

`remitente` es siempre uno de `CONTACTO` / `OPERADOR` / `SISTEMA` (mensajes
automáticos del bot — bienvenida, menú, despedida). No paginado (es una
lista completa, no un listado — si una conversación termina siendo
larguísima en la práctica y hace falta paginar esto, pedirlo aparte).

### 4.5 `POST /api/core/conversaciones/{id}/responder/`

Manda un mensaje AL CONTACTO por el canal real (Core internamente le pega
a Channel Gateway — el cliente operador no ve ni necesita saber ese
detalle, ver §0).

```json
// Request
{ "texto": "Dale, ¿en qué te puedo ayudar?" }
// 200 OK
{ "entregado": true }
```

- 403 si la conversación no está tomada por VOS (`operador` tiene que ser
  el usuario logueado — tomarla primero, ver §4.3).
- 400 si ya está cerrada, o si `texto` viene vacío.
- `entregado: false` significa que Core pudo procesar el pedido pero
  Channel Gateway no confirmó la entrega (ej. `api_key` del canal vencida)
  — el mensaje YA quedó logueado en el hilo igual (`ConversacionLog`), no
  reintentes automáticamente, mostralo como advertencia.
- Renueva el lock de 2 minutos.
- `texto` puede llevar el marcado neutro del proyecto (sección 4.1.2 de
  `CONTEXTO_PROYECTO.md`): `**negrita**`, `_cursiva_`, `~tachado~`,
  `` `monoespaciado` `` — Core/Channel Gateway lo traducen (o lo
  descartan) según soporte el canal real; el cliente operador nunca arma
  sintaxis propia de WhatsApp ni de ningún otro canal (ver §0).

### 4.6 `POST /api/core/conversaciones/{id}/cerrar/`

```json
// 200 OK — mismo shape que §4.1, con estado="CERRADA" y cerrada_at seteado
```

- 403 si no está tomada por vos, 400 si ya estaba cerrada.
- **400 si la conversación no tiene ninguna `observacion` cargada todavía**
  (`{"error": {"code": "validation_error", "detail": {"observacion": ["Hace
  falta cargar al menos una observación antes de cerrar la conversación."]}}}`,
  pedido explícito 2026-10) — contá cualquiera de las dos vías válidas: una
  observación suelta (§4.9) o la que ya se crea sola al aplicar una
  etiqueta `resuelto`/`rechazado`/`en_pausa` (§4.8). Mostrale al operador
  el flujo "cargá una observación antes de poder cerrar" en vez de dejar
  que descubra el 400 recién al tocar "Cerrar".
- Dispara el mensaje de despedida configurado por el Admin, si hay uno.
- **No aplica sola ninguna etiqueta de resolución** — si el flujo de tu UI
  quiere que "resolver" también cierre la conversación, hacé las dos
  llamadas (primero `etiquetas` con `resuelto`/`rechazado` + observación,
  después `cerrar`), no asumas que una implica la otra.

### 4.7 `POST /api/core/conversaciones/{id}/derivar/`

Deriva a mano una conversación YA en curso a otro equipo — distinto de la
derivación automática que dispara el árbol de menú del bot (esa pasa sola,
antes de que un operador la vea). Vuelve a quedar **sin operador
asignado**, libre para que cualquiera del equipo destino la tome.

```json
// Request
{ "team": 5, "observacion": "No es un tema de Ventas, pasa a Soporte técnico." }
// 200 OK — mismo shape que §4.1, con team actualizado, operador=null, estado_operativo="asignada"
```

- `observacion` es **obligatoria** (texto no vacío) — pedido explícito de
  negocio, queda guardada para que el equipo destino tenga contexto (ver
  §4.9). 400 si viene vacía.
- 404 si `team` no existe o es de otra organización.
- 400 si la conversación ya está cerrada.

### 4.8 Etiquetas de una conversación puntual

#### `GET /api/core/conversaciones/{id}/etiquetas/`

```json
[
  {
    "id": 71,
    "etiqueta": { "id": 104, "team": null, "codigo": "en_proceso", "nombre": "En proceso", "color": "#F59E0B", "color_texto": "#FFFFFF", "es_sistema": true, "orden": 3, "created_at": "...", "updated_at": "..." },
    "aplicada_por_email": "operador@organizacion.test",
    "aplicada_at": "2026-09-16T14:10:00Z"
  }
]
```

#### `POST /api/core/conversaciones/{id}/etiquetas/`

```json
// Request — etiqueta general o de equipo, sin observación
{ "etiqueta": 109 }

// Request — una de las 3 etiquetas de sistema que exigen motivo
{ "etiqueta": 107, "observacion": "Se resolvió el reclamo, se le hizo la devolución." }

// 201 Created — la lista completa de etiquetas aplicadas, mismo shape que el GET
```

- Si `etiqueta` es una de las 7 de sistema, **saca cualquier otra etiqueta
  de sistema que ya estuviera aplicada** (son mutuamente excluyentes —
  sólo puede haber un estado de sistema activo a la vez). Las etiquetas
  generales y de equipo NO se tocan entre sí, son libremente acumulables.
- Si `etiqueta.codigo` es `resuelto`, `rechazado` o `en_pausa`,
  `observacion` es **obligatoria** — 400 con
  `{"observacion": ["Hace falta cargar una observación para marcar la conversación como «Resuelto»."]}`
  si viene vacía o falta. Cuando sí viene, además de aplicar la etiqueta
  queda registrada automáticamente en §4.9 (no hace falta el POST aparte).
- 404 si `etiqueta` no existe o es de otra organización.
- Volver a aplicar una etiqueta ya aplicada es idempotente (no falla, no
  duplica la fila — sólo actualiza quién/cuándo).

#### `DELETE /api/core/conversaciones/{id}/etiquetas/{etiqueta_id}/`

Quita una etiqueta aplicada (`etiqueta_id`, no el id de la fila puente).
204 si la sacó, 404 si esa etiqueta no estaba aplicada.

### 4.9 Observaciones (notas de resolución/contexto)

#### `GET /api/core/conversaciones/{id}/observaciones/`

```json
[
  { "id": 30, "operador_email": "operador@organizacion.test", "texto": "Cliente pidió que lo llamen mañana.", "creado_at": "2026-09-16T14:12:00Z" }
]
```

#### `POST /api/core/conversaciones/{id}/observaciones/`

```json
{ "texto": "Cliente pidió que lo llamen mañana." }
```

Se puede cargar en cualquier momento, libremente — a diferencia de las que
se crean solas al resolver/rechazar/pausar (§4.8), acá no hay ninguna
restricción de cuándo. 400 si `texto` viene vacío.

### 4.10 Notas internas entre operadores (acotadas a una conversación)

Hilo de mensajería ENTRE OPERADORES sobre una conversación puntual —
**nunca sale hacia Channel Gateway ni la ve el contacto** (a diferencia de
`mensajes`, §4.4). Es el "chat interno" pedido, con un alcance acotado —
ver la sección "Notas internas vs. chat interno" más abajo.

#### `GET /api/core/conversaciones/{id}/notas-internas/`

```json
[
  { "id": 12, "operador_email": "otro@organizacion.test", "texto": "¿Alguien ya habló con este cliente antes?", "creado_at": "2026-09-16T14:08:00Z" }
]
```

#### `POST /api/core/conversaciones/{id}/notas-internas/`

```json
{ "texto": "Sí, lo atendí la semana pasada por un tema de facturación." }
```

400 si `texto` viene vacío. Visible para cualquier operador de la
organización que pueda ver esa conversación (no está restringido a
quien la tiene tomada).

## 5. Formato de errores

Toda respuesta de error, en todos los endpoints, tiene la misma forma
(BUENAS-PRACTICAS-API-REST.md §4, implementado en
`common.exceptions.exception_handler`):

```json
{"error": {"code": "<código de máquina>", "detail": "<mensaje o dict de campos>"}}
```

`code` es un identificador estable en snake_case para lógica de cliente;
`detail` es un string para la mayoría de los errores, o un dict
`{"campo": ["mensaje"]}` cuando el error es de validación de uno o más
campos de un serializer.

- **400** `validation_error` — validación de campo(s):
  `{"error": {"code": "validation_error", "detail": {"campo": ["mensaje"]}}}`.
- **401** `not_authenticated` — falta o venció el JWT:
  `{"error": {"code": "not_authenticated", "detail": "..."}}`.
- **403** `permission_denied` — autenticado pero sin permiso (ej. un operador
  tratando de crear un equipo): `{"error": {"code": "permission_denied", "detail": "..."}}`.
- **404** `not_found` — no existe, o existe pero es de otra organización
  (nunca se distingue una cosa de la otra en la respuesta — un operador no
  debería poder inferir que algo existe en otra organización).
- **429** `throttled` — throttle general, o bloqueo por fuerza bruta de login
  (§1), que además incluye `blocked_until`:
  `{"error": {"code": "throttled", "detail": "...", "blocked_until": "2026-09-20T18:00:00Z"}}`.
- **500** `internal_error` — bug no controlado; nunca expone el traceback
  real (queda sólo en el log del servidor):
  `{"error": {"code": "internal_error", "detail": "Ocurrió un error interno. Volvé a intentar más tarde."}}`.

## 6. Paginación

`PageNumberPagination`, 25 por página. Todo listado (`GET` plural) devuelve
`{"count", "next", "previous", "results"}` — `next`/`previous` son URLs
completas ya armadas con `?page=N`, no hay que construirlas a mano.
`mensajes`/`etiquetas`/`observaciones`/`notas-internas` son la excepción:
devuelven una lista simple sin paginar (son el detalle de UNA conversación,
no un listado independiente).

## 7. Tiempo real — WebSocket de Conversation Engine

`services/conversation-engine` (FastAPI) entrega en tiempo real los
eventos que Core ya decidió y guardó — **nunca reemplaza el polling por
completo, lo complementa**: si la conexión se cae, no hay reconexión
automática todavía, o el evento se pierde por cualquier motivo, seguís
viendo lo mismo en el próximo refresh REST. Tratalo como una optimización
("enterate antes"), no como la única vía de verdad.

### 7.1 Conectar: `WS /ws/operador/{token}`

`token` es el MISMO `access` JWT de §1 (no hay login aparte para este
servicio) — como cualquier JWT, vence a los 30 minutos: si el `access`
vence mientras la conexión sigue abierta, Conversation Engine no la corta
sola (no revalida en cada mensaje), pero conviene reconectar con un
`access` fresco cada vez que lo renovás por `POST /api/auth/refresh/`, para
no quedar con un token vencido si la conexión se corta y hay que
reconectar.

- Si el token es inválido/vencido, el servidor cierra la conexión con el
  código WebSocket `4401` (rango privado 4000-4999) apenas intentás
  conectar — nunca llega a completarse el handshake. Ante esto, primero
  intentá `POST /api/auth/refresh/` y reconectar; si el `refresh` también
  venció, es un logout real.
- Un socket recibe TODOS los eventos de SU organización (no filtrados por
  equipo/operador puntual) — el payload trae `team_id`/`operador_id` para
  que decidas del lado tuyo si te importa o no.
- No hace falta mandar nada por el socket una vez conectado — es sólo de
  bajada (servidor → cliente). Cualquier texto que mandes se ignora.
- **No hay reconexión automática ni backoff del lado del servidor** —
  implementalo en el cliente (ej. reconectar con backoff exponencial si el
  socket se cierra inesperadamente, tope razonable de 30-60s entre
  intentos) y, mientras no esté conectado, apoyate en el polling de más
  abajo.

### 7.2 Eventos que recibís

Un JSON por mensaje, siempre esta forma (mismo contrato que
`POST /internal/eventos/` entre Core y Conversation Engine, no es
casualidad):

```json
{ "tipo": "mensaje_nuevo", "organization_id": 7, "conversacion_id": 501, "team_id": 3, "operador_id": null }
```

| `tipo` | Cuándo | Qué refrescar |
|---|---|---|
| `mensaje_nuevo` | Llega un mensaje del contacto (incluye el primer mensaje de una conversación nueva) — dispara igual haya habido o no una derivación de menú en el camino. | La bandeja (si no la tenías abierta) y/o `GET .../mensajes/` de esa `conversacion_id` si la tenías abierta. |
| `conversacion_actualizada` | `tomar`/`cerrar`/`derivar`/aplicar o quitar una etiqueta (§4.3, 4.6, 4.7, 4.8). | La bandeja, y el detalle de esa conversación si la tenías abierta (`estado_operativo` pudo cambiar). |
| `nota_interna_nueva` | Un operador agregó una nota interna (§4.10). | `GET .../notas-internas/` de esa `conversacion_id` si la tenías abierta. |

**Nunca** trae el texto real de un mensaje/nota/observación — es
deliberadamente mínimo (mismo criterio que §8 más abajo). Refrescá por
REST lo que te interese, no intentes reconstruir el dato a partir del
evento solo.

### 7.3 Si no hay conexión (fallback, siempre vigente)

- Bandeja (`?bandeja=sin_asignar`/`mias`): refrescar cada 10-15s alcanza
  para una bandeja compartida entre pocos operadores.
- Hilo de una conversación abierta en pantalla (`mensajes`,
  `notas-internas`): cada 3-5s mientras esa pantalla esté activa; pausar
  el polling cuando la app pasa a segundo plano.
- No hay endpoint de "hay algo nuevo desde el timestamp X" — cada poll
  trae la lista completa.

### 7.4 Qué NO hace este servicio (a propósito)

- No tiene su propia base de datos de negocio — no duplica
  `team`/`operador`/lock de una `Conversacion`, eso sigue viviendo
  enteramente en Core. Si el evento y el estado real en Core llegaran a
  desincronizarse por cualquier motivo, Core es siempre la fuente de
  verdad — nunca confíes en el payload del evento por sobre un GET fresco.
- No lleva un registro de "quién está conectado" persistente entre
  reinicios del servicio (`GET /organizations/{id}/conexiones-activas` —
  con el mismo Bearer de siempre en el header, no en la URL — cuenta las
  conexiones vivas del proceso actual, útil para un panel de estado, no
  para lógica de negocio del cliente).

## 8. Notificaciones push (roadmap — no implementado)

**Explícitamente fuera de alcance hoy** (sección 11 de
`CONTEXTO_PROYECTO.md`: "no implementar salvo pedido explícito") — esta
sección documenta el enfoque que se evaluó para no perderlo, no algo que
haya que construir todavía. Si en algún momento se decide implementarlo,
volver a este proyecto con el pedido explícito antes de escribir código.

Opción evaluada: **Firebase Cloud Messaging (FCM)**, porque es la vía
estándar de Android (y sirve igual para un futuro cliente iOS) y no
depende de mantener un socket abierto en segundo plano en el celular:

1. Core necesitaría un modelo nuevo (`DeviceToken` o similar: `user` FK +
   `token` FCM + `plataforma`) y un endpoint para que el cliente lo
   registre/actualice después de loguear (`POST /api/core/users/me/device-token/`,
   a definir).
2. Core dispararía un push (server-to-server contra la API de FCM, con la
   credencial de servicio del proyecto Firebase — nunca desde el cliente)
   en los mismos momentos que hoy ya disparan un evento de WebSocket (§7.2)
   — de hecho, el lugar natural para agregar esto es
   `conversations.conversation_engine_client.notificar_evento`, el mismo
   punto que ya sabe cuándo pasó algo relevante.
3. El payload del push sería mínimo (tipo de evento + `conversacion_id`) —
   el cliente, al recibirlo, refresca esa conversación puntual vía REST
   (nunca manda el contenido real del mensaje dentro del push), mismo
   criterio que ya usa el evento de WebSocket.
4. Alternativa más simple si el volumen no lo justifica todavía: dejar
   sólo el WebSocket + polling de §7 y no construir esto — es la opción de
   menor esfuerzo y ya cubre el caso de uso real (un operador con la app
   abierta). Push sólo agrega valor para "avisame aunque tenga la app
   cerrada", que es una decisión de producto a confirmar antes de construir
   la infraestructura de Firebase (cuenta de servicio, credenciales,
   quién paga/administra el proyecto Firebase, etc.).

## 9. Qué NO existe todavía (no lo simules del lado del cliente)

- Reconexión automática del WebSocket (§7.1 — hoy es responsabilidad
  100% del cliente).
- Notificaciones push (§8).
- Selección nativa de menú por canal en el lado del OPERADOR (eso es
  Channel Gateway hablándole al CONTACTO, no afecta este contrato).
- Un endpoint para que el operador "libere" a mano una conversación
  tomada sin cerrarla ni derivarla (hoy sólo se libera por el lock de 2
  minutos venciendo, o por `derivar`).
- Respuestas predefinidas / templates de mensajes para el operador
  (mencionado en la sección 9 de `CONTEXTO_PROYECTO.md`, no implementado).
- Asignación round-robin manual vía API (hoy sólo la dispara una
  derivación del árbol de menú, `conversations.asignacion.asignar_round_robin`).

Si alguno de estos hace falta para lo que estás construyendo, es señal
para pedirlo explícitamente y extender Core — no para improvisar un
workaround en el cliente ni para hablarle directo a un canal externo.
