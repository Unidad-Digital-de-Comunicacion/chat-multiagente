# Requerimientos técnicos — Widget de chat web embebible (Webchat)

Guía para el agente (persona o IA) que en algún momento construya el canal
Webchat completo: el widget embebible (lo que corre en el navegador del
visitante) y `services/webchat` (su backend, hoy sólo un stub). **Este
documento es una especificación, no una autorización para empezar a
construir**: `CONTEXTO_PROYECTO.md` marca explícitamente a Webchat como
"opcional / fast-follow — no construir hasta que se pida explícitamente".
Si te llega este documento como tarea, confirmá primero si ya hay un pedido
explícito de construirlo o si por ahora sólo hace falta la especificación.

Contexto completo del proyecto (arquitectura de los 6 microservicios, qué
está implementado vs. planeado, convenciones transversales):
[`CONTEXTO_PROYECTO.md`](CONTEXTO_PROYECTO.md) — en particular sección 3
(tabla de servicios, fila 6), sección 4.1.1 (selección nativa por canal,
fila Webchat), sección 4.1.2 (formato de texto por canal, fila Webchat) y
sección 4.6 (`WebchatSession`).

## 0. Regla de oro — con quién habla cada pieza

**El widget (navegador del visitante) nunca habla directo con Core.** Igual
que WhatsApp/Messenger/Instagram tienen a Channel Gateway en el medio,
Webchat tiene a `services/webchat` en el medio — es el "Channel Gateway"
de este canal. El visitante no tiene una cuenta ni un JWT de usuario real;
tratarlo como un cliente de confianza igual a un operador logueado sería un
error de seguridad, no sólo de capas.

```
Widget (navegador del visitante, sitio de terceros)
   │  WebSocket / REST (a definir, §3)
   ▼
Webchat Service (services/webchat, FastAPI, puerto 8006 — HOY UN STUB)
   │  POST /api/core/bot/mensaje-entrante/  (Service-Token, igual que Channel Gateway)
   ▼
Core (services/core, Django) — decide TODO el negocio: árbol de menú,
horario hábil, a qué equipo deriva. Nunca el widget, nunca Webchat Service.
```

Cuando Core decide derivar la conversación a un equipo, es **Core mismo**
quien avisa a Conversation Engine (`conversations.
conversation_engine_client.notificar_evento` — ver `services/core/
conversations/conversation_engine_client.py`) para que el operador la vea
en tiempo real; Webchat Service no necesita hablarle directo a
Conversation Engine para eso, ni duplicar esa lógica.

Cuando un operador humano responde desde el Admin Panel/Operators Desk Web
(`POST .../responder/`), es **Core** quien le pide a Webchat Service que
entregue ese mensaje al visitante — dirección inversa, mismo patrón que
`conversations.channel_gateway_client.enviar_mensaje_saliente` usa hoy
contra Channel Gateway (`POST /messages/send`). Webchat Service necesitaría
un endpoint equivalente (a definir, §3.3) que reciba ese pedido y lo
empuje por el WebSocket abierto del visitante correspondiente.

Autenticación entre servicios: `ServiceToken` — el enum ya tiene
`Servicio.WEBCHAT` reservado en `platform_admin/models.py`, mismo mecanismo
de secreto compartido que usan Channel Gateway/Conversation Engine hoy
(sección 9 de `CONTEXTO_PROYECTO.md`). No inventar un esquema de auth
nuevo para este servicio.

## 1. Para quién es y qué NO es

- Es un chat embebible para el **sitio web propio de una organización
  cliente** (ej. `<script>` pegado en su landing) — un canal más además de
  WhatsApp/Messenger/Instagram, no un reemplazo de ninguno.
- El usuario del otro lado es un **visitante anónimo**, no un usuario de la
  plataforma — no tiene login, no tiene JWT, no aparece en `users`.
- No es una alternativa al Admin Panel ni al Operators Desk Web — un
  operador sigue atendiendo esta conversación exactamente igual que
  cualquier otra (misma bandeja, mismas acciones), el widget es sólo el
  canal de entrada/salida del lado del visitante.

## 2. Arquitectura propuesta

