# Cambios en Core que afectan a los clientes operador

Para quien mantiene `services/operators-desk/web` (React) y `UDCOperadorAPP`
(Android) — mismo contrato de API para los dos
(`docs/operators-desk-api-contract.md`, ya actualizado con todo esto en
§3, §4.3 y §4.6). Rama: `feat-reglas-cierre-y-etiquetas-sistema`.

## Resumen: no hace falta tocar código para que siga funcionando

Los dos clientes ya extraen el mensaje de error con
`extraerMensajeDeError(err)` (o su equivalente en Android), que lee
`error.detail` de la respuesta — los dos casos nuevos de abajo ya le
llegan con un mensaje armado, así que **no se rompe nada** aunque no se
toque una línea. Lo que sigue son 3 cambios de comportamiento a tener en
cuenta, y 2 mejoras de UX recomendadas (no obligatorias).

## 1. `POST .../tomar/` ahora puede dar 403

Antes: cualquier operador podía tomar cualquier conversación, incluida una
recién llegada sin derivar todavía ("pendiente").

Ahora: **sólo se puede tomar una conversación ya derivada a un equipo**
(`estado_operativo` distinto de `"pendiente"`). Si se intenta tomar una
pendiente sin el permiso `conversations.tomar_sin_derivar` (que
`administradores` tiene por default, un operador común no), devuelve:

```json
// 403
{"error": {"code": "permission_denied", "detail": "Esta conversación todavía no fue derivada a un equipo."}}
```

**Recomendado (no obligatorio):** en la bandeja "Sin asignar", no mostrar
el botón "Tomar" para las filas con `estado_operativo === "pendiente"` —
hoy ese botón se muestra siempre que `bandeja === "sin_asignar"`, sin
mirar el estado. Evita que el operador vea un error al tocarlo en vez de
simplemente no poder.

## 2. `POST .../cerrar/` ahora puede dar 400

Antes: se podía cerrar sin haber dejado ninguna constancia de qué pasó.

Ahora: **hace falta al menos una observación** antes de cerrar — cuenta
tanto una cargada a mano (`POST .../observaciones/`) como la que ya se
crea sola al aplicar una etiqueta `resuelto`/`rechazado`/`en_pausa`
(no hace falta cargar una segunda aparte en ese caso). Si no hay ninguna:

```json
// 400
{"error": {"code": "validation_error", "detail": {"observacion": ["Hace falta cargar al menos una observación antes de cerrar la conversación."]}}}
```

**Recomendado (no obligatorio):** deshabilitar el botón "Cerrar" (o
mostrar un aviso) mientras `observaciones.length === 0` y no se haya
aplicado ninguna de esas 3 etiquetas, en vez de que el operador se entere
recién al tocarlo.

## 3. Pendiente/asignada/tomada ya no son sólo un dato calculado

Antes: `estado_operativo` (`"pendiente"`/`"asignada"`/`"tomada"`/`"cerrada"`)
era un valor calculado al vuelo — nunca aparecían como filas reales en
`GET .../etiquetas/`.

Ahora: Core aplica esas 3 **de verdad** como `ConversacionEtiqueta` en los
mismos 3 momentos (alta de la conversación, derivar, tomar) — quedan en
`GET .../etiquetas/` con quién/cuándo, igual que cualquier otra etiqueta
(para que se vea en el historial de auditoría del Admin Panel).

**Esto sí puede romper algo visualmente:** si tu pantalla de "Etiquetas"
de una conversación lista TODO lo que devuelve `GET .../etiquetas/` con un
botón de "quitar" (como hace hoy `services/operators-desk/web`), ahora
van a aparecer ahí "Pendiente"/"Asignada"/"Tomada" con su propia ×, que
antes nunca se veían. Nada se rompe funcionalmente si alguien las quita
(no revierte `operador`/`team`), pero es confuso — **recomendado**
filtrarlas de esa lista en la UI (quedarse sólo con las que `etiqueta.codigo`
no sea `pendiente`/`asignada`/`tomada`), mostrando el estado actual sólo a
través del badge de `estado_operativo` que ya existe, como siempre.

## Nada de esto necesita un endpoint nuevo

Los 3 puntos son comportamiento nuevo sobre los MISMOS endpoints que ya
usan los dos clientes (`tomar`, `cerrar`, `etiquetas`) — no hay ningún
contrato nuevo que implementar, sólo manejar estos dos códigos de error
(ya se manejan solos) y, si quieren, las 2 mejoras de UX de arriba.
