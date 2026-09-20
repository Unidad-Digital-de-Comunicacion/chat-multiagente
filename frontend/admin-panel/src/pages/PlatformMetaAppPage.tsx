import { type FormEvent, useEffect, useState } from "react";

import { api, ApiError, extraerMensajeDeError } from "../api/client";
import Modal from "../components/Modal";
import type { MetaAppConfig } from "../types";
import { formatearFecha } from "../utils/fecha";

export default function PlatformMetaAppPage() {
  const [config, setConfig] = useState<MetaAppConfig | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editando, setEditando] = useState(false);
  const [visible, setVisible] = useState(false);

  async function load() {
    try {
      const data = await api.get<MetaAppConfig>("/api/core/plataforma/meta-app/");
      setConfig(data);
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 403
          ? "Esta sección es sólo para el superusuario de plataforma."
          : "No se pudo cargar la configuración.",
      );
    }
  }

  useEffect(() => {
    load();
  }, []);

  if (error) return <div className="empty-state">{error}</div>;

  if (!config) return <div className="page-loading">Cargando…</div>;

  return (
    <div>
      <div className="page-header">
        <h2>App de Meta</h2>
      </div>
      <p className="text-muted">
        ID y secreto de la app de Meta (Facebook Developers) que usa toda la plataforma para WhatsApp,
        Messenger e Instagram — una sola app para todas las organizaciones, no una por canal (eso es la api
        key de cada canal, en "Canales"). Se usa para verificar la firma de cada webhook entrante y para
        validar que un token de canal sigue vivo.
      </p>

      <div className="card">
        <div className="form-stack">
          <label>
            <span className="field-label-sm">App ID</span>
            {config.app_id ? <span className="field">{config.app_id}</span> : <span className="text-muted">Sin configurar</span>}
          </label>
          <label>
            <span className="field-label-sm">App Secret</span>
            {config.app_secret_configurada ? (
              <div>
                <div className="temp-password-box">{visible ? config.app_secret_valor : config.app_secret_preview}</div>
                <button className="btn btn-ghost" type="button" onClick={() => setVisible((v) => !v)}>
                  {visible ? "Ocultar" : "Mostrar"}
                </button>
              </div>
            ) : (
              <span className="text-muted">Sin configurar</span>
            )}
          </label>
          <div className="text-muted small">Última actualización: {formatearFecha(config.updated_at)}</div>
          <button className="btn btn-primary" type="button" onClick={() => setEditando(true)}>
            {config.app_id || config.app_secret_configurada ? "Editar" : "Cargar"}
          </button>
        </div>
      </div>

      {editando && (
        <EditarModal
          config={config}
          onClose={() => setEditando(false)}
          onSaved={() => {
            setEditando(false);
            load();
          }}
        />
      )}
    </div>
  );
}

function EditarModal({
  config, onClose, onSaved,
}: {
  config: MetaAppConfig;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [appId, setAppId] = useState(config.app_id);
  const [appSecret, setAppSecret] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);

    try {
      const body: { app_id: string; app_secret?: string } = { app_id: appId };

      if (appSecret) body.app_secret = appSecret;
      await api.patch("/api/core/plataforma/meta-app/", body);
      onSaved();
    } catch (err) {
      setError(extraerMensajeDeError(err) ?? "No se pudo guardar.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal title="App de Meta" onClose={onClose}>
      <form onSubmit={handleSubmit} className="form-stack">
        <label>
          App ID
          <input
            required
            autoFocus
            type="text"
            value={appId}
            onChange={(e) => setAppId(e.target.value)}
            placeholder="El ID de la app en Meta Developers"
          />
        </label>
        <label>
          App Secret {config.app_secret_configurada && "nuevo"}
          <input
            type="text"
            value={appSecret}
            onChange={(e) => setAppSecret(e.target.value)}
            placeholder={config.app_secret_configurada ? "Dejar vacío para no cambiarlo" : "El App Secret de Meta Developers"}
          />
        </label>
        {error && <div className="form-error">{error}</div>}
        <button className="btn btn-primary" type="submit" disabled={submitting}>
          {submitting ? "Guardando…" : "Guardar"}
        </button>
      </form>
    </Modal>
  );
}
