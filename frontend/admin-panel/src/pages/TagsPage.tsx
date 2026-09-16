import { type FormEvent, useEffect, useRef, useState } from "react";

import { api, ApiError, extraerMensajeDeError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { hasPerm } from "../auth/permissions";
import type { Etiqueta, Paginated } from "../types";

const HEX_RE = /^#[0-9A-Fa-f]{6}$/;

export default function TagsPage() {
  const { me } = useAuth();
  const canCreate = hasPerm(me, "tags.add_etiqueta");
  const canEdit = hasPerm(me, "tags.change_etiqueta");
  const canDelete = hasPerm(me, "tags.delete_etiqueta");

  const [tags, setTags] = useState<Etiqueta[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  async function load() {
    try {
      const data = await api.get<Paginated<Etiqueta>>("/api/core/etiquetas/");
      setTags(data.results);
    } catch (err) {
      setError(err instanceof ApiError && err.status === 403 ? "No tenés permiso para ver esta sección." : "No se pudo cargar el catálogo.");
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function eliminar(tag: Etiqueta) {
    if (!confirm(`¿Eliminar la etiqueta "${tag.nombre}"?`)) return;

    try {
      await api.delete(`/api/core/etiquetas/${tag.id}/`);
      load();
    } catch (err) {
      alert(err instanceof ApiError && err.data ? JSON.stringify(err.data) : "No se pudo eliminar.");
    }
  }

  if (error) return <div className="empty-state">{error}</div>;

  if (!tags) return <div className="page-loading">Cargando…</div>;

  const generales = tags.filter((t) => t.team === null);
  const deEquipo = tags.filter((t) => t.team !== null);

  return (
    <div>
      <div className="page-header">
        <h2>Etiquetas de conversación</h2>
        {canCreate && !creating && (
          <button className="btn btn-primary" onClick={() => setCreating(true)}>
            + Nueva etiqueta
          </button>
        )}
      </div>
      <p className="text-muted">
        Las 7 etiquetas de estado (Pendiente, Asignada, Tomada, En proceso, En pausa, Rechazado, Resuelto) vienen
        por defecto en toda organización — no se pueden borrar ni renombrar, sólo recolorear. Cada equipo es
        además una etiqueta en sí mismo (se autogenera y se renombra sola si renombrás el equipo). El resto de
        las etiquetas generales las arma cada organización a mano. Aplicarlas a una conversación es parte del
        Operators Desk (todavía no implementado).
      </p>

      <div className="card" style={{ marginBottom: "1rem" }}>
        <h3 className="section-title-sm">Generales de la organización</h3>
        <div className="tag-list">
          {(generales.length > 0 || creating) && <TagListHeader />}
          {creating && (
            <TagCreateRow
              onCancel={() => setCreating(false)}
              onSaved={() => {
                setCreating(false);
                load();
              }}
            />
          )}
          {generales.length === 0 && !creating && <p className="text-muted">Sin etiquetas todavía.</p>}
          {generales.map((t) => (
            <TagRow key={t.id} tag={t} canEdit={canEdit} canDelete={canDelete} onSaved={load} onDelete={() => eliminar(t)} />
          ))}
        </div>
      </div>

      <div className="card" style={{ marginBottom: "1rem" }}>
        <h3 className="section-title-sm">De equipo (una por cada equipo, automática)</h3>
        <div className="tag-list">
          {deEquipo.length === 0 ? (
            <p className="text-muted">Sin etiquetas todavía.</p>
          ) : (
            <>
              <TagListHeader />
              {deEquipo.map((t) => (
                <TagRow key={t.id} tag={t} canEdit={canEdit} canDelete={canDelete} onSaved={load} onDelete={() => eliminar(t)} />
              ))}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

/** Encabezado de columnas — una sola vez por grupo (generales / de equipo),
 * en vez de repetir la etiqueta de cada campo en cada fila. */
function TagListHeader() {
  return (
    <div className="tag-edit-row tag-list-header">
      <div className="tag-edit-col tag-edit-col-preview">
        <span className="field-label-sm">Vista previa</span>
      </div>
      <div className="tag-edit-col tag-edit-col-name">
        <span className="field-label-sm">Nombre</span>
      </div>
      <div className="tag-edit-col tag-edit-col-color">
        <span className="field-label-sm">Color de fondo</span>
      </div>
      <div className="tag-edit-col tag-edit-col-font">
        <span className="field-label-sm">Color de fuente</span>
      </div>
      <div className="tag-edit-col tag-edit-col-actions">
        <span className="field-label-sm">&nbsp;</span>
      </div>
    </div>
  );
}

/** Campos compartidos entre la fila de una etiqueta existente (siempre
 * editable, sin botón "Editar" de por medio) y la fila de alta de una
 * etiqueta nueva. */
function TagFields({
  nombre, setNombre, color, setColor, colorTexto, setColorTexto, protegida, protegidaTitle, autoFocus,
}: {
  nombre: string;
  setNombre: (v: string) => void;
  color: string;
  setColor: (v: string) => void;
  colorTexto: string;
  setColorTexto: (v: string) => void;
  protegida: boolean;
  protegidaTitle?: string;
  autoFocus?: boolean;
}) {
  return (
    <>
      <div className="tag-edit-col tag-edit-col-preview">
        <span className="tag-chip" style={{ background: color, color: colorTexto }}>
          {nombre || "Etiqueta"}
        </span>
      </div>

      <div className="tag-edit-col tag-edit-col-name">
        <input
          className="tag-edit-name"
          required
          autoFocus={autoFocus}
          value={nombre}
          disabled={protegida}
          placeholder="Nombre"
          title={protegida ? protegidaTitle : undefined}
          onChange={(e) => setNombre(e.target.value)}
        />
      </div>

      <div className="tag-edit-col tag-edit-col-color">
        <ColorPickerButton value={color} onChange={setColor} label="Color de fondo" />
      </div>

      <div className="tag-edit-col tag-edit-col-font">
        <div className="font-color-options" role="group" aria-label="Color de la fuente">
          <button
            type="button"
            className={"font-swatch" + (colorTexto === "#FFFFFF" ? " font-swatch-active" : "")}
            style={{ color: "#FFFFFF" }}
            onClick={() => setColorTexto("#FFFFFF")}
            title="Fuente blanca"
            aria-label="Fuente blanca"
          >
            A
          </button>
          <button
            type="button"
            className={"font-swatch" + (colorTexto === "#000000" ? " font-swatch-active" : "")}
            style={{ color: "#000000" }}
            onClick={() => setColorTexto("#000000")}
            title="Fuente negra"
            aria-label="Fuente negra"
          >
            A
          </button>
        </div>
      </div>
    </>
  );
}

/** Fila de una etiqueta existente — SIEMPRE editable en la lista, sin
 * botón "Editar" de por medio: se cambia el nombre/color ahí mismo y se
 * confirma con "Guardar". */
// `nombre` sólo se manda si la etiqueta no es protegida (ver `handleSubmit`
// de `TagRow` más abajo).
interface EtiquetaPayload {
  color: string;
  color_texto: string;
  nombre?: string;
}

function TagRow({
  tag, canEdit, canDelete, onSaved, onDelete,
}: {
  tag: Etiqueta;
  canEdit: boolean;
  canDelete: boolean;
  onSaved: () => void;
  onDelete: () => void;
}) {
  const protegida = tag.es_sistema || tag.team !== null;
  const [nombre, setNombre] = useState(tag.nombre);
  const [color, setColor] = useState(tag.color);
  const [colorTexto, setColorTexto] = useState(tag.color_texto);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (!canEdit) {
    return (
      <div className="tag-chip-row">
        <span className="tag-chip" style={{ background: tag.color, color: tag.color_texto }}>
          {tag.nombre}
        </span>
        {tag.es_sistema && <span className="badge">sistema</span>}
        {tag.team !== null && <span className="badge">equipo</span>}
        {canDelete && !protegida && (
          <button className="btn btn-ghost btn-sm btn-danger" onClick={onDelete}>
            Eliminar
          </button>
        )}
      </div>
    );
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);

    try {
      const body: EtiquetaPayload = { color, color_texto: colorTexto };

      if (!protegida) body.nombre = nombre;
      await api.patch(`/api/core/etiquetas/${tag.id}/`, body);
      onSaved();
    } catch (err) {
      setError(extraerMensajeDeError(err) ?? "No se pudo guardar.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="tag-edit-row">
      <TagFields
        nombre={nombre}
        setNombre={setNombre}
        color={color}
        setColor={setColor}
        colorTexto={colorTexto}
        setColorTexto={setColorTexto}
        protegida={protegida}
        protegidaTitle={
          tag.es_sistema
            ? "Etiqueta de sistema: sólo se le puede cambiar el color."
            : "Etiqueta de equipo: se renombra sola si renombrás el equipo."
        }
      />
      <div className="tag-edit-col tag-edit-col-actions">
        <div className="tag-edit-actions">
          <button className="btn btn-primary btn-sm tag-save-btn" type="submit" disabled={submitting}>
            <span aria-hidden="true">✓</span> {submitting ? "Guardando…" : "Guardar"}
          </button>
          {canDelete && !protegida && (
            <button type="button" className="btn btn-ghost btn-sm btn-danger" onClick={onDelete}>
              Eliminar
            </button>
          )}
        </div>
      </div>
      {error && <div className="form-error tag-edit-error">{error}</div>}
    </form>
  );
}

/** Fila de alta de una etiqueta nueva — sólo generales, siempre `team=None`. */
function TagCreateRow({
  onCancel, onSaved,
}: {
  onCancel: () => void;
  onSaved: () => void;
}) {
  const [nombre, setNombre] = useState("");
  const [color, setColor] = useState("#3454D1");
  const [colorTexto, setColorTexto] = useState("#FFFFFF");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);

    try {
      await api.post("/api/core/etiquetas/", { nombre, color, color_texto: colorTexto });
      onSaved();
    } catch (err) {
      setError(extraerMensajeDeError(err) ?? "No se pudo guardar.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="tag-edit-row">
      <TagFields
        nombre={nombre}
        setNombre={setNombre}
        color={color}
        setColor={setColor}
        colorTexto={colorTexto}
        setColorTexto={setColorTexto}
        protegida={false}
        autoFocus
      />
      <div className="tag-edit-col tag-edit-col-actions">
        <div className="tag-edit-actions">
          <button className="btn btn-primary btn-sm tag-save-btn" type="submit" disabled={submitting}>
            <span aria-hidden="true">✓</span> {submitting ? "Guardando…" : "Guardar"}
          </button>
          <button type="button" className="btn btn-ghost btn-sm" onClick={onCancel}>
            Cancelar
          </button>
        </div>
      </div>
      {error && <div className="form-error tag-edit-error">{error}</div>}
    </form>
  );
}

/** Botón que muestra el color actual como swatch; al clickear abre un
 * popover con el selector nativo (visual) y un campo de texto para cargar
 * el hexadecimal a mano — las dos formas quedan sincronizadas. */
function ColorPickerButton({
  value, onChange, label,
}: {
  value: string;
  onChange: (hex: string) => void;
  label: string;
}) {
  const [open, setOpen] = useState(false);
  const [hexInput, setHexInput] = useState(value);
  const wrapRef = useRef<HTMLDivElement>(null);

  useEffect(() => setHexInput(value), [value]);

  useEffect(() => {
    if (!open) return;

    function onDocClick(e: MouseEvent) {
      // SAFETY: `e.target` de un evento DOM real siempre es un Node —
      // `MouseEvent` sólo lo tipa como `EventTarget` porque también acepta
      // targets sintéticos que no lo son.
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false);
    }

    document.addEventListener("mousedown", onDocClick);

    return () => document.removeEventListener("mousedown", onDocClick);
  }, [open]);

  function applyHex(raw: string) {
    let v = raw.trim();

    if (v && !v.startsWith("#")) v = "#" + v;

    if (HEX_RE.test(v)) onChange(v.toUpperCase());
    else setHexInput(value);
  }

  return (
    <div className="color-picker" ref={wrapRef}>
      <button
        type="button"
        className="color-swatch-btn"
        style={{ background: value }}
        onClick={() => setOpen((o) => !o)}
        aria-label={`${label}: ${value}`}
        title={`${label}: ${value}`}
      />
      {open && (
        <div className="color-picker-popover">
          <input type="color" value={value} onChange={(e) => onChange(e.target.value.toUpperCase())} />
          <input
            type="text"
            className="color-hex-input"
            value={hexInput}
            onChange={(e) => setHexInput(e.target.value)}
            onBlur={() => applyHex(hexInput)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                applyHex(hexInput);
              }
            }}
            placeholder="#RRGGBB"
            maxLength={7}
          />
        </div>
      )}
    </div>
  );
}
