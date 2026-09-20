# Requerimientos técnicos — Operators Desk Web (`frontend/operators-desk-web`)

Guía para el agente (persona o IA) que construya este frontend. Es la
contraparte de escritorio de la app Android de operadores
(`UDCOperadorAPP`) — las dos son clientes del **mismo contrato de API**,
documentado exhaustivamente en
[`operators-desk-api-contract.md`](operators-desk-api-contract.md). Este
documento no repite ese contrato endpoint por endpoint (para eso está el
otro, y está desactualizado apenas los dos empiecen a divergir) — acá está
el "qué construir" del lado de la pantalla y un resumen de con quién habla,
para arrancar sin tener que leer primero las ~600 líneas del contrato
completo.

Contexto completo del proyecto (arquitectura de los 6 microservicios, qué
está implementado vs. planeado, convenciones transversales):
[`CONTEXTO_PROYECTO.md`](CONTEXTO_PROYECTO.md).

**Estado actual**: `frontend/operators-desk-web` todavía no existe como
carpeta (Fase 4/`services/operators-desk` es un stub — ver más abajo por
qué esto no bloquea construir el frontend ya). Este documento es la
especificación para crearlo.

## 0. Regla de oro — con quién habla este frontend

**Únicamente con `services/core` (Django, negocio) y `services/
conversation-engine` (FastAPI, tiempo real) — nunca con WhatsApp/Messenger/
Instagram, la Graph API de Meta, ni `services/channel-gateway`.** Core
decide todo el negocio (a qué equipo deriva una conversación, cuándo un
canal está fuera de horario, qué mensaje de bienvenida corresponde) y es
quien internamente le habla a Channel Gateway para entregar un mensaje al
contacto — este frontend no tiene por qué saber que Channel Gateway existe.

Nota sobre `services/operators-desk` (el "Operators Desk Service" de la
Fase 4 planeada, puerto 8004): hoy es sólo un stub (`/health`). El contrato
real y ya construido para atender chats vive directo en Core +
Conversation Engine — no esperes a que ese servicio exista para construir
este frontend, y no le hables a él (no tiene lógica todavía).

Consecuencia práctica: este frontend nunca necesita ningún SDK/credencial
de Meta, ni token de página/WABA, ni le importa qué es un `webhook_secret`
— eso es enteramente responsabilidad del backend. Si alguna pantalla
pareciera necesitar hablarle a algo que no sea Core o Conversation Engine,
es señal de que falta un endpoint en Core — pedilo ahí, no lo resuelvas acá
con un workaround.

## 1. Para quién es y qué NO es

- Es la herramienta de trabajo diaria del rol **operador** (grupo
  `operadores`) para atender chats de WhatsApp/Messenger/Instagram (y,
  eventualmente, Webchat — ver el documento hermano) derivados por el bot.
- **No es** el Admin Panel (`frontend/admin-panel`) — ese es sólo
  configuración/administración (organizaciones, canales, menú, usuarios,
  equipos, historial de auditoría). Nunca dupliques ahí pantallas de
  atención de chats, y nunca traigas acá pantallas de administración: un
  operador de hoy no tiene ningún permiso de Core más allá de leer/actuar
  sobre conversaciones, equipos (solo lectura) y etiquetas (solo lectura) —
  ver `GET /api/core/users/me/` → `permissions`.
- El **historial de conversaciones** (con filtros, agrupado por
  organización) es una pantalla exclusiva de `administradores`/superusuario
  de plataforma en el Admin Panel (`conversations.ver_historial_
  conversacion`) — un operador no tiene ese permiso y no debe verlo acá.

## 2. Autorización — nunca por nombre de grupo

`GET /api/core/users/me/` devuelve `permissions` (lista plana de
`app.codename`) — es lo único que debe decidir qué se renderiza. Nunca
compares contra el string `"operadores"` ni contra ningún otro nombre de
grupo: el día que se sume un rol nuevo con acceso parcial a esta pantalla,
un chequeo por nombre de grupo se rompe silenciosamente y uno por permiso
no.

## 3. Requerimientos funcionales

