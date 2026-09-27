const API_URL = import.meta.env.VITE_CORE_API_URL || "http://localhost:8001";

const CONVERSATION_ENGINE_URL = import.meta.env.VITE_CONVERSATION_ENGINE_URL || "http://localhost:8003";

// Mismo criterio (y misma limitación conocida) que frontend/admin-panel/src/api/client.ts:
// guardar el refresh token en localStorage es vulnerable a robo por XSS. Es
// una simplificación deliberada de esta primera versión — si hace falta algo
// más robusto, hay que mover esto a una cookie httpOnly emitida por Core.
const ACCESS_KEY = "operators_desk_access_token";

const REFRESH_KEY = "operators_desk_refresh_token";

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

export function getAccessToken(): string | null {
  return accessToken;
}

// `data` es el body de una respuesta HTTP de forma variable según el
// endpoint (dict de errores de validación, string, null) — no hay un tipo
// de dominio único para un cliente HTTP genérico.
export class ApiError extends Error {
  status: number;
  data: unknown;
  constructor(status: number, data: unknown) {
    super(`Error de API (${status})`);
    this.status = status;
    this.data = data;
  }
}

/** Errores de la API llegan como `{"error": {"code", "detail"}}`
 * (docs/BUENAS-PRACTICAS-API-REST.md §4 / docs/operators-desk-api-contract.md
 * §5) — `detail` es un string para la mayoría, o `{campo: string[]}` cuando
 * es un error de validación de campo(s). */
export function extraerMensajeDeError(err: unknown): string | null {
  if (!(err instanceof ApiError) || !err.data) return null;
  if (typeof err.data !== "object") return null;

  const detalle = (err.data as { error?: { detail?: unknown } }).error?.detail;
  if (detalle == null) return null;
  if (typeof detalle === "string") return detalle;

  return Object.values(detalle as Record<string, string[]>).flat().join(" ");
}

/** Código de máquina del error (`error.code`), útil para lógica de cliente
 * puntual — ej. distinguir un 429 de bloqueo por fuerza bruta (que trae
 * `blocked_until`) de un throttle común. */
export function extraerCodigoDeError(err: unknown): string | null {
  if (!(err instanceof ApiError) || !err.data || typeof err.data !== "object") return null;

  return (err.data as { error?: { code?: string } }).error?.code ?? null;
}

/** `blocked_until` del bloqueo por fuerza bruta de login (3ª falla seguida
 * desde la misma IP, §1 del contrato de API) — sólo viene en ese caso. */
export function extraerBloqueoHasta(err: unknown): string | null {
  if (!(err instanceof ApiError) || !err.data || typeof err.data !== "object") return null;

  return (err.data as { error?: { blocked_until?: string } }).error?.blocked_until ?? null;
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
    return null as T;
  }

  const text = await res.text();
  const data = text ? JSON.parse(text) : null;

  if (!res.ok) throw new ApiError(res.status, data);

  return data as T;
}

function toBody(body: unknown): BodyInit | undefined {
  if (body === undefined) return undefined;
  if (body instanceof FormData) return body;

  return JSON.stringify(body);
}

export const api = {
  get: <T>(path: string) => apiFetch<T>(path),
  post: <T>(path: string, body?: unknown) => apiFetch<T>(path, { method: "POST", body: toBody(body) }),
  patch: <T>(path: string, body: unknown) => apiFetch<T>(path, { method: "PATCH", body: toBody(body) }),
  delete: (path: string) => apiFetch<null>(path, { method: "DELETE" }),
};

export function coreUrl(path: string): string {
  return `${API_URL}${path}`;
}

/** URL absoluta (`ws://`/`wss://`) del WebSocket de Conversation Engine
 * (§7.1 del contrato de API) para el `access` token dado. */
export function operatorSocketUrl(accessTokenParaSocket: string): string {
  const wsBase = CONVERSATION_ENGINE_URL.replace(/^http/, "ws");

  return `${wsBase}/ws/operador/${accessTokenParaSocket}`;
}