### 2.1 El widget
- Snippet de instalación mínimo: un `<script>` que cualquier sitio pega
  una vez, parametrizado con `organization_id` (o un identificador público
  del canal, análogo al `uuid` que ya usan los webhooks de Meta — no
  reutilizar directamente `organization_id` numérico expuesto en HTML sin
  evaluarlo, para no filtrar un ID interno correlacionable).
- Corre en el dominio de un tercero (el sitio del cliente) — cuidar CORS y
  CSP del lado de `services/webchat` en consecuencia; nunca asumir que
  corre en un dominio propio de la plataforma.
- Burbuja minimizada/expandida, responsive para el visitante (mobile y
  desktop del lado del VISITANTE, no confundir con el "Operators Desk Web"
  que es de escritorio para el operador).

### 2.2 Identidad del visitante (sin login)
- `visitor_id` (UUID) generado la primera vez y persistido en
  `localStorage`/cookie del sitio del cliente — se reutiliza en visitas
  siguientes del mismo navegador para retomar la conversación, siguiendo el
  modelo `WebchatSession` (organization_id, visitor_id, estado) de
  `CONTEXTO_PROYECTO.md` §4.6, con el mismo patrón que `Channel`/`Contact`
  para los demás canales.
- Recargar la página del sitio del cliente **no debe perder el hilo** —
  al reconectar con el mismo `visitor_id`, el widget debe poder recuperar
  los últimos mensajes de esa sesión.
- Datos opcionales para identificar mejor al contacto en Core
  (`Contact.nombre`): nombre/teléfono, nunca obligatorios ni pedidos como
  credenciales.

### 2.3 Webchat Service (`services/webchat`)
Rol equivalente al de Channel Gateway para este canal — sin lógica de
negocio propia, sólo I/O:
- Recibe el mensaje del visitante y le pega a Core
  (`POST /api/core/bot/mensaje-entrante/` con `channel="WEBCHAT"` — ver
  §3.1) para que decida qué hacer, exactamente igual que Channel Gateway lo
  hace hoy para WhatsApp/Messenger/Instagram.
- Mantiene la conexión WebSocket abierta por visitante para poder
  empujarle: la respuesta del bot, la selección nativa de menú (§2.4), y
  los mensajes de un operador humano una vez derivada la conversación.
- No decide nunca a qué equipo deriva, ni qué dice el mensaje de
  bienvenida, ni si está fuera de horario — todo eso ya viene resuelto en
  la respuesta de Core (`acciones`, ver §3.1).

### 2.4 Selección nativa de menú (ya contemplado, no diseñar de nuevo)
Por `CONTEXTO_PROYECTO.md` §4.1.1, Webchat debe mostrar el menú como
botones nativos del widget (no texto numerado) siempre que Core mande
`opciones: [{id, titulo}]` — sin el límite artificial que sí tienen
WhatsApp/Messenger (son botones propios, no de una API externa). El texto
numerado es sólo el fallback si por algún motivo el widget no puede
renderizar botones en ese momento.

### 2.5 Formato de texto
Por `CONTEXTO_PROYECTO.md` §4.1.2, el marcado neutro (`**negrita**`,
`_cursiva_`, `~tachado~`, `` `mono` ``) se deja tal cual o se convierte a
HTML del lado del widget — Webchat es el único canal donde no hace falta
descartar ni traducir a una sintaxis ajena, porque el renderer es propio.

## 3. Contrato de comunicación (a construir — hoy no existe)

### 3.1 Webchat Service → Core (ya existe, reutilizar tal cual)

```
POST /api/core/bot/mensaje-entrante/
Authorization: Service-Token <token del servicio WEBCHAT>

{ "organization_id": 7, "channel": "WEBCHAT", "contact_externo_id": "<visitor_id>", "texto": "Hola" }

// 200 OK
{ "acciones": [
    { "tipo": "enviar_texto", "texto": "¡Hola! Bienvenido..." },
    { "tipo": "mostrar_menu", "texto": "Elegí una opción", "encabezado": "Menú principal",
      "opciones": [{ "id": "1", "titulo": "Ventas" }, { "id": "2", "titulo": "Soporte" }] }
] }
```