### 3.1 Sesión y perfil
- Login (`POST /api/auth/login/`) con manejo explícito de: credenciales
  inválidas (401), bloqueo por fuerza bruta a la 3ª falla (429 +
  `blocked_until`), y `must_change_password=true` (forzar el cambio de
  contraseña antes de dejar entrar a la bandeja).
- Guardar `access` **y** `refresh` (30 min / 7 días) y refrescar
  automáticamente ante un 401 antes de forzar logout — no asumir que la
  sesión dura toda la jornada del operador sin refrescar.
- Pantalla de perfil: editar nombre/apellido/DNI/avatar, cambiar
  contraseña. Nunca editable acá: grupo, organización.

### 3.2 Bandeja compartida
- Dos vistas con el mismo componente de lista, alimentadas por
  `?bandeja=sin_asignar` y `?bandeja=mias` — nunca el listado sin filtro
  (trae toda la organización, no es útil en la práctica).
- Cada fila muestra `estado_operativo` (`pendiente`/`asignada`/`tomada`/
  `cerrada`, ya calculado por Core — no lo recalcules combinando `estado`/
  `team`/`operador` a mano) con un badge de color, canal, contacto y hace
  cuánto se actualizó.
- Filtrar/ordenar por equipo del lado del cliente sobre `results` (la API
  no tiene más filtros que `bandeja` hoy).
- Refrescar automáticamente ante los eventos de tiempo real (§3.5) y con
  polling de respaldo cada 10-15s mientras la bandeja está en pantalla.

### 3.3 Vista de una conversación
- Hilo completo (`GET .../mensajes/`) distinguiendo visualmente
  `CONTACTO`/`OPERADOR`/`SISTEMA` (mensajes automáticos del bot).
- **Notas internas** (`GET/POST .../notas-internas/`) en un panel/pestaña
  separada del hilo — nunca mezcladas visualmente con los mensajes reales,
  ya que estas nunca salen hacia el contacto y las otras sí.
- **Observaciones** (`GET/POST .../observaciones/`) como bitácora de
  contexto, distinta de las notas internas (una es libre en cualquier
  momento, la otra queda ligada a por qué se resolvió/rechazó/pausó algo —
  ver `etiquetas`).
- Poll de este hilo cada 3-5s mientras la pantalla está activa; pausar si
  la pestaña/ventana pasa a segundo plano.

### 3.4 Acciones sobre una conversación
- **Tomar** (`POST .../tomar/`): deshabilitar el botón mientras está
  tomada por otro con el lock vigente (400 con mensaje explícito); mostrar
  quién la tiene si se puede inferir.
- **Responder** (`POST .../responder/`): editor de texto con el marcado
  neutro del proyecto (`**negrita**`, `_cursiva_`, `~tachado~`,
  `` `mono` ``) y una previsualización — reutilizar `MessageEditor`/
  `WhatsAppPreview` del Admin Panel si se puede compartir código entre los
  dos frontends, en vez de reescribir el toolbar. Mostrar advertencia (no
  reintento automático) si la respuesta vuelve con `entregado: false`.
- **Renovación del lock**: `tomar`/`responder` lo renuevan a 2 minutos —
  mientras la pantalla de una conversación tomada siga abierta, no dejar
  que expire por inactividad de red; considerar un ping periódico o
  renovarlo en cada interacción real del operador.
- **Derivar** (`POST .../derivar/`): selector de equipo (`GET /api/core/
  teams/`, solo lectura) + campo de observación obligatorio (400 si viene
  vacío) — la conversación queda sin operador asignado después de esto.
- **Cerrar** (`POST .../cerrar/`): confirmar antes de ejecutar (es
  irreversible desde esta pantalla — no hay "reabrir"). No asume que cierra
  sola una etiqueta de resolución: si el flujo de la UI quiere que
  "resolver" también cierre, encadenar las dos llamadas explícitamente.
- **Etiquetas** (`GET/POST/DELETE .../etiquetas/`): las 7 de sistema son
  mutuamente excluyentes entre sí (aplicar una saca cualquier otra de
  sistema); `resuelto`/`rechazado`/`en_pausa` piden `observacion`
  obligatoria (400 explícito si falta). Las de equipo/generales son
  libremente acumulables aparte.

### 3.5 Tiempo real (WebSocket de Conversation Engine) + fallback
- Conectar `WS /ws/operador/{token}` con el mismo `access` JWT de Core al
  loguear, y reconectar con backoff exponencial (tope razonable 30-60s) si
  se corta — no hay reconexión automática del lado del servidor.
