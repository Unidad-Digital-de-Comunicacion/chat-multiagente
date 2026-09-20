# Buenas prácticas de seguridad y testing para APIs REST

> Basado en "Taller: Control de Calidad de Software — Unidad 2: Servicios APIs" (Clase 6). Este documento es de uso transversal: aplicarlo en **cualquier** API REST que un agente construya o modifique, incluyendo el microservicio de identidad y los endpoints de Beneficios/Admin ya definidos en los documentos de arquitectura previos.

No hay un skill instalado específico para esto en el catálogo del entorno (se buscó por "API REST", "seguridad", "OWASP", "testing" sin resultados). Hasta que exista uno, este checklist reemplaza a ese skill: **es obligatorio pasarlo antes de considerar terminada cualquier tarea que cree o modifique una API**.

## 0. Cómo usar este documento

Antes de dar por cerrada una tarea de API, repasar cada sección como checklist. Si algún punto no aplica a la tarea puntual, dejar una línea aclarando por qué no aplica (no simplemente omitirlo en silencio) para que quede trazado en el PR/commit.

## 1. Autenticación y autorización segura

- [ ] Usar tokens (OAuth2/JWT), no sesiones basadas en credenciales reenviadas en cada request.
- [ ] El JWT (o token equivalente) debe llevar: identificador de usuario, tiempo de expiración, roles/permisos, y estar firmado (firma digital) para garantizar integridad.
- [ ] Evaluar MFA en operaciones críticas (alta de usuarios admin, cambios de permisos, operaciones destructivas).
- [ ] Definir *scopes*/roles que limiten qué recursos o acciones puede tocar cada token — no repartir tokens "todo-poderosos" salvo para superusuarios explícitos.
- [ ] Diferenciar claramente, si aplica, entre:
  - Token de autenticación (identifica que el usuario logueó).
  - Token de acceso (permiso temporal a un recurso puntual).
  - Token CSRF (si hay formularios server-rendered).
- [ ] Nunca guardar tokens de sesión en `localStorage` si se puede evitar — preferir cookies `httponly` + `secure` + `samesite`.

## 2. Comunicación segura

