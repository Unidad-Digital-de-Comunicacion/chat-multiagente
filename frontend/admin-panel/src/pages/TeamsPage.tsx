import { type FormEvent, useEffect, useState } from "react";

import { api, ApiError } from "../api/client";
import Modal from "../components/Modal";
import { useAuth } from "../auth/AuthContext";
import { hasPerm } from "../auth/permissions";
import type { Paginated, Team, UserRow } from "../types";

export default function TeamsPage() {
  const { me } = useAuth();
  const canCreate = hasPerm(me, "teams.add_team");
  const canEdit = hasPerm(me, "teams.change_team");
  const canDelete = hasPerm(me, "teams.delete_team");

  const [teams, setTeams] = useState<Team[] | null>(null);
  const [users, setUsers] = useState<UserRow[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [editing, setEditing] = useState<Team | null>(null);

  async function load() {
    const data = await api.get<Paginated<Team>>("/api/core/teams/");
    setTeams(data.results);
  }

  async function loadUsers() {
    // No todos los grupos tienen `users.view_user` (ver
    // users.group_permissions); si no lo tiene, el selector de miembros
    // queda vacío y la página no se cae por eso.
    try {
      const data = await api.get<Paginated<UserRow>>("/api/core/users/");
      setUsers(data.results);
    } catch {
      setUsers([]);
    }
  }

  useEffect(() => {
    load();
    loadUsers();
  }, []);

  async function eliminar(team: Team) {
    if (!confirm(`¿Eliminar el equipo "${team.name}"?`)) return;
    await api.delete(`/api/core/teams/${team.id}/`);
    load();
  }

  if (!teams) return <div className="page-loading">Cargando…</div>;

  return (
    <div>
      <div className="page-header">
        <h2>Equipos</h2>
        {canCreate && (
          <button className="btn btn-primary" onClick={() => setShowCreate(true)}>
            + Nuevo equipo
          </button>
        )}
      </div>

      <table className="table">
        <thead>
          <tr>
            <th>Nombre</th>
            <th>Miembros</th>
            <th>Activo</th>
            {(canEdit || canDelete) && <th></th>}
          </tr>
        </thead>
        <tbody>
          {teams.map((t) => (
            <tr key={t.id}>
              <td>{t.name}</td>
              <td>{t.members.length}</td>
              <td>{t.is_active ? "Sí" : "No"}</td>
              {(canEdit || canDelete) && (
                <td className="table-actions">
                  {canEdit && (
                    <button className="btn btn-ghost" onClick={() => setEditing(t)}>
                      Editar
                    </button>
                  )}
                  {canDelete && (
                    <button className="btn btn-ghost btn-danger" onClick={() => eliminar(t)}>
                      Eliminar
                    </button>
                  )}
                </td>
              )}
            </tr>
          ))}
          {teams.length === 0 && (
            <tr>
              <td colSpan={4} className="text-muted text-center">
                Sin equipos todavía. El árbol de menú necesita al menos uno para las opciones de Derivación.
              </td>
            </tr>
          )}
        </tbody>
      </table>

      {showCreate && (
        <TeamFormModal
          users={users}
          onClose={() => setShowCreate(false)}
          onSaved={() => {
            setShowCreate(false);
            load();
          }}
        />
      )}
      {editing && (
        <TeamFormModal
          team={editing}
          users={users}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            load();
          }}
        />
      )}
    </div>
  );
}

function TeamFormModal({
  team,
  users,
  onClose,
  onSaved,
}: {
  team?: Team;
  users: UserRow[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const [name, setName] = useState(team?.name ?? "");
  const [members, setMembers] = useState<number[]>(team?.members ?? []);
  const [isActive, setIsActive] = useState(team?.is_active ?? true);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  function toggleMember(id: number) {
    setMembers((prev) => (prev.includes(id) ? prev.filter((m) => m !== id) : [...prev, id]));
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const body = { name, members, is_active: isActive };
      if (team) await api.patch(`/api/core/teams/${team.id}/`, body);
      else await api.post("/api/core/teams/", body);
      onSaved();
    } catch (err) {
      setError(err instanceof ApiError ? "No se pudo guardar. Revisá los datos." : "Error de conexión.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal title={team ? "Editar equipo" : "Nuevo equipo"} onClose={onClose}>
      <form onSubmit={handleSubmit} className="form-stack">
        <label>
          Nombre
          <input required value={name} onChange={(e) => setName(e.target.value)} />
        </label>
        <label className="checkbox-label">
          <input type="checkbox" checked={isActive} onChange={(e) => setIsActive(e.target.checked)} />
          Activo
        </label>
        <div>
          <div className="field-label">Miembros</div>
          <div className="checkbox-list">
            {users.length === 0 && <div className="text-muted">No hay usuarios cargados.</div>}
            {users.map((u) => (
              <label key={u.id} className="checkbox-label">
                <input type="checkbox" checked={members.includes(u.id)} onChange={() => toggleMember(u.id)} />
                {u.email}
              </label>
            ))}
          </div>
        </div>
        {error && <div className="form-error">{error}</div>}
        <button className="btn btn-primary" type="submit" disabled={submitting}>
          {submitting ? "Guardando…" : "Guardar"}
        </button>
      </form>
    </Modal>
  );
}
