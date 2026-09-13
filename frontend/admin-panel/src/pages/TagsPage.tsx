import { type FormEvent, useEffect, useState } from "react";

import { api, ApiError } from "../api/client";
import Modal from "../components/Modal";
import { useAuth } from "../auth/AuthContext";
import { hasPerm } from "../auth/permissions";
import type { Etiqueta, Paginated } from "../types";

export default function TagsPage() {
  const { me } = useAuth();
  const canCreate = hasPerm(me, "tags.add_etiqueta");
  const canEdit = hasPerm(me, "tags.change_etiqueta");
  const canDelete = hasPerm(me, "tags.delete_etiqueta");

  const [tags, setTags] = useState<Etiqueta[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [editing, setEditing] = useState<Etiqueta | null>(null);

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
        {canCreate && (
          <button className="btn btn-primary" onClick={() => setShowCreate(true)}>
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

      <TagGroup
        title="Generales de la organización"
        tags={generales}
        canEdit={canEdit}
        canDelete={canDelete}
        onEdit={setEditing}
        onDelete={eliminar}
      />
      <TagGroup
        title="De equipo (una por cada equipo, automática)"
        tags={deEquipo}
        canEdit={canEdit}
        canDelete={canDelete}
        onEdit={setEditing}
        onDelete={eliminar}
      />

      {showCreate && (
        <TagFormModal
          onClose={() => setShowCreate(false)}
          onSaved={() => {
            setShowCreate(false);
            load();
          }}
        />
      )}
      {editing && (
        <TagFormModal
          tag={editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            load();
          }}
        />
      )}
    </div>
  );
}

function TagGroup({
  title, tags, canEdit, canDelete, onEdit, onDelete,
}: {
  title: string;
  tags: Etiqueta[];
  canEdit: boolean;
  canDelete: boolean;
  onEdit: (t: Etiqueta) => void;
  onDelete: (t: Etiqueta) => void;
}) {
  return (
    <div className="card" style={{ marginBottom: "1rem" }}>
      <h3 className="section-title-sm">{title}</h3>
      {tags.length === 0 ? (
        <p className="text-muted">Sin etiquetas todavía.</p>
      ) : (
        <div className="tag-list">
          {tags.map((t) => {
            const protegida = t.es_sistema || t.team !== null;
            return (
              <div key={t.id} className="tag-chip-row">
                <span className="tag-chip" style={{ background: t.color, color: t.color_texto }}>
                  {t.nombre}
                </span>
                {t.es_sistema && <span className="badge">sistema</span>}
                {t.team !== null && <span className="badge">equipo</span>}
                {(canEdit || (canDelete && !protegida)) && (
                  <span className="table-actions">
                    {canEdit && (
                      <button className="btn btn-ghost btn-sm" onClick={() => onEdit(t)}>
                        Editar
                      </button>
                    )}
                    {canDelete && !protegida && (
                      <button className="btn btn-ghost btn-sm btn-danger" onClick={() => onDelete(t)}>
                        Eliminar
                      </button>
                    )}
                  </span>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function TagFormModal({
  tag, onClose, onSaved,
}: {
  tag?: Etiqueta;
  onClose: () => void;
  onSaved: () => void;
}) {
  const protegida = !!tag && (tag.es_sistema || tag.team !== null);
  const [nombre, setNombre] = useState(tag?.nombre ?? "");
  const [color, setColor] = useState(tag?.color ?? "#3454D1");
  const [colorTexto, setColorTexto] = useState(tag?.color_texto ?? "#FFFFFF");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const body: Record<string, unknown> = { color, color_texto: colorTexto };
      if (!protegida) body.nombre = nombre;
      if (tag) await api.patch(`/api/core/etiquetas/${tag.id}/`, body);
      else await api.post("/api/core/etiquetas/", body);
      onSaved();
    } catch (err) {
      if (err instanceof ApiError && err.data && typeof err.data === "object") {
        setError(Object.values(err.data as Record<string, string[]>).flat().join(" "));
      } else {
        setError("No se pudo guardar.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal title={tag ? `Editar "${tag.nombre}"` : "Nueva etiqueta"} onClose={onClose}>
      <form onSubmit={handleSubmit} className="form-stack">
        <label>
          Nombre
          <input
            required
            value={nombre}
            disabled={protegida}
            onChange={(e) => setNombre(e.target.value)}
          />
          {protegida && (
            <span className="text-muted field-help">
              {tag?.es_sistema
                ? "Es una etiqueta de sistema: sólo se le puede cambiar el color."
                : "Es la etiqueta de un equipo: se renombra sola si renombrás el equipo, sólo se le puede cambiar el color."}
            </span>
          )}
        </label>
        <label>
          Color de fondo
          <input type="color" value={color} onChange={(e) => setColor(e.target.value)} />
        </label>
        <div>
          <div className="field-label">Color de la fuente</div>
          <div className="button-group">
            <button
              type="button"
              className={"btn-toggle" + (colorTexto === "#FFFFFF" ? " btn-toggle-active" : "")}
              onClick={() => setColorTexto("#FFFFFF")}
            >
              Blanco
            </button>
            <button
              type="button"
              className={"btn-toggle" + (colorTexto === "#000000" ? " btn-toggle-active" : "")}
              onClick={() => setColorTexto("#000000")}
            >
              Negro
            </button>
          </div>
        </div>
        <div>
          <div className="field-label">Vista previa</div>
          <span className="tag-chip" style={{ background: color, color: colorTexto }}>
            {nombre || "Etiqueta"}
          </span>
        </div>
        {error && <div className="form-error">{error}</div>}
        <button className="btn btn-primary" type="submit" disabled={submitting}>
          {submitting ? "Guardando…" : "Guardar"}
        </button>
      </form>
    </Modal>
  );
}
