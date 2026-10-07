// Copiado de frontend/admin-panel/src/utils/fecha.ts — `hour12: false`
// explícito evita que la medianoche se muestre como "12:xx" sin indicador
// a. m./p. m. en algunas versiones de Chrome/ICU.

export function formatearFecha(iso: string | null | undefined): string {
  if (!iso) return "—";

  try {
    return new Date(iso).toLocaleString("es-AR", { hour12: false });
  } catch {
    return iso;
  }
}

export function formatearFechaRelativa(iso: string | null | undefined): string {
  if (!iso) return "—";

  try {
    const diffMs = Date.now() - new Date(iso).getTime();
    const diffMin = Math.floor(diffMs / 60000);

    if (diffMin < 1) return "recién";
    if (diffMin < 60) return `hace ${diffMin} min`;
    const diffH = Math.floor(diffMin / 60);

    if (diffH < 24) return `hace ${diffH} h`;
    const diffD = Math.floor(diffH / 24);

    return `hace ${diffD} d`;
  } catch {
    return iso;
  }
}
