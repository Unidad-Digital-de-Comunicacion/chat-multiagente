import type { Me } from "../types";

/**
 * Igual que en frontend/admin-panel/src/auth/permissions.ts: la única
 * fuente para decidir "¿puede hacer X?" es `permissions` (permisos Django
 * reales que manda `/api/core/users/me/`) — nunca un nombre de grupo
 * hardcodeado. Por ahora esta app no distingue pantallas por permiso (todo
 * lo que hay es para el rol operador), pero queda listo para cuando haga
 * falta ocultar/mostrar algo puntual sin tocar el resto.
 */
export function hasPerm(me: Me | null, perm: string): boolean {
  return !!me?.permissions.includes(perm);
}
