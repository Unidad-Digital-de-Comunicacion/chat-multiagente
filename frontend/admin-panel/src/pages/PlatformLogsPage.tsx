import { useState } from "react";

import LogTimeline from "../components/LogTimeline";

const RANGOS = [
  { minutos: 15, label: "Últimos 15 min" },
  { minutos: 60, label: "Última hora" },
  { minutos: 6 * 60, label: "Últimas 6 horas" },
  { minutos: 24 * 60, label: "Último día" },
];

/** `datetime-local` trabaja en hora local del navegador, sin zona. */
function aInputLocal(fecha: Date): string {
  const local = new Date(fecha.getTime() - fecha.getTimezoneOffset() * 60_000);

  return local.toISOString().slice(0, 16);
}

export default function PlatformLogsPage() {
  const [hasta, setHasta] = useState(() => new Date());
  const [desde, setDesde] = useState(() => new Date(Date.now() - 60 * 60_000));
  const [requestId, setRequestId] = useState("");
  const [requestIdInput, setRequestIdInput] = useState("");

  const aplicarRango = (minutos: number) => {
    const ahora = new Date();

    setHasta(ahora);
    setDesde(new Date(ahora.getTime() - minutos * 60_000));
  };

  return (
    <div>
      <div className="page-header">
        <h2>Logs</h2>
      </div>
      <p className="text-muted">
        Logs de todos los servicios mezclados en orden cronológico. Click en un request_id para seguir ese pedido de
        punta a punta (Cloudflare → Core → Channel Gateway / Conversation Engine / Webchat).
      </p>

      <div className="toolbar">
        {RANGOS.map((r) => (
          <button key={r.minutos} type="button" className="btn btn-outline btn-sm" onClick={() => aplicarRango(r.minutos)}>
            {r.label}
          </button>
        ))}
        <label className="small">
          Desde{" "}
          <input
            type="datetime-local"
            value={aInputLocal(desde)}
            onChange={(e) => e.target.value && setDesde(new Date(e.target.value))}
          />
        </label>
        <label className="small">
          Hasta{" "}
          <input
            type="datetime-local"
            value={aInputLocal(hasta)}
            onChange={(e) => e.target.value && setHasta(new Date(e.target.value))}
          />
        </label>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            setRequestId(requestIdInput.trim());
          }}
        >
          <input
            placeholder="request_id"
            value={requestIdInput}
            onChange={(e) => setRequestIdInput(e.target.value)}
            aria-label="Filtrar por request_id"
          />{" "}
          <button type="submit" className="btn btn-outline btn-sm">
            Seguir pedido
          </button>
        </form>
      </div>

      <LogTimeline
        desde={desde.toISOString()}
        hasta={hasta.toISOString()}
        requestId={requestId}
        onRequestId={(rid) => {
          setRequestId(rid);
          setRequestIdInput(rid);
        }}
      />
    </div>
  );
}
