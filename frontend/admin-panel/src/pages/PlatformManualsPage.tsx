import { useState } from "react";

import { ApiError, conversationEngineUrl, coreUrl, downloadFile, getAccessToken } from "../api/client";

type DocumentoTecnico = { slug: string; filename: string };

export default function PlatformManualsPage() {
  const [error, setError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState<string | null>(null);
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
    setDownloading("admin-panel");

    try {
      await downloadFile("/api/core/plataforma/manual/", "manual-admin-panel.pdf");
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 403
          ? "Esta sección es sólo para el superusuario de plataforma."
          : "No se pudo descargar el manual.",
      );
    } finally {
      setDownloading(null);
    }
  }

  async function bajarDocumentoTecnico({ slug, filename }: DocumentoTecnico) {
    setError(null);
    setDownloading(slug);

    try {
      await downloadFile(`/api/core/plataforma/manual/${slug}/`, filename);
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 403
          ? "Esta sección es sólo para el superusuario de plataforma."
          : "No se pudo descargar el documento.",
      );
    } finally {
      setDownloading(null);
    }
  }

  return (
    <div>
      <div className="page-header">
        <h2>Manuales y API</h2>
      </div>
      <p className="text-muted">
        El manual de uso del Admin Panel (con capturas de la configuración del core), el contrato de API para
        quien construya un cliente operador (app Android / Operators Desk Web) y la referencia autogenerada
        de la API interna de Core — no incluye Channel Gateway/Analytics/Webchat, que todavía son stubs de
        Fase 0.
      </p>
      {error && <div className="form-error">{error}</div>}

      <div className="card manuals-card">
        <h3>Manual de uso del Admin Panel</h3>
        <p className="text-muted">Capturas de pantalla de las secciones más importantes de la configuración.</p>
        <button className="btn btn-primary" disabled={downloading !== null} onClick={bajarManual}>
          {downloading === "admin-panel" ? "Descargando…" : "Descargar PDF"}
        </button>
      </div>

      <div className="card manuals-card">
        <h3>Contrato de API — Operators Desk</h3>
        <p className="text-muted">
          Autenticación, equipos, etiquetas y todas las actions de una conversación (bandeja, tomar,
          responder, cerrar, derivar, etiquetas, observaciones, notas internas), con ejemplos de
          request/response — para quien construya la app Android o Operators Desk Web contra esta misma API.
        </p>
        <button
          className="btn btn-primary"
          disabled={downloading !== null}
          onClick={() => bajarDocumentoTecnico({ slug: "operators-desk-api", filename: "operators-desk-api-contract.md" })}
        >
          {downloading === "operators-desk-api" ? "Descargando…" : "Descargar contrato (Markdown)"}
        </button>
      </div>

      <div className="card manuals-card">
        <h3>Guía para el agente de la app Android</h3>
        <p className="text-muted">
          Cómo trabajar sobre <code>UDCOperadorAPP</code>: la regla de que el cliente sólo habla con Core
          (nunca con WhatsApp/Messenger/Instagram ni Channel Gateway), mapa del código existente y
          convenciones a seguir para pantallas nuevas.
        </p>
        <button
          className="btn btn-primary"
          disabled={downloading !== null}
          onClick={() =>
            bajarDocumentoTecnico({ slug: "operators-desk-agente-android", filename: "AGENTS-android.md" })
          }
        >
          {downloading === "operators-desk-agente-android" ? "Descargando…" : "Descargar guía (Markdown)"}
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

      <div className="card manuals-card">
        <h3>Referencia de la API de Conversation Engine</h3>
        <p className="text-muted">
          Entrega en tiempo real para clientes operador (Fase 4) — Swagger/Redoc los sirve FastAPI solo, sin
          login. No documentan <code>WS /ws/operador/{"{token}"}</code>, el endpoint que de verdad importa:
          OpenAPI no tiene forma de describir un WebSocket. Ese contrato está en el documento "Contrato de
          API — Operators Desk" de arriba, sección 7.
        </p>
        <div className="toolbar">
          <a className="btn btn-outline" href={conversationEngineUrl("/docs")} target="_blank" rel="noreferrer">
            Abrir Swagger
          </a>
          <a className="btn btn-outline" href={conversationEngineUrl("/redoc")} target="_blank" rel="noreferrer">
            Abrir Redoc
          </a>
        </div>
      </div>
    </div>
  );
}
