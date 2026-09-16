import { type FormEvent, useEffect, useState } from "react";

import { api, ApiError, extraerMensajeDeError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { hasPerm } from "../auth/permissions";
import MessageEditor from "../components/MessageEditor";
import { aplicarVariables, BotBubble, Pill, PhoneFrame, renderMarkup } from "../components/WhatsAppPreview";
import type { BotMessages } from "../types";

interface Campo {
  name: keyof BotMessages;
  label: string;
  help: string;
  multiline?: boolean;
  variables?: string[];
}

// Se usan siempre, tenga el menú activado o no — el mensaje de bienvenida se manda antes de que la
// conversación quede libre para operadores y el de despedida al cerrarla, con o sin árbol de menú
// en el medio.
const CAMPOS_SIEMPRE: Campo[] = [
  {
    name: "mensaje_bienvenida",
    label: "Mensaje de bienvenida (primer contacto)",
    help: "Se manda una sola vez, la primera vez que el contacto escribe — antes del menú, o si el " +
      "menú está desactivado, antes de que la conversación quede libre para que la tome un operador.",
    multiline: true,
    variables: ["nombre"],
  },
  {
    name: "mensaje_despedida",
    label: "Mensaje de despedida",
    help: 'Lo manda cualquier opción de tipo "Terminar" del árbol de menú, o el cierre de la ' +
      "conversación si el menú está desactivado.",
    multiline: true,
    variables: ["nombre"],
  },
  {
    name: "mensaje_operador_toma",
    label: "Saludo del operador al tomar la conversación",
    help: 'Se le sugiere al operador al marcar una conversación como "tomada". Acá {nombre} es el '
      + "nombre del OPERADOR, no el del contacto (a diferencia de los demás campos). Es sólo "
      + "configuración por ahora: aplicarlo de verdad es parte del Operators Desk (Fase 4/5).",
    multiline: true,
    variables: ["nombre"],
  },
];

// Sólo se usan con el árbol de menú activado.
const CAMPOS_MENU: Campo[] = [
  {
    name: "saludo_inicial",
    label: "Saludo del menú principal",
    help: "Encabezado del menú principal, antes del listado de opciones.",
    multiline: true,
    variables: ["nombre"],
  },
  {
    name: "saludo_area",
    label: "Saludo de cada menú",
    help: "Encabezado al entrar a un submenú.",
    multiline: true,
    variables: ["area", "nombre"],
  },
  {
    name: "derivacion_texto",
    label: 'Texto de la opción "Hablar con un operador"',
    help: "Cómo aparece la opción en el listado. Máx. 24 caracteres (límite de WhatsApp).",
  },
  {
    name: "derivacion_mensaje",
    label: "Mensaje al derivar a un operador",
    help: "Texto que recibe el contacto al pedir un operador.",
    multiline: true,
    variables: ["area", "nombre"],
  },
  {
    name: "mensaje_cierre_inactividad",
    label: "Mensaje de cierre por inactividad",
    help: "Se manda al cerrar automáticamente una conversación inactiva.",
    multiline: true,
    variables: ["nombre"],
  },
];

const EJEMPLO = { area: "Ventas", nombre: "Juan" };

const EJEMPLO_OPERADOR = { nombre: "Marina (operadora)" };

function CampoInput({
  campo, mensajes, canEdit, onChange,
}: {
  campo: Campo;
  mensajes: BotMessages;
  canEdit: boolean;
  onChange: (name: keyof BotMessages, value: string) => void;
}) {
  return (
    <label>
      {campo.label}
      {campo.multiline ? (
        <MessageEditor
          rows={3}
          disabled={!canEdit}
          value={String(mensajes[campo.name] ?? "")}
          placeholder={mensajes.valores_efectivos[campo.name] ?? ""}
          variables={campo.variables ?? []}
          onChange={(v) => onChange(campo.name, v)}
        />
      ) : (
        <input
          maxLength={campo.name === "derivacion_texto" ? 24 : undefined}
          disabled={!canEdit}
          value={String(mensajes[campo.name] ?? "")}
          placeholder={mensajes.valores_efectivos[campo.name] ?? ""}
          onChange={(e) => onChange(campo.name, e.target.value)}
        />
      )}
      <span className="text-muted field-help">{campo.help}</span>
    </label>
  );
}

export default function BotMessagesPage() {
  const { me } = useAuth();
  const canEdit = hasPerm(me, "bot_settings.change_botmessages");
  const canView = hasPerm(me, "bot_settings.view_botmessages");

  const [mensajes, setMensajes] = useState<BotMessages | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState<number | null>(null);

  async function load() {
    try {
      const data = await api.get<BotMessages>("/api/core/mensajes-bot/");
      setMensajes(data);
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 403
          ? "No tenés permiso para ver esta sección."
          : "No se pudo cargar la configuración.",
      );
    }
  }

  useEffect(() => {
    if (canView) load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function setCampo(name: keyof BotMessages, value: string | number | boolean) {
    setMensajes((prev) => prev && { ...prev, [name]: value });
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();

    if (!mensajes) return;
    setError(null);
    setSaving(true);

    try {
      const body = {
        menu_activo: mensajes.menu_activo,
        mensaje_bienvenida: mensajes.mensaje_bienvenida,
        saludo_inicial: mensajes.saludo_inicial,
        saludo_area: mensajes.saludo_area,
        mensaje_despedida: mensajes.mensaje_despedida,
        derivacion_texto: mensajes.derivacion_texto,
        derivacion_mensaje: mensajes.derivacion_mensaje,
        mensaje_cierre_inactividad: mensajes.mensaje_cierre_inactividad,
        mensaje_operador_toma: mensajes.mensaje_operador_toma,
        minutos_inactividad_cierre: mensajes.minutos_inactividad_cierre,
        segundos_remostrar_menu: mensajes.segundos_remostrar_menu,
      };

      const data = await api.patch<BotMessages>("/api/core/mensajes-bot/", body);
      setMensajes(data);
      setSavedAt(Date.now());
    } catch (err) {
      setError(extraerMensajeDeError(err) ?? "No se pudo guardar.");
    } finally {
      setSaving(false);
    }
  }

  if (error) return <div className="empty-state">{error}</div>;

  if (!mensajes) return <div className="page-loading">Cargando…</div>;

  function efectivo(campo: keyof BotMessages): string {
    const valor = String(mensajes![campo] ?? "").trim();

    return valor || mensajes!.valores_efectivos[campo] || "";
  }

  return (
    <div>
      <div className="page-header">
        <h2>Mensajes predeterminados</h2>
      </div>
      <p className="text-muted">
        Textos que usa el bot para cada sección o acción de la conversación. Un campo vacío usa el valor por
        defecto (se muestra como placeholder). La vista previa de la derecha se actualiza mientras escribís.
      </p>

      <div className="messages-layout">
        <form onSubmit={handleSubmit} className="form-stack card messages-main">
          <div>
            <div className="field-label">Modo de atención</div>
            <div className="button-group">
              <button
                type="button"
                disabled={!canEdit}
                className={"btn-toggle" + (mensajes.menu_activo ? " btn-toggle-active" : "")}
                onClick={() => setCampo("menu_activo", true)}
              >
                Usar menú del bot
              </button>
              <button
                type="button"
                disabled={!canEdit}
                className={"btn-toggle" + (!mensajes.menu_activo ? " btn-toggle-active" : "")}
                onClick={() => setCampo("menu_activo", false)}
              >
                Directo a operadores
              </button>
            </div>
            <span className="text-muted field-help">
              {mensajes.menu_activo
                ? "El bot saluda, muestra el menú y deriva según la opción elegida — los mensajes de abajo se " +
                  "usan en cada paso."
                : "El bot no muestra el árbol de menú: sólo manda la bienvenida y, entre ella y la despedida, " +
                  "la conversación queda directamente en la bandeja sin asignar para que cualquier operador la " +
                  "tome, sin pasar antes por una derivación."}
              {" "}La bienvenida, la despedida y el saludo del operador se usan siempre, con o sin menú.
            </span>
          </div>

          {CAMPOS_SIEMPRE.map((campo) => (
            <CampoInput key={campo.name} campo={campo} mensajes={mensajes} canEdit={canEdit} onChange={setCampo} />
          ))}

          <div>
            <div className="field-label">Sólo con el menú activado</div>
            <div className={mensajes.menu_activo ? undefined : "messages-fields-inactive"}>
              {CAMPOS_MENU.map((campo) => (
                <CampoInput key={campo.name} campo={campo} mensajes={mensajes} canEdit={canEdit} onChange={setCampo} />
              ))}
            </div>
          </div>

          <label>
            Segundos para volver a mostrar el menú tras una respuesta
            <input
              type="number"
              min={0}
              disabled={!canEdit}
              value={mensajes.segundos_remostrar_menu}
              onChange={(e) => setCampo("segundos_remostrar_menu", Number(e.target.value))}
            />
            <span className="text-muted field-help">0 = desactivado.</span>
          </label>

          <label>
            Minutos de inactividad para cerrar la conversación
            <input
              type="number"
              min={0}
              disabled={!canEdit}
              value={mensajes.minutos_inactividad_cierre}
              onChange={(e) => setCampo("minutos_inactividad_cierre", Number(e.target.value))}
            />
            <span className="text-muted field-help">0 = nunca cierra por inactividad.</span>
          </label>

          {error && <div className="form-error">{error}</div>}
          {canEdit && (
            <div className="toolbar">
              <button className="btn btn-primary" type="submit" disabled={saving}>
                {saving ? "Guardando…" : "Guardar"}
              </button>
              {savedAt && Date.now() - savedAt < 4000 && <span className="text-muted">Guardado.</span>}
            </div>
          )}
        </form>

        <aside className="messages-side">
          <PhoneFrame title="Vista previa">
            <BotBubble caption="Primer contacto">{renderMarkup(efectivo("mensaje_bienvenida"))}</BotBubble>
            {mensajes.menu_activo ? (
              <>
                <BotBubble caption="Menú principal">{renderMarkup(efectivo("saludo_inicial"))}</BotBubble>
                <BotBubble caption='Al entrar a un submenú (ej. "Ventas")'>
                  {renderMarkup(aplicarVariables(efectivo("saludo_area"), EJEMPLO))}
                </BotBubble>
                <BotBubble caption="Al pedir un operador">
                  {renderMarkup(aplicarVariables(efectivo("derivacion_mensaje"), EJEMPLO))}
                </BotBubble>
                {mensajes.derivacion_texto && <Pill>{mensajes.derivacion_texto || "Hablar con un operador"}</Pill>}
                {mensajes.minutos_inactividad_cierre > 0 ? (
                  <BotBubble caption={`Si no escribe por ${mensajes.minutos_inactividad_cierre} min`}>
                    {renderMarkup(efectivo("mensaje_cierre_inactividad"))}
                  </BotBubble>
                ) : (
                  <div className="wa-bubble-caption">Cierre por inactividad: desactivado</div>
                )}
              </>
            ) : (
              <div className="wa-bubble-caption">
                Estado intermedio: sin menú, la conversación queda directo en la bandeja sin asignar para que
                cualquier operador la tome, sin pasar antes por una derivación.
              </div>
            )}
            <BotBubble caption='Al tomar la conversación (lo escribe el operador, no el bot)'>
              {renderMarkup(aplicarVariables(efectivo("mensaje_operador_toma"), EJEMPLO_OPERADOR))}
            </BotBubble>
            <BotBubble caption="Al terminar la conversación">
              {renderMarkup(efectivo("mensaje_despedida"))}
            </BotBubble>
          </PhoneFrame>
        </aside>
      </div>
    </div>
  );
}
