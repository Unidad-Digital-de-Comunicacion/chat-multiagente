import { type ChangeEvent, type FormEvent, useEffect, useState } from "react";

import { api, ApiError, extraerMensajeDeError } from "../api/client";
import Modal from "../components/Modal";
import { useAuth } from "../auth/AuthContext";
import { hasPerm } from "../auth/permissions";
import MessageEditor from "../components/MessageEditor";
import {
  aplicarVariables, BackRow, BotBubble, OptionRow, PhoneFrame, renderMarkup,
} from "../components/WhatsAppPreview";
import {
  MENU_TIPO_LABELS, type BotMessages, type MenuOpcionTreeNode, type MenuTipo, type Paginated, type Team,
} from "../types";

const TIPO_ICONO: Record<MenuTipo, string> = {
  SUBMENU: "📁",
  RESPUESTA: "💬",
  DERIVACION: "👤",
  VOLVER: "↩️",
  INICIO: "🏠",
  TERMINAR: "🏁",
};

// Árbol de menú con reordenamiento/reparentado por drag-and-drop — mismo
// concepto que el editor visual portado de
// chatbot/static/js/chatbot_menu.js y chatbot/templates/chatbot/_menu_tree.html,
// adaptado a esta arquitectura (React + API REST en vez de vistas/templates
// Django con recarga de página).
export default function MenuPage() {
  const { me } = useAuth();
  const canCreate = hasPerm(me, "menu.add_menuopcion");
  const canEdit = hasPerm(me, "menu.change_menuopcion");
  const canDelete = hasPerm(me, "menu.delete_menuopcion");

  const [tree, setTree] = useState<MenuOpcionTreeNode[] | null>(null);
  const [teams, setTeams] = useState<Team[]>([]);
  const [botMessages, setBotMessages] = useState<BotMessages | null>(null);
  const [collapsed, setCollapsed] = useState<Set<number>>(new Set());
  const [draggedId, setDraggedId] = useState<number | null>(null);
  const [formState, setFormState] = useState<{ parentId: number | null; node?: MenuOpcionTreeNode } | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function loadTree() {
    const data = await api.get<MenuOpcionTreeNode[]>("/api/core/menu-opciones/tree/");
    setTree(data);
  }

  async function loadTeams() {
    const data = await api.get<Paginated<Team>>("/api/core/teams/");
    setTeams(data.results);
  }

  async function loadBotMessages() {
    try {
      const data = await api.get<BotMessages>("/api/core/mensajes-bot/");
      setBotMessages(data);
    } catch {
      setBotMessages(null); // sin permiso para verlos: la vista previa usa los defaults genéricos
    }
  }

  useEffect(() => {
    loadTree();
    loadTeams();
    loadBotMessages();
  }, []);

  function toggleCollapse(id: number) {
    setCollapsed((prev) => {
      const next = new Set(prev);

      if (next.has(id)) next.delete(id);
      else next.add(id);

      return next;
    });
  }

  async function reordenar(parentId: number | null, orden: number[]) {
    setError(null);

    try {
      await api.post("/api/core/menu-opciones/reordenar/", { parent_id: parentId, orden });
      await loadTree();
    } catch (err) {
      setError(err instanceof ApiError && err.data ? JSON.stringify(err.data) : "No se pudo mover la opción.");
    }
  }

  async function eliminar(node: MenuOpcionTreeNode) {
    if (!confirm(`¿Eliminar "${node.texto}"? Si tiene opciones adentro, también se eliminan.`)) return;
    await api.delete(`/api/core/menu-opciones/${node.id}/`);
    await loadTree();
  }

  if (!tree) return <div className="page-loading">Cargando…</div>;

  return (
    <div>
      <div className="page-header">
        <h2>Menú</h2>
        {canCreate && (
          <button className="btn btn-primary" onClick={() => setFormState({ parentId: null })}>
            + Agregar opción
          </button>
        )}
      </div>
      <p className="text-muted">
        {canEdit
          ? "Arrastrá una opción para reordenarla, o soltala sobre un Menú para moverla adentro."
          : "Vista de sólo lectura — te falta el permiso para editar el árbol."}
      </p>
      {error && <div className="form-error">{error}</div>}

      <div className="menu-layout">
        <div className="menu-tree menu-main">
          <MenuChildrenList
            parentId={null}
            nodes={tree}
            canCreate={canCreate}
            canEdit={canEdit}
            canDelete={canDelete}
            collapsed={collapsed}
            onToggleCollapse={toggleCollapse}
            draggedId={draggedId}
            setDraggedId={setDraggedId}
            onReorder={reordenar}
            onEdit={(node) => setFormState({ parentId: null, node })}
            onDelete={eliminar}
            onAddChild={(parentId) => setFormState({ parentId })}
          />
        </div>

        <aside className="menu-side">
          <MenuWhatsAppPreview tree={tree} teams={teams} botMessages={botMessages} />
        </aside>
      </div>

      {formState && (
        <MenuOpcionFormModal
          parentId={formState.parentId}
          node={formState.node}
          teams={teams}
          botMessages={botMessages}
          onClose={() => setFormState(null)}
          onSaved={() => {
            setFormState(null);
            loadTree();
          }}
        />
      )}
    </div>
  );
}

