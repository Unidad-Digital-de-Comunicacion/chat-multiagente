import { useEffect, useState } from "react";

import { api, ApiError } from "../api/client";
import Modal from "../components/Modal";
import type { Paginated, ServiceToken } from "../types";

export default function PlatformTokensPage() {
  const [tokens, setTokens] = useState<ServiceToken[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [generatingId, setGeneratingId] = useState<number | null>(null);
  const [nuevoToken, setNuevoToken] = useState<{ servicio: string; token: string } | null>(null);

  async function load() {
    try {
      const data = await api.get<Paginated<ServiceToken>>("/api/core/plataforma/tokens-servicios/");
      setTokens(data.results);
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 403
          ? "Esta sección es sólo para el superusuario de plataforma."
          : "No se pudo cargar la lista.",
      );
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function toggleActivo(token: ServiceToken) {
    try {
      await api.patch(`/api/core/plataforma/tokens-servicios/${token.id}/`, { activo: !token.activo });
      load();
    } catch (err) {
      alert(err instanceof ApiError && err.data ? JSON.stringify(err.data) : "No se pudo guardar.");
    }
  }

  async function generar(token: ServiceToken) {
    if (
      token.token_configurado
      && !confirm(`Ya hay un token cargado para ${token.servicio_display}. ¿Generar uno nuevo? El anterior deja de servir.`)
    ) {
      return;
    }
    setGeneratingId(token.id);
    try {
      const data = await api.post<{ token: string } & ServiceToken>(
        `/api/core/plataforma/tokens-servicios/${token.id}/generar/`,
      );
      setNuevoToken({ servicio: token.servicio_display, token: data.token });
      load();
    } catch (err) {
      alert(err instanceof ApiError && err.data ? JSON.stringify(err.data) : "No se pudo generar el token.");
    } finally {
      setGeneratingId(null);
    }
  }

  if (error) return <div className="empty-state">{error}</div>;
  if (!tokens) return <div className="page-loading">Cargando…</div>;

  return (
    <div>
      <div className="page-header">
        <h2>Tokens internos</h2>
      </div>
      <p className="text-muted">
        Con qué se va a autenticar cada uno de los OTROS microservicios de este mismo proyecto (Channel
        Gateway, Conversation Engine, Operators Desk, Analytics, Webchat) contra la API de Core. No es la
        api key de un servicio externo como WhatsApp — eso se configura en "Canales", dentro de cada
        organización. Hoy son todos stubs de Fase 0, nada consume estos tokens todavía.
      </p>

      <table className="table">
        <thead>
          <tr>
            <th>Servicio</th>
            <th>Token</th>
            <th>Generado</th>
            <th>Activo</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {tokens.map((t) => (
            <tr key={t.id}>
              <td>{t.servicio_display}</td>
              <td>
                {t.token_configurado ? (
                  <span className="field">{t.token_preview}</span>
                ) : (
                  <span className="text-muted">Sin generar</span>
                )}
              </td>
              <td className="text-muted">{t.generado_at ? new Date(t.generado_at).toLocaleString("es-AR") : "—"}</td>
              <td>
                <input type="checkbox" checked={t.activo} onChange={() => toggleActivo(t)} />
              </td>
              <td className="table-actions">
                <button className="btn btn-ghost" disabled={generatingId === t.id} onClick={() => generar(t)}>
                  {generatingId === t.id ? "Generando…" : t.token_configurado ? "Regenerar" : "Generar token"}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {nuevoToken && (
        <Modal title={`Token generado — ${nuevoToken.servicio}`} onClose={() => setNuevoToken(null)}>
          <p className="text-muted">
            Copialo y pasáselo a ese microservicio por otro medio — no se guarda en texto plano en ningún
            lado, si cerrás esto sin copiarlo hay que generar uno nuevo.
          </p>
          <div className="temp-password-box">{nuevoToken.token}</div>
          <button className="btn btn-primary" onClick={() => setNuevoToken(null)}>Listo</button>
        </Modal>
      )}
    </div>
  );
}
