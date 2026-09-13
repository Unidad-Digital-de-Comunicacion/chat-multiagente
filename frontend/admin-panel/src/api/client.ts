const API_URL = import.meta.env.VITE_CORE_API_URL || "http://localhost:8001";

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

export class ApiError extends Error {
  status: number;
  data: unknown;
  constructor(status: number, data: unknown) {
    super(`Error de API (${status})`);
    this.status = status;
    this.data = data;
  }
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

  if (res.status === 204) return null as T;

  const text = await res.text();
  const data = text ? JSON.parse(text) : null;

  if (!res.ok) throw new ApiError(res.status, data);
  return data as T;
}

// `FormData` (subida de archivos, ej. el avatar) viaja tal cual — el browser
// arma el `Content-Type: multipart/form-data; boundary=...` solo, y
// `apiFetch` ya evita pisarlo con "application/json" (ver más arriba).
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
