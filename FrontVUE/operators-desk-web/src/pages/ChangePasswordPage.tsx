import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import { api, extraerMensajeDeError } from "../api/client";
import { useAuth } from "../auth/AuthContext";

export default function ChangePasswordPage() {
  const { me, refreshMe, logout } = useAuth();
  const navigate = useNavigate();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);

    if (newPassword !== confirmPassword) {
      setError("La confirmación no coincide con la contraseña nueva.");

      return;
    }

    setEnviando(true);

    try {
      await api.post("/api/core/users/me/cambiar-password/", {
        current_password: currentPassword,
        new_password: newPassword,
      });
      await refreshMe();
      navigate("/", { replace: true });
    } catch (err) {
      setError(extraerMensajeDeError(err) ?? "No se pudo cambiar la contraseña.");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="auth-page">
      <form className="auth-card" onSubmit={onSubmit}>
        <h1>Cambiar contraseña</h1>
        {me?.must_change_password && (
          <p className="text-muted">
            Un administrador reinició tu contraseña — elegí una nueva antes de seguir.
          </p>
        )}
        {error && <div className="alert alert-error">{error}</div>}

        <label>
          Contraseña actual
          <input
            type="password"
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            required
            disabled={enviando}
          />
        </label>
        <label>
          Contraseña nueva
          <input
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            required
            disabled={enviando}
          />
        </label>
        <label>
          Confirmar contraseña nueva
          <input
            type="password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            required
            disabled={enviando}
          />
        </label>

        <button type="submit" className="btn btn-primary" disabled={enviando}>
          {enviando ? "Guardando…" : "Guardar"}
        </button>
        <button type="button" className="btn btn-link" onClick={logout} disabled={enviando}>
          Cancelar y cerrar sesión
        </button>
      </form>
    </div>
  );
}
