import type { ReactNode } from "react";

// Basado en frontend/admin-panel/src/components/WhatsAppPreview.tsx
// (`renderMarkup`) — acá sólo se necesita la función de render, no el
// mockup de teléfono del Admin Panel (eso es para previsualizar el mensaje
// del bot antes de guardarlo; acá estamos mostrando el hilo real ya
// enviado). Traduce el marcado neutro del proyecto (sección 4.1.2 de
// docs/CONTEXTO_PROYECTO.md) a elementos de React.

const MARKUP_RE = /\*\*(.+?)\*\*|_(.+?)_|~(.+?)~|`(.+?)`/g;

function renderLine(line: string, keyPrefix: string): ReactNode[] {
  const parts: ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  let i = 0;
  MARKUP_RE.lastIndex = 0;

  while ((match = MARKUP_RE.exec(line))) {
    if (match.index > lastIndex) parts.push(line.slice(lastIndex, match.index));
    const key = `${keyPrefix}-${i++}`;

    if (match[1] !== undefined) parts.push(<strong key={key}>{match[1]}</strong>);
    else if (match[2] !== undefined) parts.push(<em key={key}>{match[2]}</em>);
    else if (match[3] !== undefined) parts.push(<s key={key}>{match[3]}</s>);
    else if (match[4] !== undefined) parts.push(<code key={key}>{match[4]}</code>);
    lastIndex = MARKUP_RE.lastIndex;
  }

  if (lastIndex < line.length) parts.push(line.slice(lastIndex));

  return parts;
}

export function renderMarkup(texto: string): ReactNode {
  if (!texto) return null;
  const lineas = texto.split("\n");

  return lineas.map((linea, i) => (
    <span key={i}>
      {renderLine(linea, String(i))}
      {i < lineas.length - 1 && <br />}
    </span>
  ));
}
