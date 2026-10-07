import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { api, extraerMensajeDeError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import MessageEditor from "../components/MessageEditor";
import { renderMarkup } from "../components/MessageFormat";
import { useOperatorSocket } from "../hooks/useOperatorSocket";
import {
  CANAL_TIPO_LABELS,
  ESTADO_OPERATIVO_LABELS,
  type Conversacion,
  type Etiqueta,
  type EtiquetaAplicada,
  type Mensaje,
  type NotaInterna,
  type Observacion,
  type Paginated,
  type Team,
} from "../types";
import { formatearFecha } from "../utils/fecha";

type Tab = "mensajes" | "notas" | "observaciones" | "etiquetas";

// Los 3 códigos de etiqueta de sistema que exigen `observacion` obligatoria
// al aplicarse — §4.8 del contrato de API.
const ETIQUETAS_QUE_PIDEN_OBSERVACION = ["resuelto", "rechazado", "en_pausa"];

const POLLING_MENSAJES_MS = 4000;
const POLLING_CONVERSACION_MS = 10000;
// Renovar el lock de 2 min mientras la pantalla siga abierta y la
// conversación siga tomada por mí — §4.3/§3.4 del documento de
// requerimientos ("considerar un ping periódico").
const RENOVAR_LOCK_MS = 90000;

export default function ConversationPage() {
  const { id } = useParams<{ id: string }>();
  const conversacionId = Number(id);
  const navigate = useNavigate();
  const { me } = useAuth();

  const [conversacion, setConversacion] = useState<Conversacion | null>(null);
  const [mensajes, setMensajes] = useState<Mensaje[]>([]);
  const [notas, setNotas] = useState<NotaInterna[]>([]);
  const [observaciones, setObservaciones] = useState<Observacion[]>([]);
  const [etiquetasAplicadas, setEtiquetasAplicadas] = useState<EtiquetaAplicada[]>([]);
  const [catalogoEtiquetas, setCatalogoEtiquetas] = useState<Etiqueta[]>([]);
  const [teams, setTeams] = useState<Team[]>([]);
  const [tab, setTab] = useState<Tab>("mensajes");
  const [error, setError] = useState<string | null>(null);
  const [cargando, setCargando] = useState(true);

  const [textoRespuesta, setTextoRespuesta] = useState("");
  const [enviandoRespuesta, setEnviandoRespuesta] = useState(false);
  const [avisoEntrega, setAvisoEntrega] = useState<string | null>(null);

  const [textoNota, setTextoNota] = useState("");
  const [enviandoNota, setEnviandoNota] = useState(false);

  const [textoObservacion, setTextoObservacion] = useState("");
  const [enviandoObservacion, setEnviandoObservacion] = useState(false);

  const [mostrarDerivar, setMostrarDerivar] = useState(false);
  const [derivarTeam, setDerivarTeam] = useState<string>("");
  const [derivarObservacion, setDerivarObservacion] = useState("");
  const [derivando, setDerivando] = useState(false);

  const [cerrando, setCerrando] = useState(false);
  const [aplicandoEtiqueta, setAplicandoEtiqueta] = useState<number | null>(null);
  const [pendienteObservacionEtiqueta, setPendienteObservacionEtiqueta] = useState<Etiqueta | null>(null);
  const [textoObservacionEtiqueta, setTextoObservacionEtiqueta] = useState("");

  const esMia = !!conversacion && !!me && conversacion.operador === me.id;
  const abierta = conversacion?.estado === "ABIERTA";

  const hiloMensajesRef = useRef<HTMLDivElement>(null);

  // Mostrar siempre lo último de la conversación por default — sin esto,
  // cada mensaje nuevo (propio o del contacto) entra abajo del todo y hay
  // que scrollear a mano para verlo cada vez.
  useEffect(() => {
    const el = hiloMensajesRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [mensajes, tab]);

  const cargarConversacion = useCallback(async () => {
    try {
      const data = await api.get<Conversacion>(`/api/core/conversaciones/${conversacionId}/`);
      setConversacion(data);
    } catch (err) {
      setError(extraerMensajeDeError(err) ?? "No se pudo cargar la conversación.");
    }
  }, [conversacionId]);

  const cargarMensajes = useCallback(async () => {
    try {
      const data = await api.get<Mensaje[]>(`/api/core/conversaciones/${conversacionId}/mensajes/`);
      setMensajes(data);
    } catch {
      // El error de la conversación en sí ya se muestra vía cargarConversacion; acá evitamos duplicar el aviso.
    }
  }, [conversacionId]);

  const cargarNotas = useCallback(async () => {
    const data = await api.get<NotaInterna[]>(`/api/core/conversaciones/${conversacionId}/notas-internas/`);
    setNotas(data);
  }, [conversacionId]);

  const cargarObservaciones = useCallback(async () => {
    const data = await api.get<Observacion[]>(`/api/core/conversaciones/${conversacionId}/observaciones/`);
    setObservaciones(data);
  }, [conversacionId]);

  const cargarEtiquetasAplicadas = useCallback(async () => {
    const data = await api.get<EtiquetaAplicada[]>(`/api/core/conversaciones/${conversacionId}/etiquetas/`);
    setEtiquetasAplicadas(data);
  }, [conversacionId]);

  // Carga inicial de todo lo de esta conversación + catálogos (equipos/etiquetas).
  useEffect(() => {
    setCargando(true);
    Promise.all([
      cargarConversacion(),
      cargarMensajes(),
      cargarNotas(),
      cargarObservaciones(),
      cargarEtiquetasAplicadas(),
      api.get<Paginated<Team>>("/api/core/teams/").then((d) => setTeams(d.results)),
      api.get<Paginated<Etiqueta>>("/api/core/etiquetas/").then((d) => setCatalogoEtiquetas(d.results)),
    ]).finally(() => setCargando(false));
  }, [conversacionId, cargarConversacion, cargarMensajes, cargarNotas, cargarObservaciones, cargarEtiquetasAplicadas]);

  // Polling de respaldo — se pausa si la pestaña pasa a segundo plano
  // (§3.3/§7.3 del documento de requerimientos).
  useEffect(() => {
    const idMensajes = setInterval(() => {
      if (!document.hidden) cargarMensajes();
    }, POLLING_MENSAJES_MS);
    const idConv = setInterval(() => {
      if (!document.hidden) cargarConversacion();
    }, POLLING_CONVERSACION_MS);

    return () => {
      clearInterval(idMensajes);
      clearInterval(idConv);
    };
  }, [cargarMensajes, cargarConversacion]);

  // Renovación del lock mientras la pantalla siga abierta y sea mía.
  useEffect(() => {
    if (!esMia || !abierta) return;

    const idLock = setInterval(() => {
      api.post(`/api/core/conversaciones/${conversacionId}/tomar/`).catch(() => {
        // Si falla (ej. el lock ya lo perdimos por algún motivo), la
        // próxima acción real del operador (responder/etc.) va a fallar
        // con un error explícito y visible — no hace falta duplicarlo acá.
      });
    }, RENOVAR_LOCK_MS);

    return () => clearInterval(idLock);
  }, [esMia, abierta, conversacionId]);

  useOperatorSocket((evento) => {
    if (evento.conversacion_id !== conversacionId) return;
    if (evento.tipo === "mensaje_nuevo") cargarMensajes();
    if (evento.tipo === "conversacion_actualizada") {
      cargarConversacion();
      cargarEtiquetasAplicadas();
    }
    if (evento.tipo === "nota_interna_nueva") cargarNotas();
  });

  async function tomar() {
    try {
      await api.post(`/api/core/conversaciones/${conversacionId}/tomar/`);
      await cargarConversacion();
    } catch (err) {
      setError(extraerMensajeDeError(err) ?? "No se pudo tomar la conversación.");
    }
  }

  async function enviarRespuesta() {
    if (!textoRespuesta.trim()) return;
    setEnviandoRespuesta(true);
    setAvisoEntrega(null);
    try {
      const resultado = await api.post<{ entregado: boolean }>(`/api/core/conversaciones/${conversacionId}/responder/`, {
        texto: textoRespuesta,
      });
      setTextoRespuesta("");
      await Promise.all([cargarMensajes(), cargarConversacion()]);
      if (!resultado.entregado) {
        setAvisoEntrega("El mensaje quedó registrado, pero no se confirmó la entrega al contacto (revisar el canal).");
      }
    } catch (err) {
      setError(extraerMensajeDeError(err) ?? "No se pudo enviar la respuesta.");
    } finally {
      setEnviandoRespuesta(false);
    }
  }

  async function enviarNota() {
    if (!textoNota.trim()) return;
    setEnviandoNota(true);
    try {
      await api.post(`/api/core/conversaciones/${conversacionId}/notas-internas/`, { texto: textoNota });
      setTextoNota("");
      await cargarNotas();
    } catch (err) {
      setError(extraerMensajeDeError(err) ?? "No se pudo guardar la nota interna.");
    } finally {
      setEnviandoNota(false);
    }
  }

  async function enviarObservacion() {
    if (!textoObservacion.trim()) return;
    setEnviandoObservacion(true);
    try {
      await api.post(`/api/core/conversaciones/${conversacionId}/observaciones/`, { texto: textoObservacion });
      setTextoObservacion("");
      await cargarObservaciones();
    } catch (err) {
      setError(extraerMensajeDeError(err) ?? "No se pudo guardar la observación.");
    } finally {
      setEnviandoObservacion(false);
    }
  }

  async function derivar() {
    if (!derivarTeam || !derivarObservacion.trim()) return;
    setDerivando(true);
    try {
      await api.post(`/api/core/conversaciones/${conversacionId}/derivar/`, {
        team: Number(derivarTeam),
        observacion: derivarObservacion,
      });
      setMostrarDerivar(false);
      setDerivarTeam("");
      setDerivarObservacion("");
      navigate("/bandeja/mias");
    } catch (err) {
      setError(extraerMensajeDeError(err) ?? "No se pudo derivar la conversación.");
    } finally {
      setDerivando(false);
    }
  }

  async function cerrar() {
    if (!window.confirm("¿Cerrar esta conversación? No se puede reabrir desde acá.")) return;
    setCerrando(true);
    try {
      await api.post(`/api/core/conversaciones/${conversacionId}/cerrar/`);
      await cargarConversacion();
    } catch (err) {
      setError(extraerMensajeDeError(err) ?? "No se pudo cerrar la conversación.");
    } finally {
      setCerrando(false);
    }
  }

  async function aplicarEtiqueta(etiqueta: Etiqueta, observacion?: string) {
    setAplicandoEtiqueta(etiqueta.id);
    try {
      await api.post(`/api/core/conversaciones/${conversacionId}/etiquetas/`, {
        etiqueta: etiqueta.id,
        ...(observacion ? { observacion } : {}),
      });
      await cargarEtiquetasAplicadas();
      if (observacion) await cargarObservaciones();
      setPendienteObservacionEtiqueta(null);
      setTextoObservacionEtiqueta("");
    } catch (err) {
      setError(extraerMensajeDeError(err) ?? "No se pudo aplicar la etiqueta.");
    } finally {
      setAplicandoEtiqueta(null);
    }
  }

  function onClickEtiqueta(etiqueta: Etiqueta) {
    if (ETIQUETAS_QUE_PIDEN_OBSERVACION.includes(etiqueta.codigo)) {
      setPendienteObservacionEtiqueta(etiqueta);

      return;
    }
    aplicarEtiqueta(etiqueta);
  }

  async function quitarEtiqueta(etiquetaId: number) {
    try {
      await api.delete(`/api/core/conversaciones/${conversacionId}/etiquetas/${etiquetaId}/`);
      await cargarEtiquetasAplicadas();
    } catch (err) {
      setError(extraerMensajeDeError(err) ?? "No se pudo quitar la etiqueta.");
    }
  }

  if (cargando) return <div className="page-loading">Cargando…</div>;
  if (!conversacion) return <div className="page">{error ?? "No se encontró la conversación."}</div>;

  const idsAplicadas = new Set(etiquetasAplicadas.map((e) => e.etiqueta.id));

  return (
    <div className="page conversation-page">
      <button type="button" className="btn btn-link" onClick={() => navigate(-1)}>
        ← Volver a la bandeja
      </button>

      <div className="conversation-header">
        <div>
          <h1>{conversacion.contact.nombre || conversacion.contact.identificador_externo}</h1>
          <p className="text-muted">
            {CANAL_TIPO_LABELS[conversacion.canal] ?? conversacion.canal_display} · Equipo:{" "}
            {conversacion.team_nombre ?? "sin asignar"} ·{" "}
            <span className={`badge badge-${conversacion.estado_operativo}`}>
              {ESTADO_OPERATIVO_LABELS[conversacion.estado_operativo]}
            </span>
          </p>
        </div>
        <div className="conversation-actions">
          {abierta && !esMia && (
            <button type="button" className="btn btn-primary" onClick={tomar}>
              Tomar
            </button>
          )}
          {abierta && esMia && (
            <>
              <button type="button" className="btn btn-secondary" onClick={() => setMostrarDerivar((s) => !s)}>
                Derivar
              </button>
              <button type="button" className="btn btn-danger" disabled={cerrando} onClick={cerrar}>
                {cerrando ? "Cerrando…" : "Cerrar"}
              </button>
            </>
          )}
        </div>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      {mostrarDerivar && (
        <div className="card">
          <h3>Derivar a otro equipo</h3>
          <label>
            Equipo destino
            <select value={derivarTeam} onChange={(e) => setDerivarTeam(e.target.value)}>
              <option value="">Elegir equipo…</option>
              {teams
                .filter((t) => t.id !== conversacion.team)
                .map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                  </option>
                ))}
            </select>
          </label>
          <label>
            Observación (obligatoria)
            <textarea
              rows={2}
              value={derivarObservacion}
              onChange={(e) => setDerivarObservacion(e.target.value)}
              placeholder="Por qué se deriva, para que el equipo destino tenga contexto…"
            />
          </label>
          <button
            type="button"
            className="btn btn-primary"
            disabled={derivando || !derivarTeam || !derivarObservacion.trim()}
            onClick={derivar}
          >
            {derivando ? "Derivando…" : "Confirmar derivación"}
          </button>
        </div>
      )}

      <div className="tabs">
        <button type="button" className={tab === "mensajes" ? "active" : ""} onClick={() => setTab("mensajes")}>
          Mensajes
        </button>
        <button type="button" className={tab === "notas" ? "active" : ""} onClick={() => setTab("notas")}>
          Notas internas ({notas.length})
        </button>
        <button type="button" className={tab === "observaciones" ? "active" : ""} onClick={() => setTab("observaciones")}>
          Observaciones ({observaciones.length})
        </button>
        <button type="button" className={tab === "etiquetas" ? "active" : ""} onClick={() => setTab("etiquetas")}>
          Etiquetas ({etiquetasAplicadas.length})
        </button>
      </div>

      {tab === "mensajes" && (
        <div className="thread">
          <div className="thread-messages" ref={hiloMensajesRef}>
            {mensajes.map((m) => (
              <div key={m.id} className={`thread-msg thread-msg-${m.remitente.toLowerCase()}`}>
                <div className="thread-msg-meta">
                  {m.remitente === "CONTACTO" ? "Contacto" : m.remitente === "OPERADOR" ? "Operador" : "Sistema / bot"} ·{" "}
                  {formatearFecha(m.creado_at)}
                </div>
                <div className="thread-msg-body">{renderMarkup(m.texto)}</div>
              </div>
            ))}
          </div>

          {avisoEntrega && <div className="alert alert-warning">{avisoEntrega}</div>}

          {abierta && esMia ? (
            <div className="thread-composer">
              <MessageEditor value={textoRespuesta} onChange={setTextoRespuesta} rows={3} disabled={enviandoRespuesta} />
              <button
                type="button"
                className="btn btn-primary"
                disabled={enviandoRespuesta || !textoRespuesta.trim()}
                onClick={enviarRespuesta}
              >
                {enviandoRespuesta ? "Enviando…" : "Enviar"}
              </button>
            </div>
          ) : (
            <p className="text-muted">
              {abierta ? "Tomá la conversación para poder responder." : "Esta conversación está cerrada."}
            </p>
          )}
        </div>
      )}

      {tab === "notas" && (
        <div className="thread">
          <div className="thread-messages">
            {notas.length === 0 && <p className="text-muted">Sin notas internas todavía.</p>}
            {notas.map((n) => (
              <div key={n.id} className="thread-msg thread-msg-nota">
                <div className="thread-msg-meta">
                  {n.operador_email ?? "—"} · {formatearFecha(n.creado_at)}
                </div>
                <div className="thread-msg-body">{n.texto}</div>
              </div>
            ))}
          </div>
          <div className="thread-composer">
            <textarea
              rows={2}
              value={textoNota}
              onChange={(e) => setTextoNota(e.target.value)}
              placeholder="Nota visible sólo para operadores — nunca sale al contacto…"
              disabled={enviandoNota}
            />
            <button type="button" className="btn btn-secondary" disabled={enviandoNota || !textoNota.trim()} onClick={enviarNota}>
              {enviandoNota ? "Guardando…" : "Agregar nota"}
            </button>
          </div>
        </div>
      )}

      {tab === "observaciones" && (
        <div className="thread">
          <div className="thread-messages">
            {observaciones.length === 0 && <p className="text-muted">Sin observaciones todavía.</p>}
            {observaciones.map((o) => (
              <div key={o.id} className="thread-msg thread-msg-nota">
                <div className="thread-msg-meta">
                  {o.operador_email ?? "—"} · {formatearFecha(o.creado_at)}
                </div>
                <div className="thread-msg-body">{o.texto}</div>
              </div>
            ))}
          </div>
          <div className="thread-composer">
            <textarea
              rows={2}
              value={textoObservacion}
              onChange={(e) => setTextoObservacion(e.target.value)}
              placeholder="Bitácora de contexto de esta conversación…"
              disabled={enviandoObservacion}
            />
            <button
              type="button"
              className="btn btn-secondary"
              disabled={enviandoObservacion || !textoObservacion.trim()}
              onClick={enviarObservacion}
            >
              {enviandoObservacion ? "Guardando…" : "Agregar observación"}
            </button>
          </div>
        </div>
      )}

      {tab === "etiquetas" && (
        <div className="thread">
          <div className="etiquetas-aplicadas">
            {etiquetasAplicadas.length === 0 && <p className="text-muted">Sin etiquetas aplicadas.</p>}
            {etiquetasAplicadas.map((ea) => (
              <span
                key={ea.id}
                className="chip"
                style={{ backgroundColor: ea.etiqueta.color, color: ea.etiqueta.color_texto }}
              >
                {ea.etiqueta.nombre || ea.etiqueta.codigo}
                <button type="button" className="chip-remove" onClick={() => quitarEtiqueta(ea.etiqueta.id)}>
                  ×
                </button>
              </span>
            ))}
          </div>

          <h3>Catálogo</h3>
          <div className="etiquetas-catalogo">
            {catalogoEtiquetas.map((et) => (
              <button
                key={et.id}
                type="button"
                className="chip chip-selectable"
                style={{
                  backgroundColor: et.color,
                  color: et.color_texto,
                  opacity: idsAplicadas.has(et.id) ? 0.5 : 1,
                }}
                disabled={aplicandoEtiqueta === et.id}
                onClick={() => onClickEtiqueta(et)}
              >
                {et.nombre || et.codigo}
              </button>
            ))}
          </div>

          {pendienteObservacionEtiqueta && (
            <div className="card">
              <h3>Observación para «{pendienteObservacionEtiqueta.nombre}»</h3>
              <textarea
                rows={2}
                value={textoObservacionEtiqueta}
                onChange={(e) => setTextoObservacionEtiqueta(e.target.value)}
                placeholder="Obligatoria para esta etiqueta…"
              />
              <div className="conversation-actions">
                <button
                  type="button"
                  className="btn btn-primary"
                  disabled={!textoObservacionEtiqueta.trim()}
                  onClick={() => aplicarEtiqueta(pendienteObservacionEtiqueta, textoObservacionEtiqueta)}
                >
                  Confirmar
                </button>
                <button type="button" className="btn btn-link" onClick={() => setPendienteObservacionEtiqueta(null)}>
                  Cancelar
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
