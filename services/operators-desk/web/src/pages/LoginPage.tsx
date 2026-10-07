import { useState, type FormEvent } from "react";
import { Navigate, useNavigate } from "react-router-dom";

import { extraerBloqueoHasta, extraerCodigoDeError, extraerMensajeDeError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { formatearFecha } from "../utils/fecha";

export default function LoginPage() {
  const { me, login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [bloqueadoHasta, setBloqueadoHasta] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  // Si ya hay sesión (ej. volvió a /login a mano), no tiene sentido mostrar
  // el formulario de nuevo.
  if (me) return <Navigate to="/" replace />;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBloqueadoHasta(null);
    setEnviando(true);

    try {
      await login(email, password);
      navigate("/", { replace: true });
    } catch (err) {
      const codigo = extraerCodigoDeError(err);

      if (codigo === "throttled") {
        const hasta = extraerBloqueoHasta(err);

        if (hasta) {
          setBloqueadoHasta(hasta);
        } else {
          setError("Demasiados intentos, probá de nuevo en unos minutos.");
        }
      } else {
        setError(extraerMensajeDeError(err) ?? "Usuario o contraseña incorrectos.");
      }
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="auth-page">
      <form className="auth-card" onSubmit={onSubmit}>
        <h1>Operators Desk</h1>
        <p className="text-muted">Ingresá con tu cuenta de operador.</p>

        {bloqueadoHasta && (
          <div className="alert alert-error">
            Cuenta bloqueada temporalmente por varios intentos fallidos. Podés volver a intentar después de{" "}
            {formatearFecha(bloqueadoHasta)}.
          </div>
        )}
        {error && !bloqueadoHasta && <div className="alert alert-error">{error}</div>}

        <label>
          Email
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoFocus
            disabled={enviando}
          />
        </label>
        <label>
          Contraseña
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            disabled={enviando}
          />
        </label>

        <button type="submit" className="btn btn-primary" disabled={enviando}>
          {enviando ? "Ingresando…" : "Ingresar"}
        </button>
      </form>
    </div>
  );
}