interface ChildrenListProps {
  parentId: number | null;
  nodes: MenuOpcionTreeNode[];
  canCreate: boolean;
  canEdit: boolean;
  canDelete: boolean;
  collapsed: Set<number>;
  onToggleCollapse: (id: number) => void;
  draggedId: number | null;
  setDraggedId: (id: number | null) => void;
  onReorder: (parentId: number | null, orden: number[]) => void;
  onEdit: (node: MenuOpcionTreeNode) => void;
  onDelete: (node: MenuOpcionTreeNode) => void;
  onAddChild: (parentId: number) => void;
}

function MenuChildrenList({
  parentId, nodes, canCreate, canEdit, canDelete, collapsed, onToggleCollapse,
  draggedId, setDraggedId, onReorder, onEdit, onDelete, onAddChild,
}: ChildrenListProps) {
  const ids = nodes.map((n) => n.id);

  function dropBefore(beforeId: number | null) {
    if (draggedId === null) return;
    const filtered = ids.filter((id) => id !== draggedId);
    const idx = beforeId === null ? filtered.length : filtered.indexOf(beforeId);
    filtered.splice(idx === -1 ? filtered.length : idx, 0, draggedId);
    onReorder(parentId, filtered);
    setDraggedId(null);
  }

  return (
    <div className="menu-list">
      {canEdit && <DropIndicator active={draggedId !== null} onDrop={() => dropBefore(nodes[0]?.id ?? null)} />}
      {nodes.map((node, index) => (
        <div key={node.id} className="menu-node">
          <MenuCard
            node={node}
            canCreate={canCreate}
            canEdit={canEdit}
            canDelete={canDelete}
            isCollapsed={collapsed.has(node.id)}
            isDragging={draggedId === node.id}
            onToggleCollapse={() => onToggleCollapse(node.id)}
            onDragStart={() => setDraggedId(node.id)}
            onDragEnd={() => setDraggedId(null)}
            onDropInto={
              canEdit && node.tipo === "SUBMENU" && draggedId !== null && draggedId !== node.id
                ? () => {
                    const childIds = node.hijos.map((h) => h.id).filter((id) => id !== draggedId);
                    childIds.push(draggedId!);
                    onReorder(node.id, childIds);
                    setDraggedId(null);
                  }
                : undefined
            }
            onEdit={() => onEdit(node)}
            onDelete={() => onDelete(node)}
            onAddChild={node.tipo === "SUBMENU" ? () => onAddChild(node.id) : undefined}
          />
          {node.tipo === "SUBMENU" && !collapsed.has(node.id) && (
            <div className="menu-children">
              <MenuChildrenList
                parentId={node.id}
                nodes={node.hijos}
                canCreate={canCreate}
                canEdit={canEdit}
                canDelete={canDelete}
                collapsed={collapsed}
                onToggleCollapse={onToggleCollapse}
                draggedId={draggedId}
                setDraggedId={setDraggedId}
                onReorder={onReorder}
                onEdit={onEdit}
                onDelete={onDelete}
                onAddChild={onAddChild}
              />
            </div>
          )}
          {canEdit && (
            <DropIndicator active={draggedId !== null} onDrop={() => dropBefore(nodes[index + 1]?.id ?? null)} />
          )}
        </div>
      ))}
      {nodes.length === 0 && <div className="menu-empty">Sin opciones — soltá una acá</div>}
    </div>
  );
}

