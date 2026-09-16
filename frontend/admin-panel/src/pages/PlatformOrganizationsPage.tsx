import { type ChangeEvent, type FormEvent, useEffect, useState } from "react";

import { api, ApiError, extraerMensajeDeError } from "../api/client";
import Modal from "../components/Modal";
import { PLAN_LABELS, type PlatformOrganization, type Plan, type Paginated } from "../types";

function limiteTexto(n: number): string {
  return n === 0 ? "Sin límite" : String(n);
}

export default function PlatformOrganizationsPage() {
  const [orgs, setOrgs] = useState<PlatformOrganization[] | null>(null);
  const [verEliminadas, setVerEliminadas] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [editing, setEditing] = useState<PlatformOrganization | null>(null);

  async function load(incluirEliminadas = verEliminadas) {
    try {
      const path = incluirEliminadas
        ? "/api/core/plataforma/organizaciones/?incluir_eliminadas=1"
        : "/api/core/plataforma/organizaciones/";

      const data = await api.get<Paginated<PlatformOrganization>>(path);
      setOrgs(data.results);
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 403
          ? "Esta sección es sólo para el superusuario de plataforma."
          : "No se pudo cargar la lista.",
      );
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function eliminar(org: PlatformOrganization) {
    if (
      !confirm(
        `¿Eliminar "${org.name}"? También se van a eliminar (y desactivar) TODOS sus usuarios. Se puede `
        + "restaurar después, no se pierde nada.",
      )
    ) {
      return;
    }

    await api.delete(`/api/core/plataforma/organizaciones/${org.id}/`);
    load();
  }

  async function restaurar(org: PlatformOrganization) {
    await api.post(`/api/core/plataforma/organizaciones/${org.id}/restaurar/`);
    load();
  }

  if (error) return <div className="empty-state">{error}</div>;

  if (!orgs) return <div className="page-loading">Cargando…</div>;

  return (
    <div>
      <div className="page-header">
        <h2>Organizaciones</h2>
        <button className="btn btn-primary" onClick={() => setShowCreate(true)}>
          + Nueva organización
        </button>
      </div>
      <p className="text-muted">
        Todas las organizaciones de la plataforma, su plan y sus límites de uso (0 = sin límite).
        "Eliminar" es reversible: no borra nada, desactiva la organización y todos sus usuarios — se
        puede restaurar después.
      </p>

      <label className="checkbox-label">
        <input
          type="checkbox"
          checked={verEliminadas}
          onChange={(e) => { setVerEliminadas(e.target.checked); load(e.target.checked); }}
        />
        Ver eliminadas
      </label>

      <table className="table">
        <thead>
          <tr>
            <th>Nombre</th>
            <th>Slug</th>
            <th>Plan</th>
            <th>Operadores concurrentes</th>
            <th>Usuarios</th>
            <th>Conversaciones/mes</th>
            <th>Estado</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {orgs.map((o) => (
            <tr key={o.id}>
              <td>{o.name}</td>
              <td className="text-muted">{o.slug}</td>
              <td>{PLAN_LABELS[o.plan]}</td>
              <td>{limiteTexto(o.connection_limit)}</td>
              <td>{limiteTexto(o.user_limit)}</td>
              <td>{limiteTexto(o.monthly_conversation_limit)}</td>
              <td>
                {o.deleted_at ? (
                  <span className="badge badge-warning">Eliminada</span>
                ) : o.is_active ? (
                  "Activa"
                ) : (
                  "Inactiva"
                )}
              </td>
              <td className="table-actions">
                {o.deleted_at ? (
                  <button className="btn btn-ghost" onClick={() => restaurar(o)}>
                    Restaurar
                  </button>
                ) : (
                  <>
                    <button className="btn btn-ghost" onClick={() => setEditing(o)}>
                      Editar
                    </button>
                    <button className="btn btn-ghost btn-danger" onClick={() => eliminar(o)}>
                      Eliminar
                    </button>
                  </>
                )}
              </td>
            </tr>
          ))}
          {orgs.length === 0 && (
            <tr>
              <td colSpan={8} className="text-muted text-center">
                Sin organizaciones todavía.
              </td>
            </tr>
          )}
        </tbody>
      </table>

      {showCreate && (
        <OrganizationFormModal onClose={() => setShowCreate(false)} onSaved={() => { setShowCreate(false); load(); }} />
      )}
      {editing && (
        <OrganizationFormModal
          org={editing}
          onClose={() => setEditing(null)}
          onSaved={() => { setEditing(null); load(); }}
        />
      )}
    </div>
  );
}

function OrganizationFormModal({
  org, onClose, onSaved,
}: {
  org?: PlatformOrganization;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [name, setName] = useState(org?.name ?? "");
  const [slug, setSlug] = useState(org?.slug ?? "");
  const [plan, setPlan] = useState<Plan>(org?.plan ?? "basico");
  const [connectionLimit, setConnectionLimit] = useState(org?.connection_limit ?? 0);
  const [userLimit, setUserLimit] = useState(org?.user_limit ?? 0);
  const [conversationLimit, setConversationLimit] = useState(org?.monthly_conversation_limit ?? 0);
  const [isActive, setIsActive] = useState(org?.is_active ?? true);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);

    const body = {
      name, slug, plan,
      connection_limit: connectionLimit,
      user_limit: userLimit,
      monthly_conversation_limit: conversationLimit,
      is_active: isActive,
    };

    try {
      if (org) {
        await api.patch(`/api/core/plataforma/organizaciones/${org.id}/`, body);
      } else {
        await api.post("/api/core/plataforma/organizaciones/", body);
      }

      onSaved();
    } catch (err) {
      setError(extraerMensajeDeError(err) ?? "No se pudo guardar.");
    } finally {
      setSubmitting(false);
    }
  }

  function handlePlanChange(e: ChangeEvent<HTMLSelectElement>) {
    // SAFETY: las <option> salen de `PLAN_LABELS` (claves = Plan), así que
    // el value siempre es uno de esos literales.
    setPlan(e.target.value as Plan);
  }

  return (
    <Modal title={org ? `Editar ${org.name}` : "Nueva organización"} onClose={onClose}>
      <form onSubmit={handleSubmit} className="form-stack">
        <label>
          Nombre
          <input required value={name} onChange={(e) => setName(e.target.value)} />
        </label>
        <label>
          Slug
          <input required value={slug} onChange={(e) => setSlug(e.target.value)} />
        </label>
        <label>
          Plan
          <select value={plan} onChange={handlePlanChange}>
            {Object.entries(PLAN_LABELS).map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        </label>
        <label>
          Límite de operadores concurrentes
          <input type="number" min={0} value={connectionLimit} onChange={(e) => setConnectionLimit(Number(e.target.value))} />
          <span className="text-muted field-help">0 = sin límite.</span>
        </label>
        <label>
          Límite de usuarios
          <input type="number" min={0} value={userLimit} onChange={(e) => setUserLimit(Number(e.target.value))} />
          <span className="text-muted field-help">0 = sin límite.</span>
        </label>
        <label>
          Límite de conversaciones mensuales
          <input type="number" min={0} value={conversationLimit} onChange={(e) => setConversationLimit(Number(e.target.value))} />
          <span className="text-muted field-help">0 = sin límite.</span>
        </label>
        <label className="checkbox-label">
          <input type="checkbox" checked={isActive} onChange={(e) => setIsActive(e.target.checked)} />
          Activa
        </label>
        {error && <div className="form-error">{error}</div>}
        <button className="btn btn-primary" type="submit" disabled={submitting}>
          {submitting ? "Guardando…" : "Guardar"}
        </button>
      </form>
    </Modal>
  );
}
