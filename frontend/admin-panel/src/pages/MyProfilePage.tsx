import { type FormEvent, useEffect, useState } from "react";

import { api, extraerMensajeDeError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import AvatarCropper from "../components/AvatarCropper";
import type { Me } from "../types";

export default function MyProfilePage() {
  const { me, refreshMe } = useAuth();
  const [firstName, setFirstName] = useState(me?.first_name ?? "");
  const [lastName, setLastName] = useState(me?.last_name ?? "");
  const [email, setEmail] = useState(me?.email ?? "");
  const [dni, setDni] = useState(me?.dni ?? "");
  const [avatarFile, setAvatarFile] = useState<File | null>(null);
  const [avatarPreview, setAvatarPreview] = useState<string | null>(me?.avatar ?? null);
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!me) return;
    setFirstName(me.first_name);
    setLastName(me.last_name);
    setEmail(me.email);
    setDni(me.dni ?? "");
    setAvatarPreview(me.avatar ?? null);
  }, [me]);

  function handleAvatarChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0] ?? null;
    e.target.value = "";

    if (file) setPendingFile(file);
  }

  function handleCropConfirm(blob: Blob) {
    const file = new File([blob], "avatar.jpg", { type: "image/jpeg" });
    setAvatarFile(file);
    setAvatarPreview(URL.createObjectURL(blob));
    setPendingFile(null);
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSaved(false);
    setSubmitting(true);

    try {
      const form = new FormData();
      form.append("first_name", firstName);
      form.append("last_name", lastName);
      form.append("email", email);
      form.append("dni", dni);

      if (avatarFile) form.append("avatar", avatarFile);

      await api.patch<Me>("/api/core/users/me/", form);
      await refreshMe();
      setSaved(true);
      setAvatarFile(null);
    } catch (err) {
      setError(extraerMensajeDeError(err) ?? "No se pudo guardar.");
    } finally {
      setSubmitting(false);
    }
  }

  if (!me) return <div className="page-loading">Cargando…</div>;

  return (
    <div>
      <div className="page-header">
        <h2>Mi perfil</h2>
      </div>

      <form onSubmit={handleSubmit} className="form-stack card profile-form">
        <div className="profile-avatar-row">
          <div className="avatar-preview">
            {avatarPreview ? <img src={avatarPreview} alt="Avatar" /> : <span>{firstName[0] || email[0] || "?"}</span>}
          </div>
          <label className="btn btn-outline profile-avatar-upload">
            Cambiar foto
            <input type="file" accept="image/*" onChange={handleAvatarChange} hidden />
          </label>
        </div>

        <label>
          Nombre
          <input value={firstName} onChange={(e) => setFirstName(e.target.value)} />
        </label>
        <label>
          Apellido
          <input value={lastName} onChange={(e) => setLastName(e.target.value)} />
        </label>
        <label>
          Email
          <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
          <span className="text-muted field-help">Es también tu usuario para ingresar.</span>
        </label>
        <label>
          DNI
          <input value={dni} onChange={(e) => setDni(e.target.value)} placeholder="Sin cargar" />
          <span className="text-muted field-help">Se usa para recuperar tu usuario si te olvidás el email.</span>
        </label>

        {error && <div className="form-error">{error}</div>}
        <div className="toolbar">
          <button className="btn btn-primary" type="submit" disabled={submitting}>
            {submitting ? "Guardando…" : "Guardar"}
          </button>
          {saved && <span className="text-muted">Guardado.</span>}
        </div>
      </form>

      {pendingFile && (
        <AvatarCropper file={pendingFile} onCancel={() => setPendingFile(null)} onConfirm={handleCropConfirm} />
      )}
    </div>
  );
}
