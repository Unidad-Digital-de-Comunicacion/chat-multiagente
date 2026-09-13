import { type FormEvent, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../api/client";

const MENSAJE_GENERICO = "Si el email está registrado, te enviamos instrucciones para restablecer la contraseña.";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [enviado, setEnviado] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      await api.post("/api/auth/password-reset/", { email });
    } catch {
      // El back devuelve el mismo mensaje genérico exista o no la cuenta —
      // si igual falla la request (red, 429 del throttle), mostramos el
      // mismo texto de todas formas para no filtrar información.
    } finally {
      setSubmitting(false);
      setEnviado(true);
    }
  }

  return (
    <div className="login-page">
      <div className="login-card">
        <h1>¿Olvidaste tu contraseña?</h1>
        {enviado ? (
          <>
            <p className="text-muted">{MENSAJE_GENERICO}</p>
            <Link to="/login" className="btn btn-outline">
              Volver a ingresar
            </Link>
          </>
        ) : (
          <form onSubmit={handleSubmit} className="form-stack">
            <p className="text-muted">Ingresá tu email y te mandamos un link para elegir una contraseña nueva.</p>
            <label>
              Email
              <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} autoFocus />
            </label>
            <button className="btn btn-primary" type="submit" disabled={submitting}>
              {submitting ? "Enviando…" : "Enviar link"}
            </button>
            <Link to="/login">Volver a ingresar</Link>
          </form>
        )}
      </div>
    </div>
  );
}
