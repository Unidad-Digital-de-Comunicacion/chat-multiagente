import { type FormEvent, useEffect, useState } from "react";

import { api, ApiError } from "../api/client";
import Modal from "../components/Modal";
import { useAuth } from "../auth/AuthContext";
import { hasPerm } from "../auth/permissions";
import type { Canal, Paginated } from "../types";

export default function ChannelsPage() {
  const { me } = useAuth();
  const canEdit = hasPerm(me, "channels.change_canal");

  const [canales, setCanales] = useState<Canal[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [verifyingId, setVerifyingId] = useState<number | null>(null);
  const [webhookId, setWebhookId] = useState<number | null>(null);

  async function load() {
    try {
      const data = await api.get<Paginated<Canal>>("/api/core/canales/");
      setCanales(data.results);
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 403 ? "No tenés permiso para ver esta sección." : "No se pudo cargar la configuración.",
      );
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function toggleActivo(canal: Canal) {
    try {
      await api.patch(`/api/core/canales/${canal.id}/`, { activo: !canal.activo });
      load();
    } catch (err) {
      alert(err instanceof ApiError && err.data ? JSON.stringify(err.data) : "No se pudo guardar.");
    }
  }

  async function verificar(canal: Canal) {
    setVerifyingId(canal.id);
    try {
      await api.post(`/api/core/canales/${canal.id}/verificar/`);
      load();
    } catch (err) {
      alert(err instanceof ApiError && err.data ? JSON.stringify(err.data) : "No se pudo verificar.");
    } finally {
      setVerifyingId(null);
    }
  }

  if (error) return <div className="empty-state">{error}</div>;
  if (!canales) return <div className="page-loading">Cargando…</div>;

  return (
    <div>
      <div className="page-header">
        <h2>Canales</h2>
      </div>
      <p className="text-muted">
        Api key y estado de cada canal de mensajería. Messenger e Instagram ya tienen conexión real a través de
        Channel Gateway — "Datos del webhook" tiene la URL y el secreto que hay que cargar en la app de Meta para
        que los mensajes entrantes lleguen. WhatsApp todavía no está conectado.
      </p>

      <div className="card">
        <table className="table">
          <thead>
            <tr>
              <th>Canal</th>
              <th>Api key</th>
              <th>Activo</th>
              <th>Salud de la conexión</th>
              {canEdit && <th></th>}
            </tr>
          </thead>
          <tbody>
            {canales.map((c) => (
              <tr key={c.id}>
                <td>{c.tipo_display}</td>
                <td>
                  {c.api_key_configurada ? (
                    <span className="field">{c.api_key_preview}</span>
                  ) : (
                    <span className="text-muted">Sin configurar</span>
                  )}
                </td>
                <td>
                  {canEdit ? (
                    <input type="checkbox" checked={c.activo} onChange={() => toggleActivo(c)} />
                  ) : c.activo ? (
                    "Sí"
                  ) : (
                    "No"
                  )}
                </td>
                <td>
                  <EstadoConexion canal={c} />
                </td>
                {canEdit && (
                  <td className="table-actions">
                    <button className="btn btn-ghost" onClick={() => setEditingId(c.id)}>
                      {c.api_key_configurada ? "Reemplazar api key" : "Cargar api key"}
                    </button>
                    {c.api_key_configurada && (
                      <button
                        className="btn btn-ghost"
                        disabled={verifyingId === c.id}
                        onClick={() => verificar(c)}
                      >
                        {verifyingId === c.id ? "Verificando…" : "Verificar conexión"}
                      </button>
                    )}
                    {c.webhook_url && (
                      <button className="btn btn-ghost" onClick={() => setWebhookId(c.id)}>
                        Datos del webhook
                      </button>
                    )}
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {editingId && (
        <ApiKeyModal
          canal={canales.find((c) => c.id === editingId)!}
          onClose={() => setEditingId(null)}
          onSaved={() => {
            setEditingId(null);
            load();
          }}
        />
      )}
      {webhookId && (
        <WebhookModal
          canal={canales.find((c) => c.id === webhookId)!}
          onClose={() => setWebhookId(null)}
          onRegenerado={() => load()}
        />
      )}
    </div>
  );
}

function EstadoConexion({ canal }: { canal: Canal }) {
  if (!canal.ultimo_chequeo_at) {
    return <span className="text-muted">Todavía no se verificó</span>;
  }
  if (canal.ultimo_chequeo_ok === null) {
    // Webchat: se "verificó" pero no hay servidor externo que consultar.
    return (
      <span className="text-muted" title={canal.ultimo_chequeo_detalle}>
        No aplica
      </span>
    );
  }

  const fecha = new Date(canal.ultimo_chequeo_at).toLocaleString("es-AR");
  return (
    <div>
      <span className={"badge" + (canal.ultimo_chequeo_ok ? "" : " badge-warning")}>
        {canal.ultimo_chequeo_ok ? "Conectado" : "Sin conexión"}
      </span>
      <div className="text-muted small">{fecha}</div>
      <div className="text-muted small">{canal.ultimo_chequeo_detalle}</div>
    </div>
  );
}

function WebhookModal({
  canal, onClose, onRegenerado,
}: {
  canal: Canal;
  onClose: () => void;
  onRegenerado: () => void;
}) {
  const [regenerando, setRegenerando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function copiar(valor: string) {
    try {
      await navigator.clipboard.writeText(valor);
    } catch {
      // Sin acceso al portapapeles (ej. contexto no seguro) — el valor
      // sigue seleccionable a mano en el cuadro de texto, no es fatal.
    }
  }

  async function regenerar() {
    if (!confirm("¿Regenerar el secreto del webhook? El anterior deja de funcionar — hay que volver a pegar el nuevo en la configuración del webhook de Meta.")) return;
    setRegenerando(true);
    setError(null);
    try {
      await api.post(`/api/core/canales/${canal.id}/regenerar-webhook-secret/`);
      onRegenerado();
    } catch {
      setError("No se pudo regenerar.");
    } finally {
      setRegenerando(false);
    }
  }

  return (
    <Modal title={`Webhook — ${canal.tipo_display}`} onClose={onClose}>
      <p className="text-muted">
        Pegar esta URL y este secreto en la configuración del webhook de la app de Meta para este canal —
        Meta manda acá los mensajes entrantes de esta organización puntual.
      </p>
      <div className="form-stack">
        <label>
          URL de entrada
          <div className="temp-password-box">{canal.webhook_url}</div>
        </label>
        <button className="btn btn-outline" type="button" onClick={() => copiar(canal.webhook_url || "")}>
          Copiar URL
        </button>
        <label>
          Secreto (verify token)
          <div className="temp-password-box">{canal.webhook_secret}</div>
        </label>
        <button className="btn btn-outline" type="button" onClick={() => copiar(canal.webhook_secret || "")}>
          Copiar secreto
        </button>
        {error && <div className="form-error">{error}</div>}
        <button className="btn btn-ghost btn-danger" type="button" disabled={regenerando} onClick={regenerar}>
          {regenerando ? "Regenerando…" : "Regenerar secreto"}
        </button>
      </div>
    </Modal>
  );
}

function ApiKeyModal({
  canal, onClose, onSaved,
}: {
  canal: Canal;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [apiKey, setApiKey] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await api.patch(`/api/core/canales/${canal.id}/`, { api_key: apiKey });
      onSaved();
    } catch (err) {
      if (err instanceof ApiError && err.data && typeof err.data === "object") {
        setError(Object.values(err.data as Record<string, string[]>).flat().join(" "));
      } else {
        setError("No se pudo guardar.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal title={`Api key — ${canal.tipo_display}`} onClose={onClose}>
      <form onSubmit={handleSubmit} className="form-stack">
        {canal.api_key_configurada && (
          <p className="text-muted">
            Ya hay una cargada (<span className="field">{canal.api_key_preview}</span>). Escribir una nueva la
            reemplaza — no se puede volver a ver la anterior.
          </p>
        )}
        <label>
          Api key nueva
          <input
            required
            autoFocus
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="Pegar la api key del canal"
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
