import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { api, ApiError } from "../api/client";
import LogTimeline from "../components/LogTimeline";
import type { ChequeoSalud, Incidente, IncidenteEstado, Paginated } from "../types";
import { formatearFecha } from "../utils/fecha";

const MARGENES_MINUTOS = [2, 5, 15, 60];

const FILTROS_ESTADO: { valor: IncidenteEstado | ""; label: string }[] = [
  { valor: "abierto", label: "Abiertos" },
  { valor: "resuelto", label: "Resueltos" },
  { valor: "", label: "Todos" },
];

function badgeTipo(i: Incidente): string {
  if (i.tipo === "caida") return "badge badge-danger";

  if (i.tipo === "seguridad") return "badge badge-warning";

  return "badge";
}

function desplazar(iso: string, minutos: number): string {
  return new Date(new Date(iso).getTime() + minutos * 60_000).toISOString();
}

export default function PlatformIncidentsPage() {
  const [params, setParams] = useSearchParams();
  const idSeleccionado = Number(params.get("id")) || null;

  const [estado, setEstado] = useState<IncidenteEstado | "">("abierto");
  const [pagina, setPagina] = useState(1);
  const [lista, setLista] = useState<Paginated<Incidente> | null>(null);
  const [chequeos, setChequeos] = useState<ChequeoSalud[]>([]);
  const [seleccionado, setSeleccionado] = useState<Incidente | null>(null);
  const [margen, setMargen] = useState(5);
  const [requestId, setRequestId] = useState("");
  const [error, setError] = useState<string | null>(null);

  const cargarLista = useCallback(() => {
    const q = new URLSearchParams({ page: String(pagina) });

    if (estado) q.set("estado", estado);
    Promise.all([
      api.get<Paginated<Incidente>>(`/api/core/plataforma/incidentes/?${q.toString()}`),
      api.get<ChequeoSalud[]>("/api/core/plataforma/chequeos-salud/"),
    ])
      .then(([data, salud]) => {
        setLista(data);
        setChequeos(salud);
      })
      .catch((err) => {
        setError(
          err instanceof ApiError && err.status === 403
            ? "Esta sección es sólo para el superusuario de plataforma."
            : "No se pudieron cargar los incidentes.",
        );
      });
  }, [estado, pagina]);

  useEffect(() => {
    cargarLista();
    const intervalo = window.setInterval(cargarLista, 30_000);

    return () => window.clearInterval(intervalo);
  }, [cargarLista]);

  useEffect(() => {
    if (!idSeleccionado) {
      setSeleccionado(null);

      return;
    }

    api
      .get<Incidente>(`/api/core/plataforma/incidentes/${idSeleccionado}/`)
      .then((data) => {
        setSeleccionado(data);
        setRequestId("");
      })
      .catch(() => setError("No se encontró ese incidente."));
  }, [idSeleccionado]);

  const cambiarEstado = async (nuevo: IncidenteEstado) => {
    if (!seleccionado) return;
    const data = await api.patch<Incidente>(`/api/core/plataforma/incidentes/${seleccionado.id}/`, { estado: nuevo });

    setSeleccionado(data);
    cargarLista();
  };

  if (error) return <div className="empty-state">{error}</div>;

  if (!lista) return <div className="page-loading">Cargando…</div>;

  const caidos = chequeos.filter((c) => c.ok === false);

  return (
    <div>
      <div className="page-header">
        <h2>Incidentes</h2>
      </div>
      <p className="text-muted">
        Eventos anómalos detectados en los logs de todos los servicios (errores, caídas, intentos de login sospechosos).
        Los nuevos se avisan por mail; esta lista se actualiza sola cada 30 segundos.
      </p>

      <div className="toolbar">
        <span className="text-muted small">Salud:</span>
        {chequeos.length === 0 && <span className="text-muted small">todavía sin chequeos</span>}
        {chequeos.map((c) => (
          <span
            key={c.nombre}
            className={"badge" + (c.ok === false ? " badge-danger" : "")}
            title={`${c.url} — ${c.ultimo_detalle} (${formatearFecha(c.ultimo_chequeo_at)})`}
          >
            {c.ok === false ? "✕" : "✓"} {c.nombre}
          </span>
        ))}
        {caidos.length > 0 && <strong className="small">{caidos.length} sin responder</strong>}
      </div>

      <div className="tabs">
        {FILTROS_ESTADO.map((f) => (
          <button
            key={f.label}
            type="button"
            className={"tab" + (estado === f.valor ? " tab-active" : "")}
            onClick={() => {
              setEstado(f.valor);
              setPagina(1);
            }}
          >
            {f.label}
          </button>
        ))}
      </div>

      <table className="table">
        <thead>
          <tr>
            <th>Tipo</th>
            <th>Incidente</th>
            <th>Servicio</th>
            <th>Ocurrencias</th>
            <th>Última vez</th>
            <th>Estado</th>
          </tr>
        </thead>
        <tbody>
          {lista.results.map((i) => (
            <tr
              key={i.id}
              className={"row-clickable" + (i.id === idSeleccionado ? " row-selected" : "")}
              onClick={() => setParams({ id: String(i.id) })}
            >
              <td>
                <span className={badgeTipo(i)}>{i.tipo_display}</span>
              </td>
              <td>{i.titulo}</td>
              <td>{i.servicio}</td>
              <td>{i.ocurrencias}</td>
              <td>{formatearFecha(i.ultima_vez)}</td>
              <td>{i.estado_display}</td>
            </tr>
          ))}
          {lista.results.length === 0 && (
            <tr>
              <td colSpan={6} className="text-muted text-center">
                Sin incidentes {estado === "abierto" ? "abiertos" : ""}.
              </td>
            </tr>
          )}
        </tbody>
      </table>
      {(lista.next || lista.previous) && (
        <div className="toolbar">
          <button type="button" className="btn btn-outline btn-sm" disabled={!lista.previous} onClick={() => setPagina(pagina - 1)}>
            Anterior
          </button>
          <span className="small">Página {pagina}</span>
          <button type="button" className="btn btn-outline btn-sm" disabled={!lista.next} onClick={() => setPagina(pagina + 1)}>
            Siguiente
          </button>
        </div>
      )}

      {seleccionado && (
        <section className="card incident-detail">
          <div className="page-header">
            <h3>
              <span className={badgeTipo(seleccionado)}>{seleccionado.tipo_display}</span> {seleccionado.titulo}
            </h3>
            <div className="btn-toolbar">
              {seleccionado.estado === "abierto" ? (
                <button type="button" className="btn btn-primary" onClick={() => cambiarEstado("resuelto")}>
                  Marcar resuelto
                </button>
              ) : (
                <button type="button" className="btn btn-outline" onClick={() => cambiarEstado("abierto")}>
                  Reabrir
                </button>
              )}
              <button type="button" className="btn btn-ghost" onClick={() => setParams({})}>
                Cerrar
              </button>
            </div>
          </div>
          <p className="small">
            <strong>{seleccionado.ocurrencias}</strong> ocurrencia(s) · primera vez {formatearFecha(seleccionado.primera_vez)} ·
            última {formatearFecha(seleccionado.ultima_vez)} · avisado por mail{" "}
            {seleccionado.notificado_at ? formatearFecha(seleccionado.notificado_at) : "todavía no"}
            {seleccionado.resuelto_at && (
              <>
                {" "}
                · resuelto {formatearFecha(seleccionado.resuelto_at)}
                {seleccionado.resuelto_por_email ? ` por ${seleccionado.resuelto_por_email}` : " (solo)"}
              </>
            )}
          </p>
          <pre className="log-pre">{seleccionado.detalle || "—"}</pre>

          {seleccionado.request_ids.length > 0 && (
            <div className="toolbar">
              <span className="text-muted small">Pedidos afectados (seguir en todos los servicios):</span>
              {seleccionado.request_ids.map((rid) => (
                <button
                  key={rid}
                  type="button"
                  className={"btn btn-sm " + (rid === requestId ? "btn-primary" : "btn-outline")}
                  onClick={() => setRequestId(rid === requestId ? "" : rid)}
                >
                  {rid}
                </button>
              ))}
            </div>
          )}

          <h4>Línea de tiempo de todos los servicios</h4>
          <div className="toolbar">
            <label className="small">
              {requestId ? "Buscar el pedido entre" : "Ventana alrededor del incidente"}: ±{" "}
              <select value={margen} onChange={(e) => setMargen(Number(e.target.value))}>
                {MARGENES_MINUTOS.map((m) => (
                  <option key={m} value={m}>
                    {m} min
                  </option>
                ))}
              </select>
            </label>
          </div>
          <LogTimeline
            desde={desplazar(seleccionado.primera_vez, -margen)}
            hasta={desplazar(seleccionado.ultima_vez, margen)}
            requestId={requestId}
            onRequestId={setRequestId}
          />
        </section>
      )}
    </div>
  );
}