function DropIndicator({ active, onDrop }: { active: boolean; onDrop: () => void }) {
  const [hover, setHover] = useState(false);

  if (!active) return <div className="menu-drop-indicator" />;

  return (
    <div
      className={"menu-drop-indicator" + (hover ? " menu-drop-indicator-active" : "")}
      onDragOver={(e) => {
        e.preventDefault();
        setHover(true);
      }}
      onDragLeave={() => setHover(false)}
      onDrop={(e) => {
        e.preventDefault();
        setHover(false);
        onDrop();
      }}
    />
  );
}

function MenuCard({
  node, canCreate, canEdit, canDelete, isCollapsed, isDragging, onToggleCollapse,
  onDragStart, onDragEnd, onDropInto, onEdit, onDelete, onAddChild,
}: {
  node: MenuOpcionTreeNode;
  canCreate: boolean;
  canEdit: boolean;
  canDelete: boolean;
  isCollapsed: boolean;
  isDragging: boolean;
  onToggleCollapse: () => void;
  onDragStart: () => void;
  onDragEnd: () => void;
  onDropInto?: () => void;
  onEdit: () => void;
  onDelete: () => void;
  onAddChild?: () => void;
}) {
  const [hover, setHover] = useState(false);

  return (
    <div
      className={
        "menu-card" +
        (isDragging ? " menu-card-dragging" : "") +
        (!node.activo ? " menu-card-inactive" : "") +
        (hover && onDropInto ? " menu-card-drop-active" : "")
      }
      draggable={canEdit}
      onDragStart={(e) => {
        e.dataTransfer.effectAllowed = "move";
        onDragStart();
      }}
      onDragEnd={onDragEnd}
      onDragOver={(e) => {
        if (!onDropInto) return;
        e.preventDefault();
        setHover(true);
      }}
      onDragLeave={() => setHover(false)}
      onDrop={(e) => {
        if (!onDropInto) return;
        e.preventDefault();
        setHover(false);
        onDropInto();
      }}
    >
      {canEdit && <span className="menu-drag-handle" title="Arrastrar">⠿</span>}
      {node.tipo === "SUBMENU" ? (
        <button className="menu-toggle" onClick={onToggleCollapse} title="Mostrar/ocultar">
          {isCollapsed ? "▸" : "▾"}
        </button>
      ) : (
        <span className="menu-toggle-placeholder" />
      )}
      <span className="menu-icon">{TIPO_ICONO[node.tipo]}</span>
      <div className="menu-card-text">
        <strong>{node.texto}</strong> <code className="text-muted">({node.slug})</code>
        {!node.activo && <span className="badge badge-warning">Inactiva</span>}
      </div>
      <span className="badge">{MENU_TIPO_LABELS[node.tipo]}</span>
      {(canCreate || canEdit || canDelete) && (
        <div className="menu-card-actions">
          {canCreate && onAddChild && (
            <button className="btn btn-ghost btn-sm" onClick={onAddChild} title="Agregar opción adentro">
              +
            </button>
          )}
          {canEdit && (
            <button className="btn btn-ghost btn-sm" onClick={onEdit} title="Editar">
              ✎
            </button>
          )}
          {canDelete && (
            <button className="btn btn-ghost btn-sm btn-danger" onClick={onDelete} title="Eliminar">
              🗑
            </button>
          )}
        </div>
      )}
    </div>
  );
}

/** Texto del "mensaje" que dispara un nodo que no es Respuesta pero igual
 * manda algo (Derivación → mensaje de derivación, Terminar → despedida) —
 * usa los mensajes predeterminados de la organización, con fallback a un
 * texto genérico si todavía no se cargaron/no hay permiso para verlos. */