- [ ] Todo el tráfico va por **HTTPS** (TLS), nunca HTTP plano en producción ni en el entorno de prueba una vez que hay datos reales.
- [ ] Usar versiones recientes de TLS (1.2+), certificados renovados automáticamente (Certbot/Let's Encrypt u otro).
- [ ] Verificar que el certificado cubra todos los hostnames que sirve el servicio (dominio canónico + alias, si los hay).

## 3. Validación de datos

- [ ] Toda validación de entrada se hace **del lado del servidor**, nunca confiar solo en la validación del cliente/frontend.
- [ ] Sanear/escapar entradas para evitar inyección (SQL injection, XSS, command injection).
- [ ] Usar serializers/schemas (DRF serializers, Pydantic, JSON Schema, etc.) en vez de parsear el body a mano.
- [ ] Rechazar payloads con campos inesperados o de tamaño desproporcionado (evitar payloads gigantes como vector de DoS).

## 4. Manejo adecuado de errores

- [ ] Devolver códigos HTTP correctos y consistentes:

  | Rango | Significado | Ejemplos |
  |---|---|---|
  | 2xx | Éxito | 200 OK, 201 Created, 204 No Content |
  | 3xx | Redirección | 301 Moved Permanently, 304 Not Modified |
  | 4xx | Error del cliente | 400 Bad Request, 401 Unauthorized, 403 Forbidden, 404 Not Found, 422 Unprocessable Entity |
  | 5xx | Error del servidor | 500 Internal Server Error, 502 Bad Gateway, 503 Service Unavailable |

- [ ] Mensajes de error **genéricos hacia afuera** (nunca exponer stack traces, queries SQL, paths internos, ni detalles de la excepción real) — el detalle completo va al log del servidor, no a la respuesta HTTP.
- [ ] Formato de error consistente en toda la API (ver los MD de arquitectura previos: `{"error": {"code": "...", "detail": "..."}}`).

## 5. Rate limiting y control de tráfico

- [ ] Limitar frecuencia de requests por IP y/o por usuario, especialmente en endpoints de login/auth (mitiga fuerza bruta y DDoS).
- [ ] Aplicar *throttling* diferenciado: endpoints de lectura pueden tolerar más volumen que endpoints de escritura o de auth.
- [ ] Documentar los límites aplicados (para que un cliente legítimo sepa qué esperar, no solo para ataques).

## 6. CORS (Cross-Origin Resource Sharing)

- [ ] Configurar `CORS_ALLOWED_ORIGINS` (o equivalente) con la lista explícita de dominios permitidos — nunca `*` en un servicio que maneja auth o datos sensibles.
- [ ] Revisar esta lista cada vez que se agregue un dominio o alias nuevo (ej. el alias `.org` de Beneficios).

## 7. Logs y auditoría

- [ ] Registrar accesos y modificaciones relevantes (quién, qué, cuándo) — en particular altas/bajas de usuarios, cambios de permisos, y logins fallidos repetidos.
- [ ] Nunca loguear passwords, tokens completos, ni datos sensibles en texto plano.
- [ ] Si hay herramienta de monitoreo disponible, alertar sobre patrones anómalos (muchos 401 seguidos, picos de tráfico, etc.).

## 8. Seguridad en claves de API

- [ ] Las API keys de servicio (`X-Service-Key` u otras) se guardan **hasheadas** en la base y nunca en el repo.
- [ ] Cada clave tiene permisos acotados al servicio que la usa (principio de mínimo privilegio) — no una clave maestra compartida entre todo.
- [ ] Soportar rotación sin downtime (aceptar clave vieja + nueva durante una ventana de transición).

## 9. Pruebas de seguridad

- [ ] Incluir al menos pruebas automatizadas básicas de seguridad en el pipeline de CI/CD: intentos de acceso sin token, con token expirado, con token de otro usuario/rol, y con payloads maliciosos simples (inyección, payload gigante).
- [ ] Si el proyecto lo justifica, programar pentesting periódico (manual o con herramienta automatizada) — no es parte del día a día del agente, pero sí dejarlo anotado como pendiente si no existe.

## 10. Documentación clara

- [ ] Documentar cada endpoint: método, path, auth requerida, body esperado, respuestas posibles (incluyendo errores).
- [ ] Documentar explícitamente las prácticas de seguridad que el consumidor de la API debe respetar (manejo de tokens, expiración, CORS).
- [ ] Preferir un formato estándar (OpenAPI/Swagger) cuando el proyecto ya tenga o vaya a tener múltiples consumidores externos.

---

## 11. Testing funcional — qué probar y con qué

Además de la seguridad, toda API nueva o modificada necesita esta cobertura mínima:

| Tipo de prueba | Qué verifica |
|---|---|
| **Funcionales** | Cada endpoint devuelve el resultado esperado para las entradas dadas (status code, estructura y valores de la respuesta). |
| **De contrato** | La API cumple su especificación (OpenAPI/Swagger) — importante si hay más de un consumidor. |
| **De integración** | La API funciona junto con la base de datos y los servicios externos de los que depende (ej. el monolito contra el microservicio de identidad). |
| **De carga/performance** | Comportamiento bajo volumen alto de solicitudes concurrentes — tiempos de respuesta, throughput. |
| **Smoke tests** | Conjunto mínimo que valida lo más crítico apenas se despliega, antes de correr la suite completa. |

**Shift-left testing**: probar lo antes posible en el ciclo de desarrollo (no esperar a integrar con el cliente final para descubrir errores). Esto es especialmente relevante para el microservicio de identidad: sus endpoints deben tener tests propios *antes* de que los monolitos empiecen a integrarse contra él.

### Herramientas sugeridas (elegir según el stack del proyecto)
- **Manuales/exploratorias**: Postman, Insomnia.
- **Automatizadas**: pytest + `requests`/`httpx` (Python/Django, que es el stack de estos proyectos), o REST-assured/Karate si en algún momento se suma un stack Java.
- **Contrato**: Swagger UI / drf-spectacular (para proyectos Django+DRF) para generar y validar contra OpenAPI.
- **Línea de comandos**: cURL o HTTPie para checks rápidos manuales durante el desarrollo.

## 12. Checklist rápido antes de cerrar un PR de API

```
[ ] Todos los endpoints nuevos/modificados están detrás de HTTPS
[ ] Auth y permisos verificados con tests (con y sin token, con rol incorrecto)
[ ] Inputs validados server-side con serializer/schema
[ ] Errores devuelven código HTTP correcto y mensaje genérico (nada de detalle interno)
[ ] Rate limiting aplicado si el endpoint es sensible (login, auth, escritura masiva)
[ ] CORS actualizado si se agregó un dominio/alias nuevo
[ ] No hay secretos, claves ni tokens hardcodeados en el código o el repo
[ ] Logs no exponen passwords/tokens completos
[ ] Tests funcionales + al menos un test de integración corriendo en CI
[ ] Documentación del endpoint actualizada (incluyendo casos de error)
```
