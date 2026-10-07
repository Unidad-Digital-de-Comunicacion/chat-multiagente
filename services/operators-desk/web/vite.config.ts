import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3001,
    // El subdominio público del túnel de Cloudflare que apunta a este
    // servicio (docker-compose.yml, servicio `cloudflared`) — sin esto,
    // Vite rechaza con 403 "Blocked request" cualquier request cuyo header
    // Host no sea localhost, así llegue detrás de un túnel HTTPS legítimo
    // o no. Mismo criterio que frontend/admin-panel/vite.config.ts.
    allowedHosts: ["operadores.udcchat.com.ar"],
    watch: {
      usePolling: true,
      interval: 300,
    },
  },
});
