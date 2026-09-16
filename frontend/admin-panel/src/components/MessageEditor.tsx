import { useEffect, useRef, useState } from "react";

// Barra de formato + emojis para los campos de mensaje del bot — mismo
// concepto que `chatbot/static/js/chatbot_wa_editor.js` del repo
// garzamorada/chatbot, reimplementado como componente de React. La sintaxis
// que insertan los botones es el marcado NEUTRO del proyecto
// (**negrita**/_cursiva_/~tachado~/`monoespaciado`, sección 4.1.2 de
// docs/CONTEXTO_PROYECTO.md) — cada canal la traduce a la suya (WhatsApp usa
// un solo asterisco, por ejemplo), no la sintaxis literal de WhatsApp.
const EMOJIS = [
  "✅", "❌", "⚠️", "ℹ️", "❓", "❗",
  "🙏", "👍", "👎", "👋", "💪", "🙌", "👏", "☝️", "👌", "🤝",
  "⏰", "📅", "📍", "📌",
  "💬", "📞", "📱", "✉️", "📧", "🔗", "📎", "📄", "📷",
  "🏢", "🏠", "💼", "💰", "💳", "🛒", "🚗", "✈️", "🏖️",
  "🧒", "🧓", "🎒", "✏️", "📚",
  "🎉", "🎁", "⭐", "🔥", "❤️", "💙",
];

export default function MessageEditor({
  value, onChange, rows = 3, disabled, placeholder, maxLength, variables = [],
}: {
  value: string;
  onChange: (value: string) => void;
  rows?: number;
  disabled?: boolean;
  placeholder?: string;
  maxLength?: number;
  variables?: string[];
}) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const [showEmojis, setShowEmojis] = useState(false);

  useEffect(() => {
    function onDocClick(e: MouseEvent) {
      // SAFETY: `e.target` de un evento DOM real siempre es un Node —
      // `MouseEvent` sólo lo tipa como `EventTarget` porque también acepta
      // targets sintéticos que no lo son.
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setShowEmojis(false);
    }

    document.addEventListener("mousedown", onDocClick);

    return () => document.removeEventListener("mousedown", onDocClick);
  }, []);

  function wrapSelection(before: string, after: string) {
    const el = textareaRef.current;

    if (!el || disabled) return;
    const start = el.selectionStart;
    const end = el.selectionEnd;
    const selected = value.slice(start, end) || "texto";
    const next = value.slice(0, start) + before + selected + after + value.slice(end);
    onChange(next);
    const cursorStart = start + before.length;
    requestAnimationFrame(() => {
      el.focus();
      el.setSelectionRange(cursorStart, cursorStart + selected.length);
    });
  }

  function insertAtCursor(text: string) {
    const el = textareaRef.current;

    if (!el || disabled) return;
    const start = el.selectionStart;
    const end = el.selectionEnd;
    const next = value.slice(0, start) + text + value.slice(end);
    onChange(next);
    const pos = start + text.length;
    requestAnimationFrame(() => {
      el.focus();
      el.setSelectionRange(pos, pos);
    });
  }

  return (
    <div className="msg-editor" ref={wrapRef}>
      <div className="msg-editor-toolbar">
        <button type="button" className="btn-toolbar" disabled={disabled} title="Negrita" onClick={() => wrapSelection("**", "**")}>
          <strong>N</strong>
        </button>
        <button type="button" className="btn-toolbar" disabled={disabled} title="Itálica" onClick={() => wrapSelection("_", "_")}>
          <em>I</em>
        </button>
        <button type="button" className="btn-toolbar" disabled={disabled} title="Tachado" onClick={() => wrapSelection("~", "~")}>
          <s>T</s>
        </button>
        <button type="button" className="btn-toolbar" disabled={disabled} title="Monoespaciado" onClick={() => wrapSelection("`", "`")}>
          {"</>"}
        </button>
        <div className="msg-editor-emoji-wrap">
          <button
            type="button"
            className="btn-toolbar"
            disabled={disabled}
            title="Insertar emoji"
            onClick={() => setShowEmojis((s) => !s)}
          >
            🙂
          </button>
          {showEmojis && (
            <div className="msg-editor-emoji-menu">
              {EMOJIS.map((emoji) => (
                <button
                  key={emoji}
                  type="button"
                  className="msg-editor-emoji-btn"
                  onClick={() => {
                    insertAtCursor(emoji);
                    setShowEmojis(false);
                  }}
                >
                  {emoji}
                </button>
              ))}
            </div>
          )}
        </div>
        {variables.length > 0 && (
          <>
            <span className="msg-editor-sep" />
            {variables.map((v) => (
              <button
                key={v}
                type="button"
                className="btn-toolbar btn-toolbar-var"
                disabled={disabled}
                title={`Insertar {${v}}`}
                onClick={() => insertAtCursor(`{${v}}`)}
              >
                {`{${v}}`}
              </button>
            ))}
          </>
        )}
      </div>
      <textarea
        ref={textareaRef}
        rows={rows}
        disabled={disabled}
        placeholder={placeholder}
        maxLength={maxLength}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
      <div className="msg-editor-hint text-muted">
        Formato: <code>**negrita**</code>, <code>_cursiva_</code>, <code>~tachado~</code>, <code>`monoespaciado`</code>. Cada
        canal (WhatsApp, Telegram, etc.) lo traduce a su sintaxis real al enviarlo.
      </div>
    </div>
  );
}