function mensajeDeNodo(
  node: { tipo: MenuTipo; respuesta_texto: string; team: number | null },
  botMessages: BotMessages | null,
  teams: Team[],
  area: string,
): { caption: string; texto: string } | null {
  if (node.tipo === "RESPUESTA") {
    return { caption: "Respuesta", texto: node.respuesta_texto || "(sin texto todavía)" };
  }

  if (node.tipo === "DERIVACION") {
    const base = botMessages?.derivacion_mensaje?.trim() || botMessages?.valores_efectivos?.derivacion_mensaje
      || "Te derivamos con un operador. En breve te van a contactar. 🕑";

    const equipo = teams.find((t) => t.id === node.team)?.name ?? "un equipo";

    return { caption: `Deriva a "${equipo}"`, texto: aplicarVariables(base, { area, nombre: "Juan" }) };
  }

  if (node.tipo === "TERMINAR") {
    const base = botMessages?.mensaje_despedida?.trim() || botMessages?.valores_efectivos?.mensaje_despedida
      || "Gracias por contactarnos. ¡Hasta luego!";

    return { caption: "Despedida", texto: aplicarVariables(base, { nombre: "Juan" }) };
  }

  return null;
}

/** Vista previa navegable estilo chat: arranca en el menú principal y deja
 * clickear cada opción como lo haría un contacto real (entra a los
 * submenús, muestra la respuesta/derivación/despedida correspondiente). */
function MenuWhatsAppPreview({
  tree, teams, botMessages,
}: {
  tree: MenuOpcionTreeNode[];
  teams: Team[];
  botMessages: BotMessages | null;
}) {
  const [path, setPath] = useState<MenuOpcionTreeNode[]>([]);
  const [respuesta, setRespuesta] = useState<{ caption: string; texto: string } | null>(null);

  const nivelActual = (path.length === 0 ? tree : path[path.length - 1].hijos).filter((n) => n.activo);
  const areaActual = path.length === 0 ? "Menú principal" : path[path.length - 1].texto;

  function elegir(node: MenuOpcionTreeNode) {
    setRespuesta(null);

    if (node.tipo === "SUBMENU") {
      setPath((p) => [...p, node]);

      return;
    }

    if (node.tipo === "INICIO") {
      setPath([]);

      return;
    }

    if (node.tipo === "VOLVER") {
      setPath((p) => p.slice(0, -1));

      return;
    }

    setRespuesta(mensajeDeNodo(node, botMessages, teams, areaActual));
  }

  const saludo =
    path.length === 0
      ? botMessages?.saludo_inicial?.trim() || botMessages?.valores_efectivos?.saludo_inicial || "Menú principal"
      : aplicarVariables(
          botMessages?.saludo_area?.trim() || botMessages?.valores_efectivos?.saludo_area || 'Área "{area}"',
          { area: areaActual },
        );

  return (
    <PhoneFrame title="Menú (navegable)">
      <BotBubble>{renderMarkup(saludo)}</BotBubble>
      <div className="wa-bubble wa-bubble-bot wa-bubble-list">
        {path.length > 0 && <BackRow onClick={() => setPath((p) => p.slice(0, -1))} />}
        {nivelActual.map((node, i) => (
          <OptionRow key={node.id} index={i + 1} onClick={() => elegir(node)}>
            {node.texto}
          </OptionRow>
        ))}
        {nivelActual.length === 0 && <div className="wa-empty">Sin opciones acá todavía</div>}
      </div>
      {respuesta && <BotBubble caption={respuesta.caption}>{renderMarkup(respuesta.texto)}</BotBubble>}
    </PhoneFrame>
  );
}

const TIPOS: MenuTipo[] = ["SUBMENU", "RESPUESTA", "DERIVACION", "VOLVER", "INICIO", "TERMINAR"];

// Body de POST/PATCH a `menu-opciones` — `respuesta_texto`/`team`/`parent`
// sólo se mandan según `tipo` (ver `handleSubmit` de `MenuOpcionFormModal`).
interface MenuOpcionPayload {
  texto: string;
  tipo: MenuTipo;
  activo: boolean;
  respuesta_texto?: string;
  team?: number | null;
  parent?: number | null;
}

