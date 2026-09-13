import type { Me } from "../types";

/**
 * Único punto del front que decide "¿puede hacer X?" — siempre mirando la
 * lista `permissions` que manda el back en `/api/core/users/me/` (permisos
 * Django reales, unión de todos los grupos del usuario), nunca un nombre de
 * rol o de grupo hardcodeado acá. Si el back no lo permite, esto tampoco.
 */
export function hasPerm(me: Me | null, perm: string): boolean {
  return !!me?.permissions.includes(perm);
}

export function hasAnyPerm(me: Me | null, perms: string[]): boolean {
  return perms.some((perm) => hasPerm(me, perm));
}
