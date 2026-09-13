import { type FormEvent, useEffect, useState } from "react";

import { api, ApiError } from "../api/client";
import Modal from "../components/Modal";
import AvatarCropper from "../components/AvatarCropper";
import { useAuth } from "../auth/AuthContext";
import { hasPerm } from "../auth/permissions";
import { GROUP_LABELS, type Group, type Paginated, type UserRow } from "../types";

export default function UsersPage() {
  const { me } = useAuth();
  const canView = hasPerm(me, "users.view_user");
  const canCreate = hasPerm(me, "users.add_user");
  const canEdit = hasPerm(me, "users.change_user");
  const canDelete = hasPerm(me, "users.delete_user");

  const [users, setUsers] = useState<UserRow[] | null>(null);
  const [groups, setGroups] = useState<Group[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [editing, setEditing] = useState<UserRow | null>(null);
  const [resetResult, setResetResult] = useState<{ email: string; password: string } | null>(null);

  async function load() {
    try {
      const data = await api.get<Paginated<UserRow>>("/api/core/users/");
      setUsers(data.results);
    } catch (err) {
      setError(err instanceof ApiError && err.status === 403 ? "No tenés permiso para ver esta sección." : "No se pudo cargar la lista.");
    }
  }

  async function loadGroups() {
    try {
      const data = await api.get<Group[]>("/api/core/groups/");
      setGroups(data);
    } catch {
      setGroups([]);
    }
  }

  useEffect(() => {
    load();
    loadGroups();
  }, []);

  async function toggleActivo(user: UserRow) {
    await api.patch(`/api/core/users/${user.id}/`, { is_active: !user.is_active });
    load();
  }

  async function eliminar(user: UserRow) {
    if (!confirm(`¿Eliminar a ${user.email}?`)) return;
    await api.delete(`/api/core/users/${user.id}/`);
    load();
  }

  async function resetearPassword(user: UserRow) {
    if (!confirm(`¿Resetear la contraseña de ${user.email}? Va a tener que elegir una nueva en su próximo ingreso.`)) return;
    const data = await api.post<{ password_temporal: string }>(`/api/core/users/${user.id}/reset-password/`);
    setResetResult({ email: user.email, password: data.password_temporal });
    load();
  }

  if (error) return <div className="empty-state">{error}</div>;
  if (!users) return <div className="page-loading">Cargando…</div>;

  return (
    <div>
      <div className="page-header">
        <h2>Usuarios</h2>
        {canCreate && (
          <button className="btn btn-primary" onClick={() => setShowCreate(true)}>
            + Nuevo usuario
          </button>
        )}
      </div>

      <table className="table">
        <thead>
          <tr>
            <th></th>
            <th>Email</th>
            <th>Nombre</th>
            <th>DNI</th>
            <th>Grupos</th>
            <th>Activo</th>
            {(canEdit || canDelete) && <th></th>}
          </tr>
        </thead>
        <tbody>
          {users.map((u) => (
            <tr key={u.id}>
              <td>{u.avatar_thumbnail ? <img src={u.avatar_thumbnail} alt="" className="avatar-thumb" /> : null}</td>
              <td>{u.email}</td>
              <td>{[u.first_name, u.last_name].filter(Boolean).join(" ") || "—"}</td>
              <td>{u.dni || "—"}</td>
              <td>
                {u.group_names.length === 0
                  ? "—"
                  : u.group_names.map((g) => (
                      <span key={g} className="badge">
                        {GROUP_LABELS[g] ?? g}
                      </span>
                    ))}
              </td>
              <td>
                {canEdit ? (
                  <input type="checkbox" checked={u.is_active} onChange={() => toggleActivo(u)} />
                ) : u.is_active ? (
                  "Sí"
                ) : (
                  "No"
                )}
              </td>
              {(canEdit || canDelete) && (
                <td className="table-actions">
                  {canEdit && (
                    <button className="btn btn-ghost" onClick={() => setEditing(u)}>
                      Editar
                    </button>
                  )}
                  {canEdit && (
                    <button className="btn btn-ghost" onClick={() => resetearPassword(u)}>
                      Resetear contraseña
                    </button>
                  )}
                  {canDelete && (
                    <button className="btn btn-ghost btn-danger" onClick={() => eliminar(u)}>
                      Eliminar
                    </button>
                  )}
                </td>
              )}
            </tr>
          ))}
          {users.length === 0 && (
            <tr>
              <td colSpan={7} className="text-muted text-center">
                Sin usuarios todavía.
              </td>
            </tr>
          )}
        </tbody>
      </table>

      {showCreate && (
        <UserFormModal
          groups={groups}
          onClose={() => setShowCreate(false)}
          onSaved={() => {
            setShowCreate(false);
            load();
          }}
        />
      )}
      {editing && (
        <UserFormModal
          user={editing}
          groups={groups}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            load();
          }}
        />
      )}
      {resetResult && (
        <Modal title="Contraseña reseteada" onClose={() => setResetResult(null)}>
          <p className="text-muted">
            Pasale esta contraseña temporal a <strong>{resetResult.email}</strong> por otro medio (no queda
            guardada en ningún lado — si cerrás esto sin copiarla, hay que resetear de nuevo). Va a tener que
            elegir la suya propia en su próximo ingreso.
          </p>
          <div className="temp-password-box">{resetResult.password}</div>
          <button className="btn btn-primary" onClick={() => setResetResult(null)}>
            Listo
          </button>
        </Modal>
      )}
    </div>
  );
}

