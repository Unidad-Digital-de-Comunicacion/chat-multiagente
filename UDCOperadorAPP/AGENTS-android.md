# AGENTS.md — app Android de operadores (`UDCOperadorAPP`)

Guía para quien (persona o agente) trabaje en esta app. Es la contraparte
mobile de `frontend/operators-desk-web` (React, todavía no creado) — las
dos son clientes del **mismo contrato de API**, documentado en
[`docs/operators-desk-api-contract.md`](../docs/operators-desk-api-contract.md)
(raíz del repo). Leelo antes de tocar cualquier pantalla nueva — este
archivo es sólo el "cómo" del lado Android, el "qué" (endpoints, formato
de cada request/response, reglas de negocio) vive ahí.

Contexto completo del proyecto (arquitectura de los 6 microservicios, qué
está implementado vs. planeado, convenciones transversales):
[`docs/CONTEXTO_PROYECTO.md`](../docs/CONTEXTO_PROYECTO.md).

Swagger/Redoc de los dos servicios que importan acá (Core y Conversation
Engine) no piden login para abrirse — URLs exactas y qué le falta a cada
uno (Conversation Engine no documenta el WebSocket, OpenAPI no puede) en
la sección "Documentación interactiva" del contrato de API, arriba del
todo.

## Regla de oro: esta app le habla únicamente a Core

Todo pedido de red de esta app va contra `services/core` (Django, puerto
8001) — **nunca** contra WhatsApp/Messenger/Instagram, la Graph API de
Meta, ni `services/channel-gateway`. Core es quien decide el negocio y
quien internamente le pega a Channel Gateway para entregar un mensaje al
contacto; esta app no tiene por qué saber que eso existe. Si alguna
funcionalidad pareciera necesitar hablarle a un canal externo
directamente, es señal de que falta un endpoint en Core — pedilo ahí, no
lo resuelvas acá adentro. (Ver sección 0 del contrato de API, y sección
2.1 "Core decide, todo lo demás ejecuta" de `CONTEXTO_PROYECTO.md`.)

Consecuencia práctica: esta app nunca necesita ningún SDK/credencial de
Meta, ni token de página/WABA, ni sabe qué es un `webhook_secret` — eso es
enteramente responsabilidad del backend.

## Estado actual del código

- `LoginActivity` — pantalla de login real, ya le pega a
  `POST /api/auth/login/` (ver contrato §1) y guarda el `access` token con
  `Sesion`.
- `HttpCliente` — wrapper mínimo sobre `HttpURLConnection` (sin librería
  externa todavía). Corre las llamadas en un `Thread` aparte a mano — toda
  pantalla nueva que haga red tiene que seguir ese mismo patrón (nunca red
  en el hilo principal).
- `Sesion` — persiste el token en `SharedPreferences`. **Pendiente**: hoy
  sólo guarda `access` (vence a los 30 minutos) — falta guardar también
  `refresh` y usar `POST /api/auth/refresh/` cuando un pedido devuelva 401,
  antes de forzar un logout.

Package base: `com.udc.operador`. Nombres de variables/métodos/comentarios
en español, igual que el resto del repo (`services/core` está en español
salvo nombres de módulos nuevos en inglés) — seguí esa convención acá
también.

## Red: URL base según dónde corra

- Emulador de Android + `docker compose up core` corriendo en tu propia
  PC: `http://10.0.2.2:8001/` (`10.0.2.2` es la IP especial que el
  emulador traduce a "localhost de la PC host").
- Celular físico en la misma red que el servidor: la IP LAN real de esa PC
  (no `10.0.2.2`, no le sirve a un dispositivo físico).
- Servidor real (cuando exista un dominio/IP pública para `core`): esa URL,
  sin cambiar nada del resto del código — la base URL debería vivir en un
  solo lugar (constante o `BuildConfig`, no repetida en cada Activity) para
  poder cambiarla sin buscar en todo el proyecto. Si el código actual
  todavía tiene la URL hardcodeada en más de un lugar (`LoginActivity` hoy
  la tiene sólo ahí), centralizarla es una mejora real a hacer apenas se
  toque una segunda pantalla que necesite hacer red.

## Convenciones a seguir para pantallas nuevas

- **Nunca mandar `organization_id` a mano** — el JWT ya scopea todo del
  lado del servidor; ni hace falta ni el backend lo aceptaría como
  override.
- **No decidir qué mostrar mirando el nombre de un grupo** (`"operadores"`
  como string) — usar `GET /api/core/users/me/` → `permissions` si en
  algún momento la app necesita ese tipo de chequeo (hoy la app sólo la
  usan operadores, así que en la práctica no hace falta todavía, pero no
  hardcodear el string igual si se llega a necesitar).
- **Formato de errores**: siempre el shape DRF estándar del contrato §5
  (`{"campo": [...]}` o `{"detail": "..."}"`) — parsear de forma genérica
  (buscar `detail` primero, si no está, tomar el primer campo con
  mensajes), no asumir un mensaje fijo por endpoint.
- **WebSocket de Conversation Engine + polling como fallback** (contrato
  §7) — `WS /ws/operador/{token}` con el mismo `access` JWT de Core, eventos
  mínimos que sólo te avisan "refrescá X por REST", nunca datos en sí. Sin
  reconexión automática del lado del servidor: implementarla en el
  cliente (backoff exponencial, tope 30-60s) y seguir con el polling de
  §7.3 mientras el socket no esté conectado. No inventar un mecanismo de
  notificación propio distinto del documentado ahí.
- **Notificaciones push**: explícitamente no implementado (contrato §8) —
  no agregar Firebase/FCM a este proyecto sin que alguien lo pida
  explícitamente primero, aunque el contrato ya documente el enfoque
  evaluado.

## Correr Core localmente para desarrollar contra él

Desde la raíz del monorepo (no desde acá):

```bash
cp .env.example .env   # una vez, si no existe
docker compose up --build core
# opcional, datos de prueba (organización + usuarios + equipos + menú):
docker compose run --rm --entrypoint python core manage.py seed_ucd_demo
```

`seed_ucd_demo` deja usuarios de prueba con distintos grupos — revisar el
management command (`services/core/organizations/management/commands/
seed_ucd_demo.py`) para las credenciales exactas que crea, incluido al
menos un usuario del grupo `operadores` para loguear desde esta app.

## Antes de dar por terminada una pantalla nueva

1. Confirmar que el request que arma coincide EXACTO con el ejemplo del
   contrato de API (nombres de campo, method, si va paginado) — no
   improvisar un shape "parecido".
2. Si el endpoint que necesitás no está en el contrato, no existe todavía
   en Core: hay que pedirlo (no inventar un workaround de cliente, y menos
   uno que hable con un canal externo — ver la regla de oro arriba).
3. Probar contra un Core local real (arriba), no sólo contra datos
   mockeados a mano — varios de estos endpoints tienen reglas de negocio
   con estados intermedios (locks de 2 minutos, observación obligatoria en
   ciertas etiquetas) que sólo se notan probando contra el backend real.
