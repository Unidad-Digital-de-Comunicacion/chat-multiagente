import { type FormEvent, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { api, ApiError } from "../api/client";

export default function ResetPasswordPage() {
  const { uid, token } = useParams<{ uid: string; token: string }>();
  const navigate = useNavigate();
  const [password, setPassword] = useState("");
  const [confirmar, setConfirmar] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (password !== confirmar) {
      setError("Las contraseñas no coinciden.");
      return;
    }
    setSubmitting(true);
    try {
      await api.post("/api/auth/password-reset-confirm/", { uid, token, new_password: password });
      setOk(true);
    } catch (err) {
      if (err instanceof ApiError && err.data && typeof err.data === "object") {
        setError(Object.values(err.data as Record<string, string[]>).flat().join(" "));
      } else {
        setError("El link no es válido o ya venció. Pedí uno nuevo.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="login-page">
      <div className="login-card">
        <h1>Elegir nueva contraseña</h1>
        {ok ? (
          <>
            <p className="text-muted">Listo, ya podés ingresar con tu contraseña nueva.</p>
            <button className="btn btn-primary" onClick={() => navigate("/login", { replace: true })}>
              Ir a ingresar
            </button>
          </>
        ) : (
          <form onSubmit={handleSubmit} className="form-stack">
            <label>
              Contraseña nueva
              <input
                type="password"
                required
                minLength={10}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoFocus
              />
            </label>
            <label>
              Repetir contraseña
              <input type="password" required value={confirmar} onChange={(e) => setConfirmar(e.target.value)} />
            </label>
            {error && <div className="form-error">{error}</div>}
            <button className="btn btn-primary" type="submit" disabled={submitting}>
              {submitting ? "Guardando…" : "Guardar"}
            </button>
            <Link to="/olvide-contrasena">Pedir un link nuevo</Link>
          </form>
        )}
      </div>
    </div>
  );
}