Mismo endpoint que usa Channel Gateway (`services/channel-gateway/app/
core_client.py::enviar_mensaje_entrante`) — `contact_externo_id` es el
`visitor_id` en este canal (donde en WhatsApp sería el teléfono). Si Core
no contesta, tratarlo igual que Channel Gateway: el mensaje ya quedó
recibido, simplemente no hay ninguna acción que ejecutar todavía.

### 3.2 Core → Conversation Engine (ya existe, no es responsabilidad de Webchat Service)

Core dispara esto solo cuando corresponde (derivación, nuevo mensaje,
etc.) — Webchat Service no necesita ni debe llamarlo directamente.

### 3.3 Core → Webchat Service (a definir — no existe todavía)

Falta un endpoint análogo a `POST /messages/send` de Channel Gateway
(`services/core/conversations/channel_gateway_client.py`) para que, cuando
un operador responde (`POST .../responder/`), Core pueda pedirle a Webchat
Service que entregue ese texto al visitante correcto:

```
POST /messages/send          (propuesta, a definir junto con la implementación)
Authorization: Service-Token <token del servicio WEBCHAT>

{ "visitor_id": "<uuid>", "texto": "Dale, ¿en qué te puedo ayudar?" }
```

Webchat Service usaría esto para empujar el texto por el WebSocket abierto
de ese `visitor_id` (o encolarlo si no está conectado en ese momento — a
decidir junto con cuánto tiempo se espera que dure una sesión de visitante
desconectada).

### 3.4 Widget ↔ Webchat Service (a definir — no existe todavía)

Ejemplos de shape a definir en el momento de construir (no vinculantes,
sólo para no arrancar de cero):

- `POST /sessions/` → crea o recupera una `WebchatSession` a partir de
  `organization_id` (o su identificador público) + `visitor_id` (si ya
  existía en `localStorage`); devuelve el historial reciente de esa sesión.
- `WS /ws/visitante/{visitor_id}` → igual de "sólo bajada más un puñado de
  eventos" que el contrato de Conversation Engine para operadores
  (`operators-desk-api-contract.md` §7) — el widget manda el mensaje por
  REST (`POST /mensajes/`) y escucha la respuesta por el socket, no al
  revés.

## 4. Requerimientos funcionales del widget

- Snippet de instalación configurable (color/posición/mensaje de
  bienvenida) sin tocar el sitio del cliente más que una vez.
- Persistencia de la sesión del visitante entre recargas de página
  (§2.2).
- Selección nativa de opciones de menú, no texto numerado (§2.4).
- Traspaso a un operador humano transparente para el visitante — no debe
  notar una diferencia técnica entre "le contesta el bot" y "le contesta
  una persona", salvo el mensaje de sistema que ya arma Core.
- Respeto del horario hábil de la organización igual que cualquier otro
  canal (lo decide Core, el widget sólo muestra el texto que le llega).
- Indicador de conectado/"escribiendo…" — deseable, no bloqueante para una
  primera versión.
- Personalización básica de marca por organización (logo, color, texto de
  bienvenida) — implica una pantalla de configuración nueva en el Admin
  Panel (no existe hoy), a diseñar junto con quien construya el backend.
- Nunca pedir credenciales ni datos sensibles del visitante.

## 5. Qué NO construir todavía

- Nada de este documento hasta tener el pedido explícito mencionado al
  principio — esto es intencionalmente una especificación adelantada, no
  una tarea en curso.
- Un esquema de base de datos `webchat` real (hoy `services/webchat` es
  sólo `app/main.py` con `/health`).
- La pantalla de personalización de marca en el Admin Panel.
- Cualquier mecanismo de reconexión/cola para visitantes desconectados más
  sofisticado que lo mínimo — evaluar el caso de uso real antes de
  construir algo elaborado (mismo criterio que el resto del proyecto:
  preferir la opción más simple que cubra el caso real).

## 6. Primer paso real si esto se aprueba

Antes de escribir código: sumar una sección de Fase propia en
`CONTEXTO_PROYECTO.md` §10 con el diseño final acordado (esquema de DB,
shape exacto de cada endpoint, qué pasa con un visitante que vuelve después
de días) — este documento es la base para esa conversación, no el
reemplazo de tenerla.
