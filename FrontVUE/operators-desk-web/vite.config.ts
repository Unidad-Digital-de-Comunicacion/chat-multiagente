import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3001,
    // Igual que en frontend/admin-panel/vite.config.ts: si esto corre
    // detrás de un túnel (Cloudflare u otro), agregar acá el hostname
    // público, o Vite lo va a rechazar con 403 "Blocked request".
    // allowedHosts: ["operadores.udcchat.com.ar"],
    watch: {
      usePolling: true,
      interval: 300,
    },
  },
});
