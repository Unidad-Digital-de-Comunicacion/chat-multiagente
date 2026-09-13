import { Component, type ErrorInfo, type ReactNode } from "react";

/** Sin esto, un error de render sin atrapar en cualquier parte del árbol
 * (ej. `groups.map is not a function` de esta semana) deja `#root` vacío y
 * sin ningún indicio en pantalla de qué pasó — sólo se ve en la consola del
 * navegador. Envuelve toda la app (`main.tsx`) para mostrar al menos un
 * mensaje legible con el error, en vez de una pantalla en blanco. */
export default class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state: { error: Error | null } = { error: null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("ErrorBoundary atrapó un error de render:", error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div style={{ padding: "2rem", maxWidth: 640, margin: "0 auto", fontFamily: "sans-serif" }}>
          <h2>Algo se rompió</h2>
          <p style={{ color: "#6b7280" }}>
            Hubo un error inesperado en esta pantalla. Recargá la página; si sigue pasando, avisá con el detalle
            de abajo (también queda en la consola del navegador, F12 → Console).
          </p>
          <pre style={{ background: "#f4f5f7", padding: "1rem", borderRadius: 8, overflow: "auto", fontSize: "0.85rem" }}>
            {this.state.error.message}
          </pre>
          <button
            onClick={() => window.location.reload()}
            style={{ padding: "0.5rem 1rem", cursor: "pointer" }}
          >
            Recargar
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
