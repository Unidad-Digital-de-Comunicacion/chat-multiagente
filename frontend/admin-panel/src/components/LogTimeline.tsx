import { Fragment, useEffect, useState } from "react";

import { api, ApiError } from "../api/client";
import type { LineaLog, RespuestaLogs } from "../types";
import { formatearFecha } from "../utils/fecha";

const COLORES_SERVICIO = new Map([
  ["core", "#3454d1"],
  ["channel-gateway", "#0f8a5f"],
  ["conversation-engine", "#8e44ad"],
  ["analytics", "#b8860b"],
  ["webchat", "#c0392b"],
]);

const NIVELES = ["", "INFO", "WARNING", "ERROR"];

function colorDe(servicio: string): string {
  return COLORES_SERVICIO.get(servicio) ?? "#6b7280";
}

function claseNivel(nivel: string): string {
  if (nivel === "ERROR" || nivel === "CRITICAL") return "badge badge-danger";

  if (nivel === "WARNING") return "badge badge-warning";

  return "badge";
}

/** Hora con milisegundos: en una línea de tiempo entre servicios el orden
 * fino importa (varias líneas caen en el mismo segundo). */
function horaConMs(iso: string): string {
  const fecha = new Date(iso);

  return `${formatearFecha(iso)}.${String(fecha.getMilliseconds()).padStart(3, "0")}`;
}

interface Props {
  desde: string;
  hasta: string;
  requestId: string;
  onRequestId: (requestId: string) => void;
  nivelInicial?: string;
}

/** Líneas de log de TODOS los servicios mezcladas en orden cronológico
 * (`GET /api/core/plataforma/logs/`). La comparten "Incidentes" (ventana
 * alrededor del incidente) y "Logs" (búsqueda libre). Click en un request_id
 * = seguir ese mismo pedido por todos los servicios. */
export default function LogTimeline({ desde, hasta, requestId, onRequestId, nivelInicial = "" }: Props) {
  const [nivel, setNivel] = useState(nivelInicial);
  const [texto, setTexto] = useState("");
  const [textoAplicado, setTextoAplicado] = useState("");
  const [ocultos, setOcultos] = useState<string[]>([]);
  const [datos, setDatos] = useState<RespuestaLogs | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);
  const [abierta, setAbierta] = useState<number | null>(null);

  useEffect(() => {
    const params = new URLSearchParams({ desde, hasta, limite: "1000" });

    if (nivel) params.set("nivel", nivel);

    if (requestId) params.set("request_id", requestId);

    if (textoAplicado) params.set("q", textoAplicado);
    setCargando(true);
    setError(null);
    api
      .get<RespuestaLogs>(`/api/core/plataforma/logs/?${params.toString()}`)
      .then((data) => {
        setDatos(data);
        setAbierta(null);
      })
      .catch((err) => {
        setError(err instanceof ApiError && err.status === 400 ? "Filtros inválidos." : "No se pudieron cargar los logs.");
      })
      .finally(() => setCargando(false));
  }, [desde, hasta, nivel, requestId, textoAplicado]);

  const lineas: LineaLog[] = (datos?.lineas ?? []).filter((l) => !ocultos.includes(l.service));

  const alternarServicio = (servicio: string) => {
    setOcultos((prev) => (prev.includes(servicio) ? prev.filter((s) => s !== servicio) : [...prev, servicio]));
  };

  return (
    <div>
      <div className="toolbar">
        <label>
          Nivel mínimo{" "}
          <select value={nivel} onChange={(e) => setNivel(e.target.value)}>
            {NIVELES.map((n) => (
              <option key={n} value={n}>
                {n || "Todos"}
              </option>
            ))}
          </select>
        </label>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            setTextoAplicado(texto.trim());
          }}
        >
          <input
            type="search"
            placeholder="Buscar texto…"
            value={texto}
            onChange={(e) => setTexto(e.target.value)}
            aria-label="Buscar texto en los logs"
          />{" "}
          <button type="submit" className="btn btn-outline btn-sm">
            Buscar
          </button>
        </form>
        {requestId && (
          <span className="badge">
            request_id: <code>{requestId}</code>{" "}
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => onRequestId("")}>
              quitar
            </button>
          </span>
        )}
      </div>

      {datos && datos.servicios_disponibles.length > 0 && (
        <div className="toolbar">
          <span className="text-muted small">Servicios:</span>
          {datos.servicios_disponibles.map((s) => (
            <label key={s} className="small" style={{ color: colorDe(s) }}>
              <input type="checkbox" checked={!ocultos.includes(s)} onChange={() => alternarServicio(s)} /> {s}
            </label>
          ))}
        </div>
      )}

      {error && <div className="form-error">{error}</div>}
      {cargando && <div className="page-loading">Cargando logs…</div>}
      {datos?.truncado && (
        <p className="text-muted small">
          Hay más líneas de las que se muestran: se ven las últimas 1000. Acotá el rango, el nivel o el texto.
        </p>
      )}

      <table className="table log-table">
        <thead>
          <tr>
            <th>Hora</th>
            <th>Servicio</th>
            <th>Nivel</th>
            <th>Mensaje</th>
            <th>request_id</th>
          </tr>
        </thead>
        <tbody>
          {lineas.map((l, i) => (
            <Fragment key={i}>
              <tr className={l.level === "ERROR" || l.level === "CRITICAL" ? "log-row-error" : undefined}>
                <td className="log-ts">{horaConMs(l.ts)}</td>
                <td>
                  <span className="log-service" style={{ borderColor: colorDe(l.service), color: colorDe(l.service) }}>
                    {l.service}
                  </span>
                </td>
                <td>
                  <span className={claseNivel(l.level)}>{l.level}</span>
                </td>
                <td className="log-msg">
                  <span className="text-muted small">{l.logger}</span> {l.msg}
                  {l.exc && (
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      onClick={() => setAbierta(abierta === i ? null : i)}
                    >
                      {abierta === i ? "ocultar traceback" : "ver traceback"}
                    </button>
                  )}
                </td>
                <td>
                  {l.request_id && (
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm log-rid"
                      title="Seguir este pedido en todos los servicios"
                      onClick={() => onRequestId(l.request_id)}
                    >
                      {l.request_id}
                    </button>
                  )}
                </td>
              </tr>
              {abierta === i && (
                <tr>
                  <td colSpan={5}>
                    <pre className="log-pre">{l.exc}</pre>
                  </td>
                </tr>
              )}
            </Fragment>
          ))}
          {!cargando && lineas.length === 0 && (
            <tr>
              <td colSpan={5} className="text-muted text-center">
                Sin líneas de log para estos filtros.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
