import { type FormEvent, useState } from "react";

import { api, extraerMensajeDeError } from "../api/client";
import { useAuth } from "../auth/AuthContext";

// Pantalla forzada (ver ProtectedRoute) cuando un Admin te resetea la
// contraseña (`must_change_password=true`) — pide la actual (la temporal que
// te pasó el Admin) y una elegida por vos. También sirve para cambiarla en
// cualquier otro momento por voluntad propia.
export default function ChangePasswordPage() {
  const { me, refreshMe, logout } = useAuth();
  const [actual, setActual] = useState("");
  const [nueva, setNueva] = useState("");
  const [confirmar, setConfirmar] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);

    if (nueva !== confirmar) {
      setError("Las contraseñas nuevas no coinciden.");

      return;
    }

    setSubmitting(true);

    try {
      await api.post("/api/core/users/me/cambiar-password/", { current_password: actual, new_password: nueva });
      await refreshMe();
    } catch (err) {
      setError(extraerMensajeDeError(err) ?? "No se pudo cambiar la contraseña.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="login-page">
      <div className="login-card">
        <h1>Elegí tu contraseña</h1>
        {me?.must_change_password && (
          <p className="text-muted">
            Un administrador reseteó tu contraseña. Antes de seguir, elegí una propia.
          </p>
        )}
        <form onSubmit={handleSubmit} className="form-stack">
          <label>
            Contraseña actual
            <input type="password" required value={actual} onChange={(e) => setActual(e.target.value)} autoFocus />
          </label>
          <label>
            Contraseña nueva
            <input type="password" required minLength={10} value={nueva} onChange={(e) => setNueva(e.target.value)} />
          </label>
          <label>
            Repetir contraseña nueva
            <input type="password" required value={confirmar} onChange={(e) => setConfirmar(e.target.value)} />
          </label>
          {error && <div className="form-error">{error}</div>}
          <button className="btn btn-primary" type="submit" disabled={submitting}>
            {submitting ? "Guardando…" : "Guardar"}
          </button>
          <button type="button" className="btn btn-ghost" onClick={logout}>
            Cerrar sesión
          </button>
        </form>
      </div>
    </div>
  );
}
