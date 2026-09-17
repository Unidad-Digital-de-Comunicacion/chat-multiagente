import { type ChangeEvent, useEffect, useState } from "react";

import { api, ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { isPlatformSuperuser } from "../auth/permissions";
import { CANAL_TIPO_LABELS, type CanalTipo, type ConversacionHistorialRow, type Paginated } from "../types";

// Vista de sólo lectura para `administradores` (una organización,
// `conversations.ver_historial_conversacion`) y para el superusuario de
// plataforma (todas, agrupadas por organización) — nunca mensajes,
// etiquetas ni notas internas, sólo inicio/derivación/fin (ver el
// docstring de `ConversacionHistorialSerializer` en Core). Filtros y
// paginación reflejan exactamente `aplicar_filtros_historial` del backend
// — no hay ningún filtro que se resuelva sólo del lado del cliente.

interface Filtros {
  canal: CanalTipo | "";
  derivada: "" | "true" | "false";
  desde: string;
  hasta: string;
  q: string;
}

const FILTROS_VACIOS: Filtros = { canal: "", derivada: "", desde: "", hasta: "", q: "" };

function construirQuery(filtros: Filtros, page: number): string {
  const params = new URLSearchParams();

  if (filtros.canal) params.set("canal", filtros.canal);

  if (filtros.derivada) params.set("derivada", filtros.derivada);

  if (filtros.desde) params.set("desde", filtros.desde);

  if (filtros.hasta) params.set("hasta", filtros.hasta);

  if (filtros.q) params.set("q", filtros.q);

  if (page > 1) params.set("page", String(page));

  const query = params.toString();

  return query ? `?${query}` : "";
}

function formatearFecha(iso: string | null): string {
  if (!iso) return "—";

  return new Date(iso).toLocaleString("es-AR");
}

function EstadoBadge({ fila }: { fila: ConversacionHistorialRow }) {
  if (fila.estado === "CERRADA") return <span className="badge">Cerrada</span>;

  if (fila.operador_email) return <span className="badge badge-warning">Tomada</span>;

  if (fila.team_nombre) return <span className="badge badge-warning">Asignada</span>;

  return <span className="badge badge-warning">Pendiente</span>;
}

function ConversacionRow({ fila }: { fila: ConversacionHistorialRow }) {
  const [abierta, setAbierta] = useState(false);

  return (
    <div className="card historial-row">
      <button type="button" className="historial-row-header" onClick={() => setAbierta((a) => !a)}>
        <span className="menu-toggle" aria-hidden="true">
          {abierta ? "▾" : "▸"}
        </span>
        <span className="historial-row-contacto">{fila.contact.nombre || fila.contact.identificador_externo}</span>
        <span className="text-muted small">{CANAL_TIPO_LABELS[fila.canal]}</span>
        <span className="text-muted small">{formatearFecha(fila.iniciada_at)}</span>
        <EstadoBadge fila={fila} />
      </button>

      {abierta && (
        <div className="historial-row-detalle">
          <div>
            <span className="field-label-sm">Inicio</span>
            <div>
              {formatearFecha(fila.iniciada_at)} — {CANAL_TIPO_LABELS[fila.canal]} ({fila.contact.identificador_externo})
            </div>
          </div>
          <div>
            <span className="field-label-sm">Derivación</span>
            <div>
              {fila.team_nombre
                ? `${fila.team_nombre}${fila.derivada_at ? " — " + formatearFecha(fila.derivada_at) : ""}`
                : "Sin derivar todavía"}
            </div>
          </div>
          <div>
            <span className="field-label-sm">Fin</span>
            <div>
              {fila.estado === "CERRADA"
                ? formatearFecha(fila.cerrada_at)
                : fila.operador_email
                  ? `En curso — tomada por ${fila.operador_email}`
                  : "En curso, sin tomar"}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function AgrupadoPorOrganizacion({ filas }: { filas: ConversacionHistorialRow[] }) {
  const grupos = new Map<string, ConversacionHistorialRow[]>();

  for (const fila of filas) {
    const lista = grupos.get(fila.organization_nombre) ?? [];

    lista.push(fila);
    grupos.set(fila.organization_nombre, lista);
  }

  return (
    <>
      {Array.from(grupos.entries()).map(([organizacion, filasOrg]) => (
        <div key={organizacion} className="card" style={{ marginBottom: "1rem" }}>
          <h3 className="section-title-sm">{organizacion}</h3>
          <div className="historial-list">
            {filasOrg.map((fila) => (
              <ConversacionRow key={fila.id} fila={fila} />
            ))}
          </div>
        </div>
      ))}
    </>
  );
}

function FiltrosBar({
  filtrosInput, setFiltrosInput,
}: {
  filtrosInput: Filtros;
  setFiltrosInput: (f: Filtros) => void;
}) {
  function handleCanalChange(e: ChangeEvent<HTMLSelectElement>) {
    // SAFETY: el `value` de cada `<option>` de acá abajo es literalmente
    // uno de `CanalTipo` o "" (el "Todos") — no hay ningún otro valor
    // posible que el navegador pueda mandar en este `<select>`.
    setFiltrosInput({ ...filtrosInput, canal: e.target.value as CanalTipo | "" });
  }

  function handleDerivadaChange(e: ChangeEvent<HTMLSelectElement>) {
    // SAFETY: mismo criterio — los únicos `value` posibles de las 3
    // `<option>` de acá abajo son exactamente los de `Filtros["derivada"]`.
    setFiltrosInput({ ...filtrosInput, derivada: e.target.value as Filtros["derivada"] });
  }

  return (
    <div className="card historial-filtros" style={{ marginBottom: "1rem" }}>
      <div className="historial-filtros-fila">
        <label>
          <span className="field-label-sm">Canal</span>
          <select value={filtrosInput.canal} onChange={handleCanalChange}>
            <option value="">Todos</option>
            {Object.entries(CANAL_TIPO_LABELS).map(([valor, etiqueta]) => (
              <option key={valor} value={valor}>
                {etiqueta}
              </option>
            ))}
          </select>
        </label>

        <label>
          <span className="field-label-sm">Derivación</span>
          <select value={filtrosInput.derivada} onChange={handleDerivadaChange}>
            <option value="">Todas</option>
            <option value="true">Derivadas</option>
            <option value="false">Sin derivar</option>
          </select>
        </label>

        <label>
          <span className="field-label-sm">Desde</span>
          <input
            type="date"
            value={filtrosInput.desde}
            onChange={(e) => setFiltrosInput({ ...filtrosInput, desde: e.target.value })}
          />
        </label>

        <label>
          <span className="field-label-sm">Hasta</span>
          <input
            type="date"
            value={filtrosInput.hasta}
            onChange={(e) => setFiltrosInput({ ...filtrosInput, hasta: e.target.value })}
          />
        </label>

        <label className="historial-filtro-busqueda">
          <span className="field-label-sm">Teléfono / usuario</span>
          <input
            type="text"
            placeholder="Buscar…"
            value={filtrosInput.q}
            onChange={(e) => setFiltrosInput({ ...filtrosInput, q: e.target.value })}
          />
        </label>

        <button type="button" className="btn btn-ghost btn-sm" onClick={() => setFiltrosInput(FILTROS_VACIOS)}>
          Limpiar filtros
        </button>
      </div>
    </div>
  );
}

function Paginador({
  page, count, onCambiarPage,
}: {
  page: number;
  count: number;
  onCambiarPage: (p: number) => void;
}) {
  const PAGE_SIZE = 25;
  const totalPaginas = Math.max(1, Math.ceil(count / PAGE_SIZE));

  if (totalPaginas <= 1) return null;

  return (
    <div className="toolbar historial-paginador">
      <button type="button" className="btn btn-outline btn-sm" disabled={page <= 1} onClick={() => onCambiarPage(page - 1)}>
        ← Anterior
      </button>
      <span className="text-muted small">
        Página {page} de {totalPaginas} — {count} conversaciones
      </span>
      <button
        type="button"
        className="btn btn-outline btn-sm"
        disabled={page >= totalPaginas}
        onClick={() => onCambiarPage(page + 1)}
      >
        Siguiente →
      </button>
    </div>
  );
}

export default function ConversationHistoryPage() {
  const { me } = useAuth();
  const superuser = isPlatformSuperuser(me);

  const [filtrosInput, setFiltrosInput] = useState<Filtros>(FILTROS_VACIOS);
  const [filtrosAplicados, setFiltrosAplicados] = useState<Filtros>(FILTROS_VACIOS);
  const [page, setPage] = useState(1);

  const [filas, setFilas] = useState<ConversacionHistorialRow[] | null>(null);
  const [count, setCount] = useState(0);
  const [error, setError] = useState<string | null>(null);

  // Los selects/fechas disparan el filtro al toque; el texto libre espera
  // una pausa corta para no mandar un pedido por cada letra tipeada.
  useEffect(() => {
    const id = setTimeout(() => {
      setPage(1);
      setFiltrosAplicados(filtrosInput);
    }, filtrosInput.q !== filtrosAplicados.q ? 400 : 0);

    return () => clearTimeout(id);
    // Sólo depende de `filtrosInput` a propósito — comparar contra
    // `filtrosAplicados.q` es sólo para elegir el delay, no algo que deba
    // disparar este efecto por sí solo.
  }, [filtrosInput]);

  useEffect(() => {
    const base = superuser
      ? "/api/core/plataforma/historial-conversaciones/"
      : "/api/core/conversaciones/historial/";

    api
      .get<Paginated<ConversacionHistorialRow>>(base + construirQuery(filtrosAplicados, page))
      .then((data) => {
        setFilas(data.results);
        setCount(data.count);
      })
      .catch((err) => {
        setError(
          err instanceof ApiError && err.status === 403
            ? "No tenés permiso para ver el historial de conversaciones."
            : err instanceof ApiError && err.status === 400
              ? "Alguno de los filtros no es válido."
              : "No se pudo cargar el historial.",
        );
      });
  }, [superuser, filtrosAplicados, page]);

  if (error) return <div className="empty-state">{error}</div>;

  return (
    <div>
      <div className="page-header">
        <h2>Historial de conversaciones</h2>
      </div>
      <p className="text-muted">
        Inicio, derivación y cierre de cada conversación{superuser ? ", de todas las organizaciones" : " de tu organización"} —
        no incluye el contenido de los mensajes ni las notas internas de los operadores.
      </p>

      <FiltrosBar filtrosInput={filtrosInput} setFiltrosInput={setFiltrosInput} />

      {!filas ? (
        <div className="page-loading">Cargando…</div>
      ) : (
        <>
          {filas.length === 0 && <p className="text-muted">No hay conversaciones que coincidan con estos filtros.</p>}

          {superuser ? (
            <AgrupadoPorOrganizacion filas={filas} />
          ) : (
            <div className="historial-list">
              {filas.map((fila) => (
                <ConversacionRow key={fila.id} fila={fila} />
              ))}
            </div>
          )}

          <Paginador page={page} count={count} onCambiarPage={setPage} />
        </>
      )}
    </div>
  );
}
