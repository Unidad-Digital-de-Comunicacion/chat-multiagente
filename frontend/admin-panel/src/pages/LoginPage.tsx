import { type FormEvent, useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import { ApiError } from "../api/client";

function formatearFechaHora(iso: string): string {
  try {
    return new Date(iso).toLocaleString("es-AR", { dateStyle: "short", timeStyle: "short" });
  } catch {
    return iso;
  }
}

export default function LoginPage() {
  const { me, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (me) {
    const from = (location.state as { from?: string } | null)?.from || "/menu";
    return <Navigate to={from} replace />;
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(email, password);
      navigate("/menu", { replace: true });
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setError("Email o contraseña incorrectos.");
      } else if (err instanceof ApiError && err.status === 429) {
        const data = err.data as { blocked_until?: string } | null;
        const hasta = data?.blocked_until ? ` (hasta ${formatearFechaHora(data.blocked_until)})` : "";
        setError(`Demasiados intentos fallidos desde esta conexión. Probá de nuevo más tarde${hasta}.`);
      } else {
        setError("No se pudo conectar con el servidor.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="login-page">
      <form className="login-card" onSubmit={handleSubmit}>
        <h1>Chat Multiagente</h1>
        <p className="text-muted">Admin Panel</p>
        <label>
          Email
          <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} autoFocus />
        </label>
        <label>
          Contraseña
          <input type="password" required value={password} onChange={(e) => setPassword(e.target.value)} />
        </label>
        {error && <div className="form-error">{error}</div>}
        <button className="btn btn-primary" type="submit" disabled={submitting}>
          {submitting ? "Ingresando…" : "Ingresar"}
        </button>
        <div className="login-links">
          <Link to="/olvide-usuario">¿Olvidaste tu usuario?</Link>
          <Link to="/olvide-contrasena">¿Olvidaste tu contraseña?</Link>
        </div>
      </form>
    </div>
  );
}
