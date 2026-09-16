import { useEffect, useState } from "react";

import { api, ApiError } from "../api/client";
import { CANAL_TIPO_LABELS, type ExternalHealthRow, type PlatformStats } from "../types";

export default function PlatformStatsPage() {
  const [stats, setStats] = useState<PlatformStats | null>(null);
  const [health, setHealth] = useState<ExternalHealthRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      api.get<PlatformStats>("/api/core/plataforma/estadisticas/"),
      api.get<ExternalHealthRow[]>("/api/core/plataforma/salud-canales/"),
    ])
      .then(([statsData, healthData]) => {
        setStats(statsData);
        setHealth(healthData);
      })
      .catch((err) => {
        setError(
          err instanceof ApiError && err.status === 403
            ? "Esta sección es sólo para el superusuario de plataforma."
            : "No se pudieron cargar las estadísticas.",
        );
      });
  }, []);

  if (error) return <div className="empty-state">{error}</div>;

  if (!stats || !health) return <div className="page-loading">Cargando…</div>;

  return (
    <div>
      <div className="page-header">
        <h2>Estadísticas</h2>
      </div>
      <p className="text-muted">
        Uso general de este microservicio (Core) y salud de las APIs externas de mensajería de todas las
        organizaciones. Todavía no hay conversaciones que contar — eso es Conversation Engine, Fase 4.
      </p>

      <div className="stats-grid">
        <StatCard label="Organizaciones" value={stats.organizaciones_total} sub={`${stats.organizaciones_activas} activas`} />
        <StatCard label="Usuarios" value={stats.usuarios_total} sub={`${stats.usuarios_activos} activos`} />
        <StatCard label="Equipos" value={stats.equipos_total} />
        <StatCard label="Canales configurados" value={stats.canales_configurados} sub={`${stats.canales_activos} activos`} />
      </div>

      <h3>Usuarios y equipos por organización</h3>
      <table className="table">
        <thead>
          <tr>
            <th>Organización</th>
            <th>Activa</th>
            <th>Usuarios</th>
            <th>Límite de usuarios</th>
            <th>Equipos</th>
            <th>Canales activos</th>
          </tr>
        </thead>
        <tbody>
          {stats.por_organizacion.map((o) => (
            <tr key={o.organization_id}>
              <td>{o.organization_name}</td>
              <td>{o.is_active ? "Sí" : "No"}</td>
              <td>{o.usuarios}</td>
              <td>{o.user_limit === 0 ? "Sin límite" : o.user_limit}</td>
              <td>{o.equipos}</td>
              <td>{o.canales_activos}</td>
            </tr>
          ))}
          {stats.por_organizacion.length === 0 && (
            <tr>
              <td colSpan={6} className="text-muted text-center">Sin organizaciones todavía.</td>
            </tr>
          )}
        </tbody>
      </table>

      <h3>Salud de las APIs externas (todas las organizaciones)</h3>
      <table className="table">
        <thead>
          <tr>
            <th>Organización</th>
            <th>Canal</th>
            <th>Activo</th>
            <th>Api key</th>
            <th>Último chequeo</th>
          </tr>
        </thead>
        <tbody>
          {health.map((c, i) => (
            <tr key={i}>
              <td>{c.organization_name}</td>
              <td>{CANAL_TIPO_LABELS[c.tipo] ?? c.tipo_display}</td>
              <td>{c.activo ? "Sí" : "No"}</td>
              <td>{c.api_key_configurada ? "Configurada" : <span className="text-muted">Sin configurar</span>}</td>
              <td>
                {!c.ultimo_chequeo_at ? (
                  <span className="text-muted">Nunca se verificó</span>
                ) : c.ultimo_chequeo_ok === null ? (
                  <span className="text-muted" title={c.ultimo_chequeo_detalle}>No aplica</span>
                ) : (
                  <>
                    <span className={"badge" + (c.ultimo_chequeo_ok ? "" : " badge-warning")}>
                      {c.ultimo_chequeo_ok ? "Conectado" : "Sin conexión"}
                    </span>
                    <div className="text-muted small">{new Date(c.ultimo_chequeo_at).toLocaleString("es-AR")}</div>
                  </>
                )}
              </td>
            </tr>
          ))}
          {health.length === 0 && (
            <tr>
              <td colSpan={5} className="text-muted text-center">Sin canales todavía.</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function StatCard({ label, value, sub }: { label: string; value: number; sub?: string }) {
  return (
    <div className="card stats-card">
      <div className="stats-card-value">{value}</div>
      <div className="stats-card-label">{label}</div>
      {sub && <div className="text-muted small">{sub}</div>}
    </div>
  );
}
