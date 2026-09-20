// `toLocaleString("es-AR")` sin `hour12: false` explícito renderiza la
// medianoche como "12:xx" (formato 12 horas) SIN indicador a. m./p. m. en
// varias versiones de Chrome/ICU — un evento real de las 00:19 se lee como
// si fueran las 12:19, un error de lectura de 12 horas. Confirmado en vivo
// 2026-09-20 (bug real reportado en el historial de conversaciones del
// Admin Panel). Forzar 24 horas en un solo lugar evita repetir este mismo
// bug en cada pantalla que formatea una fecha.

export function formatearFecha(iso: string | null | undefined): string {
  if (!iso) return "—";

  try {
    return new Date(iso).toLocaleString("es-AR", { hour12: false });
  } catch {
    return iso;
  }
}

export function formatearFechaCorta(iso: string | null | undefined): string {
  if (!iso) return "—";

  try {
    return new Date(iso).toLocaleString("es-AR", { dateStyle: "short", timeStyle: "short", hour12: false });
  } catch {
    return iso;
  }
}
