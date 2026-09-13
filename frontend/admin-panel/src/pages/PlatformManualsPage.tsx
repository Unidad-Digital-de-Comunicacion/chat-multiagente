import { useState } from "react";

import { ApiError, coreUrl, downloadFile, getAccessToken } from "../api/client";

export default function PlatformManualsPage() {
  const [error, setError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);
  const [copiado, setCopiado] = useState(false);

  async function copiarToken() {
    const token = getAccessToken();
    if (!token) return;
    await navigator.clipboard.writeText(token);
    setCopiado(true);
    setTimeout(() => setCopiado(false), 3000);
  }

  async function bajarManual() {
    setError(null);
    setDownloading(true);
    try {
      await downloadFile("/api/core/plataforma/manual/", "manual-admin-panel.pdf");
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 403
          ? "Esta sección es sólo para el superusuario de plataforma."
          : "No se pudo descargar el manual.",
      );
    } finally {
      setDownloading(false);
    }
  }

  return (
    <div>
      <div className="page-header">
        <h2>Manuales y API</h2>
      </div>
      <p className="text-muted">
        El manual de uso del Admin Panel (con capturas de la configuración del core) y la referencia
        autogenerada de la API interna de Core — no incluye Channel Gateway/Conversation Engine/Operators
        Desk/Analytics/Webchat, que todavía son stubs de Fase 0.
      </p>

      <div className="card manuals-card">
        <h3>Manual de uso del Admin Panel</h3>
        <p className="text-muted">Capturas de pantalla de las secciones más importantes de la configuración.</p>
        {error && <div className="form-error">{error}</div>}
        <button className="btn btn-primary" disabled={downloading} onClick={bajarManual}>
          {downloading ? "Descargando…" : "Descargar PDF"}
        </button>
      </div>

      <div className="card manuals-card">
        <h3>Referencia de la API interna de Core</h3>
        <p className="text-muted">
          Autogenerada a partir de los serializers/vistas reales (drf-spectacular) — siempre al día con el
          código. Al abrirla, usá el botón "Authorize" (candadito, arriba a la derecha) y pegá tu propio
          token de acceso para que pueda consultar el esquema real.
        </p>
        <div className="toolbar">
          <a className="btn btn-outline" href={coreUrl("/api/core/plataforma/schema/swagger/")} target="_blank" rel="noreferrer">
            Abrir Swagger
          </a>
          <a className="btn btn-outline" href={coreUrl("/api/core/plataforma/schema/redoc/")} target="_blank" rel="noreferrer">
            Abrir Redoc
          </a>
          <button className="btn btn-ghost" onClick={copiarToken}>
            {copiado ? "¡Copiado!" : "Copiar mi token de acceso"}
          </button>
        </div>
      </div>
    </div>
  );
}
