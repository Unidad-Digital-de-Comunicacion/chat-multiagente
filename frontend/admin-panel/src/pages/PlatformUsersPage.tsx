import { type FormEvent, useEffect, useMemo, useState } from "react";

import { api, ApiError } from "../api/client";
import Modal from "../components/Modal";
import { GROUP_LABELS, type Group, type Paginated, type PlatformOrganization, type PlatformUser } from "../types";

function agruparPorOrganizacion(users: PlatformUser[], orgs: PlatformOrganization[]) {
  const porOrg = new Map<number, PlatformUser[]>();
  const sinOrganizacion: PlatformUser[] = [];
  for (const u of users) {
    if (u.organization) {
      const lista = porOrg.get(u.organization) ?? [];
      lista.push(u);
      porOrg.set(u.organization, lista);
    } else {
      sinOrganizacion.push(u);
    }
  }
  const grupos = orgs.map((org) => ({ org, usuarios: porOrg.get(org.id) ?? [] }));
  return { grupos, sinOrganizacion };
}

export default function PlatformUsersPage() {
  const [users, setUsers] = useState<PlatformUser[] | null>(null);
  const [orgs, setOrgs] = useState<PlatformOrganization[]>([]);
  const [groups, setGroups] = useState<Group[]>([]);
  const [busqueda, setBusqueda] = useState("");
  const [verEliminados, setVerEliminados] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [editing, setEditing] = useState<PlatformUser | null>(null);
  const [resetResult, setResetResult] = useState<{ email: string; password: string } | null>(null);

  async function load(incluirEliminados = verEliminados) {
    try {
      const path = incluirEliminados
        ? "/api/core/plataforma/usuarios/?incluir_eliminados=1"
        : "/api/core/plataforma/usuarios/";
      const data = await api.get<Paginated<PlatformUser>>(path);
      setUsers(data.results);
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
    api.get<Paginated<PlatformOrganization>>("/api/core/plataforma/organizaciones/")
      .then((data) => setOrgs(data.results)).catch(() => setOrgs([]));
    api.get<Group[]>("/api/core/groups/").then(setGroups).catch(() => setGroups([]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function resetearPassword(user: PlatformUser) {
    if (!confirm(`¿Resetear la contraseña de ${user.email}?`)) return;
    const data = await api.post<{ password_temporal: string }>(`/api/core/plataforma/usuarios/${user.id}/reset-password/`);
    setResetResult({ email: user.email, password: data.password_temporal });
    load();
  }

  async function eliminar(user: PlatformUser) {
    if (!confirm(`¿Eliminar a ${user.email}? Se puede restaurar después, no se pierde nada.`)) return;
    await api.delete(`/api/core/plataforma/usuarios/${user.id}/`);
    load();
  }

  async function restaurar(user: PlatformUser) {
    await api.post(`/api/core/plataforma/usuarios/${user.id}/restaurar/`);
    load();
  }

  const usuariosFiltrados = useMemo(() => {
    if (!users) return [];
    const texto = busqueda.trim().toLowerCase();
    if (!texto) return users;
    return users.filter((u) =>
      u.email.toLowerCase().includes(texto)
      || `${u.first_name} ${u.last_name}`.toLowerCase().includes(texto));
  }, [users, busqueda]);

  const { grupos, sinOrganizacion } = useMemo(
    () => agruparPorOrganizacion(usuariosFiltrados, orgs), [usuariosFiltrados, orgs],
  );

  if (error) return <div className="empty-state">{error}</div>;
  if (!users) return <div className="page-loading">Cargando…</div>;

  return (
    <div>
      <div className="page-header">
        <h2>Usuarios</h2>
        <button className="btn btn-primary" onClick={() => setShowCreate(true)}>
          + Nuevo usuario
        </button>
      </div>
      <p className="text-muted">
        Usuarios de la plataforma, agrupados por organización. "Eliminar" es reversible: no borra
        nada, sólo desactiva la cuenta — se puede restaurar después.
      </p>

      <div className="platform-users-toolbar">
        <input
          className="platform-users-search"
          placeholder="Buscar por email o nombre…"
          value={busqueda}
          onChange={(e) => setBusqueda(e.target.value)}
        />
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={verEliminados}
            onChange={(e) => { setVerEliminados(e.target.checked); load(e.target.checked); }}
          />
          Ver eliminados
        </label>
      </div>

      {grupos.map(({ org, usuarios }) => (
        <OrganizationUsersGroup
          key={org.id}
          title={org.name}
          usuarios={usuarios}
          onEdit={setEditing}
          onResetPassword={resetearPassword}
          onEliminar={eliminar}
          onRestaurar={restaurar}
        />
      ))}

      {sinOrganizacion.length > 0 && (
        <OrganizationUsersGroup
          title="Cuentas de plataforma (sin organización)"
          usuarios={sinOrganizacion}
          onEdit={setEditing}
          onResetPassword={resetearPassword}
          onEliminar={eliminar}
          onRestaurar={restaurar}
        />
      )}

      {grupos.length === 0 && sinOrganizacion.length === 0 && (
        <div className="empty-state">Sin usuarios que coincidan con la búsqueda.</div>
      )}

      {showCreate && (
        <PlatformUserFormModal orgs={orgs} groups={groups} onClose={() => setShowCreate(false)} onSaved={() => { setShowCreate(false); load(); }} />
      )}
      {editing && (
        <PlatformUserFormModal user={editing} orgs={orgs} groups={groups} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); load(); }} />
      )}
      {resetResult && (
        <Modal title="Contraseña reseteada" onClose={() => setResetResult(null)}>
          <p className="text-muted">
            Pasale esta contraseña temporal a <strong>{resetResult.email}</strong> por otro medio (no queda
            guardada en ningún lado). Va a tener que elegir la suya propia en su próximo ingreso.
          </p>
          <div className="temp-password-box">{resetResult.password}</div>
          <button className="btn btn-primary" onClick={() => setResetResult(null)}>Listo</button>
        </Modal>
      )}
    </div>
  );
}

function OrganizationUsersGroup({
  title, usuarios, onEdit, onResetPassword, onEliminar, onRestaurar,
}: {
  title: string;
  usuarios: PlatformUser[];
  onEdit: (user: PlatformUser) => void;
  onResetPassword: (user: PlatformUser) => void;
  onEliminar: (user: PlatformUser) => void;
  onRestaurar: (user: PlatformUser) => void;
}) {
  return (
    <div className="card platform-org-group">
      <div className="platform-org-group-header">
        <h3>{title}</h3>
        <span className="badge">{usuarios.length} usuario{usuarios.length === 1 ? "" : "s"}</span>
      </div>
      {usuarios.length === 0 ? (
        <p className="text-muted">Sin usuarios todavía.</p>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>Email</th>
              <th>Nombre</th>
              <th>Grupos</th>
              <th>Estado</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {usuarios.map((u) => (
              <tr key={u.id}>
                <td>{u.email}</td>
                <td>{[u.first_name, u.last_name].filter(Boolean).join(" ") || "—"}</td>
                <td>
                  {u.group_names.length === 0
                    ? "—"
                    : u.group_names.map((g) => (
                        <span key={g} className="badge">{GROUP_LABELS[g] ?? g}</span>
                      ))}
                </td>
                <td>
                  {u.deleted_at ? (
                    <span className="badge badge-warning">Eliminado</span>
                  ) : u.is_active ? (
                    "Activo"
                  ) : (
                    "Inactivo"
                  )}
                </td>
                <td className="table-actions">
                  {u.deleted_at ? (
                    <button className="btn btn-ghost" onClick={() => onRestaurar(u)}>Restaurar</button>
                  ) : (
                    <>
                      <button className="btn btn-ghost" onClick={() => onEdit(u)}>Editar</button>
                      <button className="btn btn-ghost" onClick={() => onResetPassword(u)}>Resetear contraseña</button>
                      <button className="btn btn-ghost btn-danger" onClick={() => onEliminar(u)}>Eliminar</button>
                    </>
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

function PlatformUserFormModal({
  user, orgs, groups, onClose, onSaved,
}: {
  user?: PlatformUser;
  orgs: PlatformOrganization[];
  groups: Group[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const [email, setEmail] = useState(user?.email ?? "");
  const [firstName, setFirstName] = useState(user?.first_name ?? "");
  const [lastName, setLastName] = useState(user?.last_name ?? "");
  const [organization, setOrganization] = useState<string>(user?.organization ? String(user.organization) : "");
  const [password, setPassword] = useState("");
  const [selectedGroups, setSelectedGroups] = useState<number[]>(user?.groups ?? []);
  const [isActive, setIsActive] = useState(user?.is_active ?? true);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  function toggleGroup(id: number) {
    setSelectedGroups((prev) => (prev.includes(id) ? prev.filter((g) => g !== id) : [...prev, id]));
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const organizationId = organization ? Number(organization) : null;
      if (user) {
        await api.patch(`/api/core/plataforma/usuarios/${user.id}/`, {
          email, first_name: firstName, last_name: lastName,
          organization: organizationId, groups: selectedGroups, is_active: isActive,
        });
      } else {
        await api.post("/api/core/plataforma/usuarios/", {
          email, first_name: firstName, last_name: lastName, password,
          organization: organizationId, groups: selectedGroups,
        });
      }
      onSaved();
    } catch (err) {
      if (err instanceof ApiError && err.data && typeof err.data === "object") {
        setError(Object.values(err.data as Record<string, string[]>).flat().join(" "));
      } else {
        setError("No se pudo guardar.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal title={user ? `Editar a ${user.email}` : "Nuevo usuario"} onClose={onClose}>
      <form onSubmit={handleSubmit} className="form-stack">
        <label>
          Email
          <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label>
          Nombre
          <input value={firstName} onChange={(e) => setFirstName(e.target.value)} />
        </label>
        <label>
          Apellido
          <input value={lastName} onChange={(e) => setLastName(e.target.value)} />
        </label>
        <label>
          Organización
          <select value={organization} onChange={(e) => setOrganization(e.target.value)}>
            <option value="">Ninguna (cuenta de plataforma)</option>
            {orgs.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
          </select>
        </label>
        {!user && (
          <label>
            Contraseña
            <input type="password" required minLength={10} value={password} onChange={(e) => setPassword(e.target.value)} />
          </label>
        )}
        {user && (
          <label className="checkbox-label">
            <input type="checkbox" checked={isActive} onChange={(e) => setIsActive(e.target.checked)} />
            Activo
          </label>
        )}
        <div>
          <div className="field-label">Grupos (puede pertenecer a más de uno)</div>
          <div className="checkbox-list">
            {groups.map((g) => (
              <label key={g.id} className="checkbox-label">
                <input type="checkbox" checked={selectedGroups.includes(g.id)} onChange={() => toggleGroup(g.id)} />
                {GROUP_LABELS[g.name] ?? g.name}
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
