import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { api, extraerMensajeDeError } from "../api/client";
import { useOperatorSocket } from "../hooks/useOperatorSocket";
import { CANAL_TIPO_LABELS, ESTADO_OPERATIVO_LABELS, type Conversacion, type Paginated } from "../types";
import { formatearFechaRelativa } from "../utils/fecha";

// §3.2 del documento de requerimientos: dos vistas con el mismo componente
// de lista, alimentadas por ?bandeja=sin_asignar / ?bandeja=mias — nunca el
// listado sin filtro. Refresca por evento de WebSocket (mensaje_nuevo /
// conversacion_actualizada) y por polling de respaldo cada 12s.
const POLLING_MS = 12000;

export default function InboxPage({ bandeja }: { bandeja: "sin_asignar" | "mias" }) {
  const navigate = useNavigate();
  const [conversaciones, setConversaciones] = useState<Conversacion[]>([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tomando, setTomando] = useState<number | null>(null);
  // Filtro de equipo del lado del cliente — la API no tiene más filtros que
  // `bandeja` hoy (§3.2 del documento de requerimientos).
  const [filtroTeam, setFiltroTeam] = useState<string>("");
  const bandejaRef = useRef(bandeja);
  bandejaRef.current = bandeja;

  const cargar = useCallback(async (mostrarCargando: boolean) => {
    if (mostrarCargando) setCargando(true);
    try {
      const data = await api.get<Paginated<Conversacion>>(`/api/core/conversaciones/?bandeja=${bandejaRef.current}`);
      setConversaciones(data.results);
      setError(null);
    } catch (err) {
      setError(extraerMensajeDeError(err) ?? "No se pudo cargar la bandeja.");
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    cargar(true);
    const id = setInterval(() => cargar(false), POLLING_MS);

    return () => clearInterval(id);
  }, [bandeja, cargar]);

  useOperatorSocket((evento) => {
    if (evento.tipo === "mensaje_nuevo" || evento.tipo === "conversacion_actualizada") {
      cargar(false);
    }
  });

  async function tomar(conv: Conversacion) {
    setTomando(conv.id);
    try {
      await api.post(`/api/core/conversaciones/${conv.id}/tomar/`);
      navigate(`/conversaciones/${conv.id}`);
    } catch (err) {
      setError(extraerMensajeDeError(err) ?? "No se pudo tomar la conversación (puede que ya esté tomada).");
      cargar(false);
    } finally {
      setTomando(null);
    }
  }

  const equipos = Array.from(new Set(conversaciones.map((c) => c.team_nombre).filter((n): n is string => !!n)));
  const listaFiltrada = filtroTeam ? conversaciones.filter((c) => c.team_nombre === filtroTeam) : conversaciones;

  return (
    <div className="page">
      <div className="page-header">
        <h1>{bandeja === "sin_asignar" ? "Sin asignar" : "Mis conversaciones"}</h1>
        {equipos.length > 1 && (
          <select value={filtroTeam} onChange={(e) => setFiltroTeam(e.target.value)}>
            <option value="">Todos los equipos</option>
            {equipos.map((nombre) => (
              <option key={nombre} value={nombre}>
                {nombre}
              </option>
            ))}
          </select>
        )}
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      {cargando ? (
        <p className="text-muted">Cargando…</p>
      ) : listaFiltrada.length === 0 ? (
        <p className="text-muted">No hay conversaciones acá por ahora.</p>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>Estado</th>
              <th>Canal</th>
              <th>Contacto</th>
              <th>Equipo</th>
              <th>Actualizado</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {listaFiltrada.map((conv) => (
              <tr key={conv.id}>
                <td>
                  <span className={`badge badge-${conv.estado_operativo}`}>
                    {ESTADO_OPERATIVO_LABELS[conv.estado_operativo]}
                  </span>
                </td>
                <td>{CANAL_TIPO_LABELS[conv.canal] ?? conv.canal_display}</td>
                <td>{conv.contact.nombre || conv.contact.identificador_externo}</td>
                <td>{conv.team_nombre ?? "—"}</td>
                <td className="text-muted">{formatearFechaRelativa(conv.updated_at)}</td>
                <td>
                  {bandeja === "sin_asignar" ? (
                    <button
                      type="button"
                      className="btn btn-primary btn-sm"
                      disabled={tomando === conv.id}
                      onClick={() => tomar(conv)}
                    >
                      {tomando === conv.id ? "Tomando…" : "Tomar"}
                    </button>
                  ) : (
                    <button type="button" className="btn btn-secondary btn-sm" onClick={() => navigate(`/conversaciones/${conv.id}`)}>
                      Abrir
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
