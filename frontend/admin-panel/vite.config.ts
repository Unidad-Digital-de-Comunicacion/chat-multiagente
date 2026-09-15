import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    // El subdominio público del túnel de Cloudflare que apunta a este
    // servicio (docker-compose.yml, servicio `cloudflared`) — sin esto,
    // Vite rechaza con 403 "Blocked request" cualquier request cuyo header
    // Host no sea localhost, así llegue detrás de un túnel HTTPS legítimo
    // o no.
    allowedHosts: ["admin.udcchat.com.ar"],
    // Docker Desktop en Windows no siempre propaga los eventos de
    // filesystem del bind mount (`docker-compose.override.yml` monta
    // `./frontend/admin-panel:/app`) al watcher nativo de Vite (chokidar) —
    // sin esto, Vite se queda sirviendo el bundle viejo después de guardar
    // un cambio hasta reiniciar el contenedor a mano, sin ningún error
    // visible que lo delate.
    watch: {
      usePolling: true,
      interval: 300,
    },
  },
});
