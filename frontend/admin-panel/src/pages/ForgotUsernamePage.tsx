import { type FormEvent, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../api/client";

const MENSAJE_GENERICO =
  "Si el DNI corresponde a una cuenta registrada, te enviamos el email asociado a esa dirección.";

export default function ForgotUsernamePage() {
  const [dni, setDni] = useState("");
  const [enviado, setEnviado] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);

    try {
      await api.post("/api/auth/username-reset/", { dni });
    } catch {
      // El back devuelve el mismo mensaje genérico exista o no el DNI — si
      // igual falla la request (red, 429 del throttle), mostramos el mismo
      // texto de todas formas para no filtrar información.
    } finally {
      setSubmitting(false);
      setEnviado(true);
    }
  }

  return (
    <div className="login-page">
      <div className="login-card">
        <h1>¿Olvidaste tu usuario?</h1>
        {enviado ? (
          <>
            <p className="text-muted">{MENSAJE_GENERICO}</p>
            <Link to="/login" className="btn btn-outline">
              Volver a ingresar
            </Link>
          </>
        ) : (
          <form onSubmit={handleSubmit} className="form-stack">
            <p className="text-muted">
              En esta plataforma tu usuario es tu email. Ingresá tu DNI y, si está cargado en tu cuenta, te
              mandamos ese email a la dirección registrada.
            </p>
            <label>
              DNI
              <input required value={dni} onChange={(e) => setDni(e.target.value)} autoFocus />
            </label>
            <button className="btn btn-primary" type="submit" disabled={submitting}>
              {submitting ? "Enviando…" : "Enviar"}
            </button>
            <Link to="/login">Volver a ingresar</Link>
          </form>
        )}
      </div>
    </div>
  );
}
