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

/**
 * La sección "Plataforma" (organizaciones, usuarios de todas las
 * organizaciones, tokens internos, estadísticas, manuales) es de alcance
 * global — no alcanza con los permisos Django estándar para mostrarla/
 * ocultarla porque `administradores` tiene esos MISMOS permisos para su
 * propia organización (`organizations.view_organization`, `users.view_user`,
 * etc. — ver `common.permissions.IsPlatformSuperuser` en el back, que aplica
 * exactamente este mismo criterio del lado del servidor). Por eso acá se
 * mira directamente `is_superuser`/`organization_id`, no `permissions`.
 */
export function isPlatformSuperuser(me: Me | null): boolean {
  return !!me?.is_superuser && !me?.organization_id;
}
