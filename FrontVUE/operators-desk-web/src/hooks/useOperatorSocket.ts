import { useEffect, useRef } from "react";

import { api, getAccessToken, operatorSocketUrl } from "../api/client";
import type { EventoOperador } from "../types";

// Implementa §7.1/§7.3 del contrato de API:
// - Conecta a WS /ws/operador/{token} con el `access` actual.
// - Si el servidor cierra con 4401 (token vencido), intenta refrescar y
//   reconectar antes de rendirse.
// - Backoff exponencial (tope 30s) si se corta por cualquier otro motivo —
//   "no hay reconexión automática del lado del servidor", así que la hace
//   el cliente.
// - Es sólo una optimización ("enterate antes"): quien use este hook debe
//   seguir teniendo su propio polling de respaldo, este hook no lo
//   reemplaza.
//
// TODO para el equipo: esto no está probado contra un Conversation Engine
// real todavía (no tuve forma de levantar el backend desde donde armé
// esto) — probarlo en serio contra §5 de
// docs/requerimientos-operators-desk-web.md antes de confiar en que
// funciona tal cual.
export function useOperatorSocket(onEvento: (evento: EventoOperador) => void) {
  const onEventoRef = useRef(onEvento);
  onEventoRef.current = onEvento;

  useEffect(() => {
    let socket: WebSocket | null = null;
    let cerradoPorNosotros = false;
    let intentos = 0;
    let timeoutId: ReturnType<typeof setTimeout> | null = null;

    async function conectar() {
      const token = getAccessToken();

      if (!token) return;

      socket = new WebSocket(operatorSocketUrl(token));

      socket.onmessage = (ev) => {
        try {
          const data = JSON.parse(ev.data) as EventoOperador;
          onEventoRef.current(data);
        } catch {
          // Evento con forma inesperada — lo ignoramos en vez de romper la
          // pantalla; el polling de respaldo sigue trayendo lo mismo igual.
        }
      };

      socket.onopen = () => {
        intentos = 0;
      };

      socket.onclose = async (ev) => {
        if (cerradoPorNosotros) return;

        // 4401 = token inválido/vencido (§7.1). Intentar refrescar antes de
        // reintentar con backoff normal.
        if (ev.code === 4401) {
          try {
            await api.post("/api/auth/refresh/", {});
          } catch {
            // Si el refresh también falló, el próximo intento de conectar
            // va a volver a fallar y vamos a seguir reintentando con
            // backoff igual — eventualmente el resto de la app (ProtectedRoute)
            // se entera por un 401 en algún GET y manda a /login.
          }
        }

        intentos += 1;
        const espera = Math.min(30000, 1000 * 2 ** intentos);
        timeoutId = setTimeout(conectar, espera);
      };
    }

    conectar();

    return () => {
      cerradoPorNosotros = true;
      if (timeoutId) clearTimeout(timeoutId);
      socket?.close();
    };
  }, []);
}