- Si el servidor cierra con código `4401`, intentar `POST /api/auth/
  refresh/` y reconectar antes de asumir logout.
- Tres tipos de evento (`mensaje_nuevo`, `conversacion_actualizada`,
  `nota_interna_nueva`) — ninguno trae datos reales, son sólo un aviso de
  "refrescá X por REST". Mientras el socket no esté conectado, apoyarse
  enteramente en el polling de §3.2/§3.3 (nunca dejar la UI sin ninguna vía
  de actualización).
- **Notificación de escritorio del navegador** (`Notification` API,
  puramente del lado del cliente, sin backend nuevo): al recibir
  `mensaje_nuevo` de una conversación que el operador no tiene abierta en
  foco, disparar una notificación/sonido — esto es una decisión 100% de
  este frontend reaccionando a un evento que ya recibe, **no** el sistema
  de push (FCM) documentado como fuera de alcance en el contrato de API
  §8 — no confundir los dos ni empezar a construir infraestructura de
  Firebase por esto.

### 3.6 Multi-conversación (propio de un panel de escritorio)
- A diferencia de un celular, un operador de escritorio típicamente
  atiende más de una conversación a la vez — contemplar un layout de
  columnas/pestañas que permita tener 2-3 conversaciones abiertas en
  paralelo sin perder el estado de cada una (borrador de respuesta sin
  enviar incluido) al cambiar de pestaña.

### 3.7 Manejo de errores
- Formato DRF estándar en todos los endpoints (§5 del contrato de API) —
  parsear de forma genérica (`detail` primero, si no está, el primer campo
  con mensajes), nunca un mensaje fijo hardcodeado por endpoint.
- 404 nunca distingue "no existe" de "existe pero es de otra
  organización" — no intentar inferir esa diferencia en la UI.

## 4. Seguridad / multi-tenant

- Nunca mandar `organization_id` a mano en ningún request — el JWT ya
  scopea todo del lado del servidor.
- Nunca decidir qué renderizar mirando el nombre de un grupo (ver §2).
- El JWT no hace falta decodificarlo nunca del lado del cliente para nada
  de negocio — `GET /api/core/users/me/` ya da todo resuelto.

## 5. Correr Core + Conversation Engine localmente para desarrollar

Desde la raíz del monorepo:

```bash
cp .env.example .env   # una vez, si no existe
docker compose up --build core conversation-engine
# datos de prueba (organización + usuarios + equipos + menú), idempotente:
docker compose run --rm --entrypoint python core manage.py seed_ucd_demo
```

`seed_ucd_demo` deja usuarios de prueba de distintos grupos — revisar
`services/core/organizations/management/commands/seed_ucd_demo.py` para
las credenciales exactas, incluido al menos un usuario del grupo
`operadores` para loguear desde este frontend.

Documentación interactiva sin login (Swagger/Redoc, útil ante cualquier
duda de shape exacto que este documento no cubra): ver la tabla de la
sección "Documentación interactiva" al principio de
[`operators-desk-api-contract.md`](operators-desk-api-contract.md).

## 6. Antes de dar por terminada una pantalla nueva

1. Confirmar que el request que arma coincide EXACTO con el ejemplo del
   contrato de API (nombres de campo, method, si va paginado) — no
   improvisar un shape "parecido".
2. Si el endpoint que necesitás no está en el contrato, no existe todavía
   en Core: pedirlo, no inventar un workaround de cliente (y menos uno que
   hable con un canal externo directamente — ver §0).
3. Probar contra un Core + Conversation Engine locales reales (§5), no
   sólo contra datos mockeados — varios endpoints tienen reglas de negocio
   con estados intermedios (locks de 2 minutos, observación obligatoria en
   ciertas etiquetas) que sólo se notan probando contra el backend real.
4. Si la pantalla comparte lógica visual con el Admin Panel (editor de
   texto con marcado neutro, badges de etiqueta), evaluar extraer el
   componente a un paquete compartido en vez de reimplementarlo — no hay
   ninguno hoy, así que el primero que lo necesite en los dos frontends es
   quien decide esa estructura.
