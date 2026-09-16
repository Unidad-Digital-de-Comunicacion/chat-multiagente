import type { ReactNode } from "react";

// Vista previa "estilo chat de WhatsApp" — es el canal real al que apunta
// el proyecto (sección 4.1.1/4.1.2 de docs/CONTEXTO_PROYECTO.md: los menús
// se mandan como lista/botones interactivos y el texto lleva el marcado
// neutro **negrita**/_cursiva_/~tachado~/`monoespaciado` que cada canal
// traduce a su sintaxis). Es un mockup genérico (marco de teléfono + burbujas
// de chat), no un componente ni asset de WhatsApp.

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

/** Convierte el marcado neutro (**negrita**, _cursiva_, ~tachado~,
 * `monoespaciado`) a elementos de React, respetando saltos de línea. */
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

export function aplicarVariables(texto: string, vars: { area?: string; nombre?: string } = {}): string {
  return (texto || "").replace("{area}", vars.area ?? "").replace("{nombre}", vars.nombre ?? "");
}

export function PhoneFrame({ title, children }: { title?: string; children: ReactNode }) {
  return (
    <div className="phone-frame">
      <div className="phone-header">{title ?? "Vista previa"}</div>
      <div className="phone-screen">{children}</div>
    </div>
  );
}

export function BotBubble({ children, caption }: { children: ReactNode; caption?: string }) {
  return (
    <div className="wa-bubble-wrap">
      {caption && <div className="wa-bubble-caption">{caption}</div>}
      <div className="wa-bubble wa-bubble-bot">{children}</div>
    </div>
  );
}

export function Pill({ children }: { children: ReactNode }) {
  return <div className="wa-pill">{children}</div>;
}

export function OptionRow({
  index, children, onClick, muted,
}: {
  index: number | string;
  children: ReactNode;
  onClick?: () => void;
  muted?: boolean;
}) {
  return (
    <button type="button" className={"wa-option-row" + (muted ? " wa-option-row-muted" : "")} onClick={onClick} disabled={!onClick}>
      <span className="wa-option-index">{index}</span>
      <span>{children}</span>
    </button>
  );
}

export function BackRow({ onClick }: { onClick: () => void }) {
  return (
    <button type="button" className="wa-back-row" onClick={onClick}>
      ‹ Volver al menú anterior
    </button>
  );
}