function UserFormModal({
  user, groups, onClose, onSaved,
}: {
  user?: UserRow;
  groups: Group[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const [email, setEmail] = useState(user?.email ?? "");
  const [firstName, setFirstName] = useState(user?.first_name ?? "");
  const [lastName, setLastName] = useState(user?.last_name ?? "");
  const [dni, setDni] = useState(user?.dni ?? "");
  const [password, setPassword] = useState("");
  const [selectedGroups, setSelectedGroups] = useState<number[]>(user?.groups ?? []);
  const [avatarFile, setAvatarFile] = useState<File | null>(null);
  const [avatarPreview, setAvatarPreview] = useState<string | null>(user?.avatar ?? null);
  const [pendingAvatarFile, setPendingAvatarFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  function toggleGroup(id: number) {
    setSelectedGroups((prev) => (prev.includes(id) ? prev.filter((g) => g !== id) : [...prev, id]));
  }

  function handleAvatarChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0] ?? null;
    e.target.value = "";
    if (file) setPendingAvatarFile(file);
  }

  function handleCropConfirm(blob: Blob) {
    const file = new File([blob], "avatar.jpg", { type: "image/jpeg" });
    setAvatarFile(file);
    setAvatarPreview(URL.createObjectURL(blob));
    setPendingAvatarFile(null);
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      if (user) {
        await api.patch(`/api/core/users/${user.id}/`, {
          email, first_name: firstName, last_name: lastName, dni,
          groups: selectedGroups,
        });
        if (avatarFile) {
          // Aparte y en multipart — mezclar campos JSON y un archivo en el
          // mismo FormData complica limpiar `groups` a [] (DRF necesita la
          // clave ausente vs. presente-y-vacía para eso en un QueryDict).
          const form = new FormData();
          form.append("avatar", avatarFile);
          await api.patch(`/api/core/users/${user.id}/`, form);
        }
      } else {
        await api.post("/api/core/users/", {
          email, first_name: firstName, last_name: lastName, dni, password,
          groups: selectedGroups,
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
        {user && (
          <div className="profile-avatar-row">
            <div className="avatar-preview">
              {avatarPreview ? <img src={avatarPreview} alt="Avatar" /> : <span>{firstName[0] || email[0] || "?"}</span>}
            </div>
            <label className="btn btn-outline profile-avatar-upload">
              Cambiar foto
              <input type="file" accept="image/*" onChange={handleAvatarChange} hidden />
            </label>
          </div>
        )}
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
          DNI
          <input value={dni} onChange={(e) => setDni(e.target.value)} placeholder="Sin cargar" />
        </label>
        {!user && (
          <label>
            Contraseña
            <input type="password" required minLength={10} value={password} onChange={(e) => setPassword(e.target.value)} />
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

      {pendingAvatarFile && (
        <AvatarCropper
          file={pendingAvatarFile}
          onCancel={() => setPendingAvatarFile(null)}
          onConfirm={handleCropConfirm}
        />
      )}
    </Modal>
  );
}