function MenuOpcionFormModal({
  parentId, node, teams, botMessages, onClose, onSaved,
}: {
  parentId: number | null;
  node?: MenuOpcionTreeNode;
  teams: Team[];
  botMessages: BotMessages | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [texto, setTexto] = useState(node?.texto ?? "");
  const [tipo, setTipo] = useState<MenuTipo>(node?.tipo ?? "SUBMENU");
  const [respuestaTexto, setRespuestaTexto] = useState(node?.respuesta_texto ?? "");
  const [teamId, setTeamId] = useState<number | "">(node?.team ?? "");
  const [activo, setActivo] = useState(node?.activo ?? true);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);

    try {
      const body: MenuOpcionPayload = { texto, tipo, activo };

      if (tipo === "RESPUESTA") body.respuesta_texto = respuestaTexto;

      // No sólo Derivación: un SUBMENU también puede tener equipo cargado,
      // para marcar "esto es el área de Soporte" desde que se entra (la
      // etiqueta de equipo se sincroniza sola al elegir la opción, no hace
      // falta llegar a una Derivación de verdad — ver `conversations.
      // etiqueta_sistema.sincronizar_etiqueta_equipo`).
      if (tipo === "DERIVACION" || tipo === "SUBMENU") body.team = teamId || null;

      if (!node) body.parent = parentId;

      if (node) await api.patch(`/api/core/menu-opciones/${node.id}/`, body);
      else await api.post("/api/core/menu-opciones/", body);
      onSaved();
    } catch (err) {
      setError(extraerMensajeDeError(err) ?? "No se pudo guardar.");
    } finally {
      setSubmitting(false);
    }
  }

  const mensajePreview = mensajeDeNodo({ tipo, respuesta_texto: respuestaTexto, team: teamId || null }, botMessages, teams, "este menú");

  function handleTipoChange(e: ChangeEvent<HTMLSelectElement>) {
    // SAFETY: las <option> de este <select> salen de `TIPOS` (MenuTipo[])
    // más abajo, así que el value siempre es uno de esos literales aunque
    // el DOM lo tipe como string.
    setTipo(e.target.value as MenuTipo);
  }

  return (
    <Modal title={node ? "Editar opción" : "Nueva opción"} onClose={onClose} wide>
      <div className="modal-with-preview">
        <form onSubmit={handleSubmit} className="form-stack">
          <label>
            Texto
            <input required value={texto} onChange={(e) => setTexto(e.target.value)} />
          </label>
          <label>
            Tipo
            <select value={tipo} onChange={handleTipoChange}>
              {TIPOS.map((t) => (
                <option key={t} value={t}>
                  {MENU_TIPO_LABELS[t]}
                </option>
              ))}
            </select>
          </label>
          {tipo === "RESPUESTA" && (
            <label>
              Texto de respuesta
              <MessageEditor rows={4} value={respuestaTexto} onChange={setRespuestaTexto} />
            </label>
          )}
          {(tipo === "DERIVACION" || tipo === "SUBMENU") && (
            <label>
              Equipo{tipo === "SUBMENU" && " (opcional)"}
              <select
                required={tipo === "DERIVACION"}
                value={teamId}
                onChange={(e) => setTeamId(e.target.value ? Number(e.target.value) : "")}
              >
                <option value="">{tipo === "SUBMENU" ? "— sin área —" : "— elegir —"}</option>
                {teams.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                  </option>
                ))}
              </select>
              {tipo === "SUBMENU" && (
                <span className="text-muted field-help">
                  Marca este submenú como el área de ese equipo — se le aplica su etiqueta al
                  contacto desde que entra, aunque todavía no haya un paso de Derivación.
                </span>
              )}
            </label>
          )}
          <label className="checkbox-label">
            <input type="checkbox" checked={activo} onChange={(e) => setActivo(e.target.checked)} />
            Activo
          </label>
          {error && <div className="form-error">{error}</div>}
          <button className="btn btn-primary" type="submit" disabled={submitting}>
            {submitting ? "Guardando…" : "Guardar"}
          </button>
        </form>

        <div className="modal-preview">
          <div className="field-label">Vista previa</div>
          <PhoneFrame>
            <div className="wa-bubble wa-bubble-bot wa-bubble-list">
              <OptionRow index="N">{texto || "(texto de la opción)"}</OptionRow>
            </div>
            {mensajePreview && <BotBubble caption={mensajePreview.caption}>{renderMarkup(mensajePreview.texto)}</BotBubble>}
          </PhoneFrame>
        </div>
      </div>
    </Modal>
  );
}
