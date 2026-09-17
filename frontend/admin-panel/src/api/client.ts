const API_URL = import.meta.env.VITE_CORE_API_URL || "http://localhost:8001";

const CONVERSATION_ENGINE_URL = import.meta.env.VITE_CONVERSATION_ENGINE_URL || "http://localhost:8003";

// NOTA de seguridad: guardar el refresh token en localStorage es vulnerable a
// robo por XSS. Es una simplificación deliberada para esta primera versión
// (ver skill chat-security-review); si se necesita algo más robusto, mover a
// una cookie httpOnly emitida por Core requiere CSRF + cambios en el login.
const ACCESS_KEY = "admin_panel_access_token";

const REFRESH_KEY = "admin_panel_refresh_token";

let accessToken: string | null = localStorage.getItem(ACCESS_KEY);

let refreshToken: string | null = localStorage.getItem(REFRESH_KEY);

export function setTokens(tokens: { access: string; refresh: string } | null): void {
  if (tokens) {
    accessToken = tokens.access;
    refreshToken = tokens.refresh;
    localStorage.setItem(ACCESS_KEY, tokens.access);
    localStorage.setItem(REFRESH_KEY, tokens.refresh);
  } else {
    accessToken = null;
    refreshToken = null;
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
  }
}

export function hasSession(): boolean {
  return !!refreshToken;
}

/** Sólo para mostrarle al superusuario su propio token vigente (ej. para
 * pegarlo en el botón "Authorize" de Swagger) — nunca se manda a otro lado. */
export function getAccessToken(): string | null {
  return accessToken;
}

// `data` es el body de una respuesta HTTP de forma variable (dict de
// errores de validación, string, null, según el endpoint); no hay un tipo
// de dominio único para el cliente HTTP genérico. Cada caller lo valida en
// el punto de uso — ver `extraerMensajeDeError` para el caso de errores de DRF.
export class ApiError extends Error {
  status: number;
  data: unknown;
  // oxlint-disable-next-line anti-slop/no-unknown-parameters
  constructor(status: number, data: unknown) {
    super(`Error de API (${status})`);
    this.status = status;
    this.data = data;
  }
}

/** Errores de validación de DRF llegan como `{campo: string[]]}` — único
 * lugar del código que asume esa forma, para no repetir el chequeo de tipo
 * en cada pantalla que hace un POST/PATCH (antes estaba duplicado 11 veces).
 * `err` es lo que cae en un `catch`, TypeScript nunca puede tiparlo más
 * específico que `unknown`. */
// oxlint-disable-next-line anti-slop/no-unknown-parameters
export function extraerMensajeDeError(err: unknown): string | null {
  if (!(err instanceof ApiError) || !err.data) return null;

  // No hay librería de validación de esquemas en este proyecto; este es el
  // único punto que necesita angostar `unknown` a un objeto antes de asumir
  // la forma de DRF (ver SAFETY abajo).
  // oxlint-disable-next-line anti-slop/no-runtime-typeof
  if (typeof err.data !== "object") return null;

  // SAFETY: ya confirmamos arriba que `err.data` es un objeto no nulo; DRF
  // devuelve errores de validación como `{campo: string[]}`.
  return Object.values(err.data as Record<string, string[]>).flat().join(" ");
}

async function refreshAccessToken(): Promise<boolean> {
  if (!refreshToken) return false;

  const res = await fetch(`${API_URL}/api/auth/refresh/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh: refreshToken }),
  });

  if (!res.ok) return false;
  const data = await res.json();
  accessToken = data.access;
  localStorage.setItem(ACCESS_KEY, data.access);

  return true;
}

export async function apiFetch<T = unknown>(
  path: string,
  options: RequestInit = {},
  retry = true,
): Promise<T> {
  const headers = new Headers(options.headers);

  if (!(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);

  const res = await fetch(`${API_URL}${path}`, { ...options, headers });

  if (res.status === 401 && retry && refreshToken) {
    const ok = await refreshAccessToken();

    if (ok) return apiFetch<T>(path, options, false);
    setTokens(null);
    window.location.assign("/login");
    throw new ApiError(401, null);
  }

  if (res.status === 204) {
    // SAFETY: `T` lo elige quien llama según lo que espera recibir de este
    // endpoint — un wrapper de fetch genérico no puede validarlo en runtime
    // sin un esquema por endpoint, que este cliente no tiene.
    return null as T;
  }

  const text = await res.text();
  const data = text ? JSON.parse(text) : null;

  if (!res.ok) throw new ApiError(res.status, data);

  // SAFETY: mismo trade-off que arriba — `T` es la forma que el caller
  // espera, no algo que este wrapper genérico pueda comprobar.
  return data as T;
}

// `FormData` (subida de archivos, ej. el avatar) viaja tal cual — el browser
// arma el `Content-Type: multipart/form-data; boundary=...` solo, y
// `apiFetch` ya evita pisarlo con "application/json" (ver más arriba).
// Cliente HTTP genérico: el body varía por endpoint (FormData o cualquier
// JSON serializable), cada caller sabe qué forma manda.
// oxlint-disable-next-line anti-slop/no-unknown-parameters
function toBody(body: unknown): BodyInit | undefined {
  if (body === undefined) return undefined;

  if (body instanceof FormData) return body;

  return JSON.stringify(body);
}

export const api = {
  get: <T>(path: string) => apiFetch<T>(path),
  // `body` es JSON serializable arbitrario según el endpoint que llama
  // (ídem `toBody`).
  // oxlint-disable-next-line anti-slop/no-unknown-parameters
  post: <T>(path: string, body?: unknown) => apiFetch<T>(path, { method: "POST", body: toBody(body) }),
  // oxlint-disable-next-line anti-slop/no-unknown-parameters
  patch: <T>(path: string, body: unknown) => apiFetch<T>(path, { method: "PATCH", body: toBody(body) }),
  delete: (path: string) => apiFetch<null>(path, { method: "DELETE" }),
};

/** Para descargar un archivo binario (ej. el manual en PDF) que necesita el
 * header `Authorization` — un `<a href>` común no lo manda, así que se baja
 * como blob y se dispara la descarga a mano con un link temporal. */
export async function downloadFile(path: string, filename: string): Promise<void> {
  const headers = new Headers();

  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  const res = await fetch(`${API_URL}${path}`, { headers });

  if (!res.ok) throw new ApiError(res.status, null);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

/** URL absoluta de Core (ej. para abrir Swagger/Redoc en una pestaña nueva
 * con un link común — esas vistas no necesitan el header `Authorization`
 * para el HTML/JS del visor, sólo para el esquema real que consultan
 * adentro; ver `platform_admin.views.PlatformSwaggerView`). */
export function coreUrl(path: string): string {
  return `${API_URL}${path}`;
}

/** URL absoluta de Conversation Engine — Swagger (`/docs`) y Redoc
 * (`/redoc`) los sirve FastAPI solo, sin nada que armar del lado de Core.
 * No documentan el WebSocket (`WS /ws/operador/{token}`, OpenAPI no tiene
 * forma de expresarlo) — sólo `/internal/eventos/` y
 * `/organizations/{id}/conexiones-activas`. */
export function conversationEngineUrl(path: string): string {
  return `${CONVERSATION_ENGINE_URL}${path}`;
}
