import { useEffect, useRef, useState } from "react";

import { api, ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { hasPerm } from "../auth/permissions";
import {
  DIA_EXCEPCIONAL_TIPO_LABELS, DIA_SEMANA_LABELS,
  type DiaExcepcional, type DiaExcepcionalTipo, type GrillaDia, type GrillaDias, type GrillaSemanal, type Paginated,
} from "../types";

// Grillas "pintables" por click-y-arrastre — mismo mecanismo que
// chatbot/static/js/chatbot_horarios.js (activarPintadoGrilla), reimplementado
// con estado de React en vez de manipular clases del DOM a mano.
export default function BusinessHoursPage() {
  const { me } = useAuth();
  const [tab, setTab] = useState<"semanal" | "excepciones">("semanal");

  return (
    <div>
      <div className="page-header">
        <h2>Horarios de atención</h2>
      </div>
      <div className="tabs">
        <button className={"tab" + (tab === "semanal" ? " tab-active" : "")} onClick={() => setTab("semanal")}>
          Horario semanal
        </button>
        <button className={"tab" + (tab === "excepciones" ? " tab-active" : "")} onClick={() => setTab("excepciones")}>
          Días excepcionales
        </button>
      </div>
      {tab === "semanal" ? (
        <WeeklyGrid canEdit={hasPerm(me, "business_hours.change_horarioatencion")} />
      ) : (
        <ExceptionsEditor canEdit={hasPerm(me, "business_hours.change_diaexcepcional")} />
      )}
    </div>
  );
}

function key(dia: number, slot: string) {
  return `${dia}-${slot}`;
}

function addMinutes(hhmm: string, minutes: number): string {
  const [h, m] = hhmm.split(":").map(Number);
  const total = h * 60 + m + minutes;
  const hh = Math.floor(total / 60) % 24;
  const mm = total % 60;
  return `${String(hh).padStart(2, "0")}:${String(mm).padStart(2, "0")}`;
}

/** Convierte los slots de media hora pintados de un día en rangos legibles,
 * ej. "09:00-13:00, 14:00-18:00" — o "Cerrado" si no hay ninguno. */
function resumenDeSlots(slots: string[], marcados: Set<string>): string {
  const indices = slots.map((s, i) => (marcados.has(s) ? i : -1)).filter((i) => i !== -1);
  if (indices.length === 0) return "Cerrado";
  const rangos: string[] = [];
  let inicio = indices[0];
  let anterior = indices[0];
  for (let i = 1; i < indices.length; i++) {
    if (indices[i] === anterior + 1) {
      anterior = indices[i];
      continue;
    }
    rangos.push(`${slots[inicio]}-${addMinutes(slots[anterior], 30)}`);
    inicio = indices[i];
    anterior = indices[i];
  }
  rangos.push(`${slots[inicio]}-${addMinutes(slots[anterior], 30)}`);
  return rangos.join(", ");
}

function WeeklyGrid({ canEdit }: { canEdit: boolean }) {
  const [slots, setSlots] = useState<string[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [incluirFinde, setIncluirFinde] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [saving, setSaving] = useState(false);
  const [diaResaltado, setDiaResaltado] = useState<number | null>(null);
  const [rangeDia, setRangeDia] = useState(0);
  const [rangeDesde, setRangeDesde] = useState("");
  const [rangeHasta, setRangeHasta] = useState("");
  const painting = useRef(false);
  const addMode = useRef(true);

  async function load() {
    const data = await api.get<GrillaSemanal>("/api/core/horarios-atencion/grilla/");
    setSlots(data.slots);
    setSelected(new Set(data.celdas));
    setLoaded(true);
    if (data.slots.length) {
      setRangeDesde(data.slots[0]);
      setRangeHasta(addMinutes(data.slots[data.slots.length - 1], 30));
    }
  }

  useEffect(() => {
    load();
    const onUp = () => {
      painting.current = false;
    };
    window.addEventListener("mouseup", onUp);
    return () => window.removeEventListener("mouseup", onUp);
  }, []);

  function setCell(k: string, value: boolean) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (value) next.add(k);
      else next.delete(k);
      return next;
    });
  }

  function handleMouseDown(dia: number, slot: string) {
    if (!canEdit) return;
    setDiaResaltado(dia);
    const k = key(dia, slot);
    addMode.current = !selected.has(k);
    painting.current = true;
    setCell(k, addMode.current);
  }

  function handleMouseEnter(dia: number, slot: string) {
    if (!canEdit || !painting.current) return;
    setCell(key(dia, slot), addMode.current);
  }

  function limpiarTodo() {
    setSelected(new Set());
  }

  /** Marca (o borra) de una sola vez todo un tramo horario continuo de un
   * día — más rápido e intuitivo que arrastrar el mouse celda por celda
   * cuando el horario es un rango largo y regular (ej. 09:00 a 18:00). */
  function aplicarRango(valor: boolean) {
    if (!rangeDesde || !rangeHasta) return;
    setSelected((prev) => {
      const next = new Set(prev);
      if (valor) {
        // "Marcar horario" reemplaza el horario de ESE día por exactamente
        // el rango elegido (no suma) — si no, no habría forma de "reducir"
        // un horario ya más ancho volviendo a elegir un rango más chico:
        // lo de afuera del nuevo rango quedaría marcado igual.
        slots.forEach((s) => next.delete(key(rangeDia, s)));
      }
      slots.forEach((s) => {
        const fin = addMinutes(s, 30);
        if (s >= rangeDesde && fin <= rangeHasta) {
          const k = key(rangeDia, s);
          if (valor) next.add(k);
          else next.delete(k);
        }
      });
      return next;
    });
    setDiaResaltado(rangeDia);
  }

  function copiarLunes() {
    const lunesSeleccionados = slots.filter((s) => selected.has(key(0, s)));
    const lunesSet = new Set(lunesSeleccionados);
    setSelected((prev) => {
      const next = new Set(prev);
      for (let dia = 1; dia <= 6; dia++) {
        if (!incluirFinde && (dia === 5 || dia === 6)) continue;
        slots.forEach((s) => {
          const k = key(dia, s);
          if (lunesSet.has(s)) next.add(k);
          else next.delete(k);
        });
      }
      return next;
    });
  }

  async function guardar() {
    setSaving(true);
    try {
      await api.post("/api/core/horarios-atencion/grilla/", { celdas: Array.from(selected) });
      await load();
    } finally {
      setSaving(false);
    }
  }

  if (!loaded) return <div className="page-loading">Cargando…</div>;

  return (
    <div className="hours-layout">
      <div className="card hours-main">
        <p className="text-muted">
          Cliqueá y arrastrá sobre la grilla para pintar los horarios en los que la opción "Derivación" deriva a un
          operador. Si dejás todo sin pintar, la derivación funciona siempre (sin restricción de horario). Los días
          excepcionales pisan esto para una fecha puntual.
        </p>
        {canEdit && (
          <>
            <div className="range-selector">
              <label>
                Día
                <select value={rangeDia} onChange={(e) => setRangeDia(Number(e.target.value))}>
                  {DIA_SEMANA_LABELS.map((label, dia) => (
                    <option key={dia} value={dia}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Desde
                <select value={rangeDesde} onChange={(e) => setRangeDesde(e.target.value)}>
                  {slots.map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Hasta
                <select value={rangeHasta} onChange={(e) => setRangeHasta(e.target.value)}>
                  {slots.map((s) => {
                    const fin = addMinutes(s, 30);
                    return (
                      <option key={fin} value={fin}>
                        {fin}
                      </option>
                    );
                  })}
                </select>
              </label>
              <div className="toolbar">
                <button className="btn btn-primary btn-sm" type="button" onClick={() => aplicarRango(true)}>
                  Marcar horario
                </button>
                <button className="btn btn-ghost btn-sm" type="button" onClick={() => aplicarRango(false)}>
                  Marcar cerrado
                </button>
              </div>
              <span className="text-muted field-help">
                "Marcar horario" reemplaza todo el horario de ese día por este rango (para reducirlo, elegí el
                rango más chico que querés dejar). "Marcar cerrado" sólo cierra este tramo puntual sin tocar el
                resto del día — útil para un corte al mediodía.
              </span>
            </div>
            <div className="toolbar">
              <button className="btn btn-ghost" onClick={limpiarTodo}>
                Limpiar todo
              </button>
              <button className="btn btn-ghost" onClick={copiarLunes}>
                Copiar Lunes a Martes-Viernes
              </button>
              <label className="checkbox-label">
                <input type="checkbox" checked={incluirFinde} onChange={(e) => setIncluirFinde(e.target.checked)} />
                incluir Sábado y Domingo
              </label>
              <button className="btn btn-primary" onClick={guardar} disabled={saving}>
                {saving ? "Guardando…" : "Guardar"}
              </button>
            </div>
          </>
        )}
        <div className="grid-scroll">
          <table className="grilla-horarios">
            <thead>
              <tr>
                <th></th>
                {DIA_SEMANA_LABELS.map((label, dia) => (
                  <th
                    key={dia}
                    className={
                      (dia >= 5 ? "columna-finde " : "") + (dia === diaResaltado ? "columna-resaltada" : "")
                    }
                  >
                    {label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {slots.map((slot) => (
                <tr key={slot} className={slot.endsWith(":00") ? "hora-en-punto" : undefined}>
                  <td className="grilla-hora">{slot}</td>
                  {DIA_SEMANA_LABELS.map((_, dia) => {
                    const isSel = selected.has(key(dia, slot));
                    return (
                      <td key={dia} className={dia === diaResaltado ? "columna-resaltada" : ""}>
                        <div
                          className={"celda-horario" + (isSel ? " celda-seleccionada" : "")}
                          onMouseDown={() => handleMouseDown(dia, slot)}
                          onMouseEnter={() => handleMouseEnter(dia, slot)}
                        />
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <aside className="hours-side">
        <div className="card">
          <h3 className="section-title-sm">Vista previa semanal</h3>
          <ul className="week-preview-list">
            {DIA_SEMANA_LABELS.map((label, dia) => (
              <li
                key={dia}
                className={"week-preview-item" + (diaResaltado === dia ? " week-preview-item-active" : "")}
                onClick={() => setDiaResaltado(dia)}
              >
                <strong>{label}</strong>
                <span className="text-muted">
                  {resumenDeSlots(slots, new Set(slots.filter((s) => selected.has(key(dia, s)))))}
                </span>
              </li>
            ))}
          </ul>
        </div>
      </aside>
    </div>
  );
}

const TIPOS_DIA: { value: DiaExcepcionalTipo | "NORMAL"; label: string }[] = [
  { value: "NORMAL", label: "Normal" },
  { value: "HORARIO_REDUCIDO", label: "Horario reducido" },
  { value: "FERIADO", label: "Feriado" },
  { value: "ASUETO", label: "Asueto" },
];

function labelTipo(tipo: DiaExcepcionalTipo | "NORMAL"): string {
  return tipo === "NORMAL" ? "Normal" : DIA_EXCEPCIONAL_TIPO_LABELS[tipo];
}

function toIso(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

const DOW = ["L", "M", "M", "J", "V", "S", "D"];

function MiniCalendar({
  monthDate, onMonthChange, selectedDate, onSelectDate, markers,
}: {
  monthDate: Date;
  onMonthChange: (d: Date) => void;
  selectedDate: string;
  onSelectDate: (iso: string) => void;
  markers: Record<string, string>;
}) {
  const year = monthDate.getFullYear();
  const month = monthDate.getMonth();
  const firstOfMonth = new Date(year, month, 1);
  const startOffset = (firstOfMonth.getDay() + 6) % 7; // lunes-first
  const daysInMonth = new Date(year, month + 1, 0).getDate();

  const cells: (Date | null)[] = [];
  for (let i = 0; i < startOffset; i++) cells.push(null);
  for (let d = 1; d <= daysInMonth; d++) cells.push(new Date(year, month, d));
  while (cells.length % 7 !== 0) cells.push(null);

  const todayIso = toIso(new Date());
  const tituloMes = monthDate
    .toLocaleDateString("es-AR", { month: "long", year: "numeric" })
    .replace(/^\w/, (c) => c.toUpperCase());

  return (
    <div className="calendar">
      <div className="calendar-header">
        <button type="button" className="btn btn-ghost btn-sm" onClick={() => onMonthChange(new Date(year, month - 1, 1))}>
          ‹
        </button>
        <strong>{tituloMes}</strong>
        <button type="button" className="btn btn-ghost btn-sm" onClick={() => onMonthChange(new Date(year, month + 1, 1))}>
          ›
        </button>
      </div>
      <div className="calendar-grid">
        {DOW.map((d, i) => (
          <div key={i} className="calendar-dow">
            {d}
          </div>
        ))}
        {cells.map((date, i) => {
          if (!date) return <div key={i} className="calendar-cell calendar-cell-empty" />;
          const iso = toIso(date);
          const tipo = markers[iso];
          return (
            <button
              type="button"
              key={i}
              className={
                "calendar-cell" +
                (iso === selectedDate ? " calendar-cell-selected" : "") +
                (iso === todayIso ? " calendar-cell-today" : "") +
                (tipo ? " calendar-cell-marked calendar-cell-" + tipo.toLowerCase() : "")
              }
              title={tipo ? labelTipo(tipo as DiaExcepcionalTipo) : undefined}
              onClick={() => onSelectDate(iso)}
            >
              {date.getDate()}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function ExceptionsEditor({ canEdit }: { canEdit: boolean }) {
  const [selectedDate, setSelectedDate] = useState(toIso(new Date()));
  const [monthDate, setMonthDate] = useState(() => new Date());
  const [dia, setDia] = useState<GrillaDia | null>(null);
  const [slots, setSlots] = useState<string[]>([]);
  const [proximos, setProximos] = useState<DiaExcepcional[] | null>(null);
  const [markers, setMarkers] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [rangeDesde, setRangeDesde] = useState("");
  const [rangeHasta, setRangeHasta] = useState("");
  const painting = useRef(false);
  const addMode = useRef(true);

  async function loadDia(fecha: string) {
    setError(null);
    try {
      const data = await api.get<GrillaDias>(`/api/core/dias-excepcionales/grilla/?desde=${fecha}&hasta=${fecha}`);
      setSlots(data.slots);
      setDia(data.dias[0]);
      if (data.slots.length) {
        setRangeDesde(data.slots[0]);
        setRangeHasta(addMinutes(data.slots[data.slots.length - 1], 30));
      }
    } catch {
      setError("No se pudo cargar ese día.");
    }
  }

  async function loadProximosYMarcadores() {
    const data = await api.get<Paginated<DiaExcepcional>>("/api/core/dias-excepcionales/");
    const hoy = toIso(new Date());
    setProximos(data.results.filter((d) => d.fecha >= hoy).sort((a, b) => a.fecha.localeCompare(b.fecha)));
    const m: Record<string, string> = {};
    data.results.forEach((d) => {
      m[d.fecha] = d.tipo;
    });
    setMarkers(m);
  }

  useEffect(() => {
    loadDia(selectedDate);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedDate]);

  useEffect(() => {
    (async () => {
      // Se actualiza el catálogo compartido de feriados (año actual +
      // siguiente) cada vez que se entra a esta sección — no en cada
      // request de la grilla, porque pega a una API externa. Si falla
      // (sin permiso, sin red) seguimos con lo que ya haya cargado.
      try {
        await api.post("/api/core/dias-excepcionales/sincronizar-feriados/");
      } catch {
        // noop
      }
      await loadProximosYMarcadores();
      await loadDia(selectedDate);
    })();
    const onUp = () => {
      painting.current = false;
    };
    window.addEventListener("mouseup", onUp);
    return () => window.removeEventListener("mouseup", onUp);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function actualizarDia(cambios: Partial<GrillaDia>) {
    setDia((prev) => prev && { ...prev, ...cambios });
  }

  function handleMouseDown(slot: string) {
    if (!canEdit || !dia || dia.tipo === "FERIADO" || dia.tipo === "ASUETO") return;
    const willAdd = !dia.celdas.includes(slot);
    addMode.current = willAdd;
    painting.current = true;
    const set = new Set(dia.celdas);
    willAdd ? set.add(slot) : set.delete(slot);
    actualizarDia({ celdas: Array.from(set) });
  }

  function handleMouseEnter(slot: string) {
    if (!canEdit || !painting.current || !dia || dia.tipo === "FERIADO" || dia.tipo === "ASUETO") return;
    const set = new Set(dia.celdas);
    addMode.current ? set.add(slot) : set.delete(slot);
    actualizarDia({ celdas: Array.from(set) });
  }

  function aplicarRango(valor: boolean) {
    if (!dia || !rangeDesde || !rangeHasta) return;
    // "Marcar horario" reemplaza el horario reducido de este día por
    // exactamente el rango elegido (no suma) — ver mismo comentario en
    // WeeklyGrid.aplicarRango.
    const set = valor ? new Set<string>() : new Set(dia.celdas);
    slots.forEach((s) => {
      const fin = addMinutes(s, 30);
      if (s >= rangeDesde && fin <= rangeHasta) {
        if (valor) set.add(s);
        else set.delete(s);
      }
    });
    actualizarDia({ celdas: Array.from(set) });
  }

  async function guardar() {
    if (!dia) return;
    setSaving(true);
    setError(null);
    try {
      await api.post("/api/core/dias-excepcionales/grilla/", {
        dias: { [selectedDate]: { tipo: dia.tipo, celdas: dia.celdas, descripcion: dia.descripcion } },
      });
      await loadDia(selectedDate);
      await loadProximosYMarcadores();
    } catch (err) {
      setError(err instanceof ApiError && err.data ? JSON.stringify(err.data) : "No se pudo guardar.");
    } finally {
      setSaving(false);
    }
  }

  async function eliminar(d: DiaExcepcional) {
    if (d.organization === null) return; // catálogo compartido, no se borra desde acá
    if (!confirm(`¿Eliminar la excepción del ${d.fecha}?`)) return;
    await api.delete(`/api/core/dias-excepcionales/${d.id}/`);
    await loadProximosYMarcadores();
    if (d.fecha === selectedDate) await loadDia(selectedDate);
  }

  const cerrado = dia?.tipo === "FERIADO" || dia?.tipo === "ASUETO";

  return (
    <div className="hours-layout">
      <div className="card hours-main">
        <p className="text-muted">
          Los feriados nacionales se sincronizan automáticamente (catálogo compartido). Elegí un día específico
          (acá o en el almanaque) para cargarle un feriado, asueto u horario reducido propio de tu organización —
          pisa el horario semanal sólo para esa fecha puntual.
        </p>
        <label className="inline-label">
          Día <input type="date" value={selectedDate} onChange={(e) => setSelectedDate(e.target.value)} />
        </label>
        {error && <div className="form-error">{error}</div>}

        {dia && (
          <>
            {canEdit && (
              <div className="toolbar">
                <button className="btn btn-primary" onClick={guardar} disabled={saving}>
                  {saving ? "Guardando…" : "Guardar"}
                </button>
              </div>
            )}
            {dia.compartido && (
              <div className="hint-box">
                Este día es <strong>{labelTipo(dia.tipo)}</strong> según el catálogo nacional
                {dia.descripcion && (
                  <>
                    : <strong>{dia.descripcion}</strong>
                  </>
                )}
                . Si lo modificás y guardás, queda como una excepción propia de tu organización para esta fecha.
              </div>
            )}
            <div className="field-label">Tipo de día</div>
            <div className="button-group">
              {TIPOS_DIA.map((t) => (
                <button
                  key={t.value}
                  type="button"
                  disabled={!canEdit}
                  className={"btn-toggle" + (dia.tipo === t.value ? " btn-toggle-active" : "")}
                  onClick={() =>
                    actualizarDia({ tipo: t.value, celdas: t.value === "HORARIO_REDUCIDO" ? dia.celdas : [] })
                  }
                >
                  {t.label}
                </button>
              ))}
            </div>

            {dia.tipo !== "NORMAL" && (
              <label>
                Descripción
                <input
                  disabled={!canEdit}
                  placeholder="Ej: Aniversario, Feriado puente, etc."
                  value={dia.descripcion}
                  onChange={(e) => actualizarDia({ descripcion: e.target.value })}
                />
              </label>
            )}

            {dia.tipo === "HORARIO_REDUCIDO" && (
              <>
                {canEdit && (
                  <div className="range-selector">
                    <label>
                      Desde
                      <select value={rangeDesde} onChange={(e) => setRangeDesde(e.target.value)}>
                        {slots.map((s) => (
                          <option key={s} value={s}>
                            {s}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label>
                      Hasta
                      <select value={rangeHasta} onChange={(e) => setRangeHasta(e.target.value)}>
                        {slots.map((s) => {
                          const fin = addMinutes(s, 30);
                          return (
                            <option key={fin} value={fin}>
                              {fin}
                            </option>
                          );
                        })}
                      </select>
                    </label>
                    <div className="toolbar">
                      <button className="btn btn-primary btn-sm" type="button" onClick={() => aplicarRango(true)}>
                        Marcar horario
                      </button>
                      <button className="btn btn-ghost btn-sm" type="button" onClick={() => aplicarRango(false)}>
                        Marcar cerrado
                      </button>
                    </div>
                    <span className="text-muted field-help">
                      "Marcar horario" reemplaza todo el horario reducido de este día por este rango (para
                      reducirlo, elegí el rango más chico). "Marcar cerrado" sólo cierra este tramo puntual.
                    </span>
                  </div>
                )}
                <div className="grid-scroll">
                <table className="grilla-horarios grilla-horarios-vertical">
                  <tbody>
                    {slots.map((slot) => {
                      const isSel = dia.celdas.includes(slot);
                      return (
                        <tr key={slot} className={slot.endsWith(":00") ? "hora-en-punto" : undefined}>
                          <td className="grilla-hora">{slot}</td>
                          <td>
                            <div
                              className={"celda-horario" + (isSel ? " celda-seleccionada" : "")}
                              onMouseDown={() => handleMouseDown(slot)}
                              onMouseEnter={() => handleMouseEnter(slot)}
                            />
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
                </div>
              </>
            )}

            {cerrado && <p className="text-muted">Este día queda cerrado todo el día (sin horario de atención).</p>}
          </>
        )}
      </div>

      <aside className="hours-side">
        <div className="card">
          <MiniCalendar
            monthDate={monthDate}
            onMonthChange={setMonthDate}
            selectedDate={selectedDate}
            onSelectDate={setSelectedDate}
            markers={markers}
          />
        </div>
        <div className="card">
          <h3 className="section-title-sm">Próximos días no laborables</h3>
          <ul className="upcoming-list">
            {(proximos ?? []).map((d) => (
              <li key={d.id} className="upcoming-item">
                <div>
                  <strong>{d.fecha}</strong> — {DIA_EXCEPCIONAL_TIPO_LABELS[d.tipo]}
                  {d.organization === null && <span className="badge">catálogo</span>}
                  {d.descripcion && <div className="text-muted small">{d.descripcion}</div>}
                </div>
                <div className="upcoming-actions">
                  <button className="btn btn-ghost btn-sm" onClick={() => setSelectedDate(d.fecha)}>
                    Ver
                  </button>
                  {canEdit && d.organization !== null && (
                    <button className="btn btn-ghost btn-sm btn-danger" onClick={() => eliminar(d)}>
                      Eliminar
                    </button>
                  )}
                </div>
              </li>
            ))}
            {(proximos ?? []).length === 0 && <li className="text-muted">No hay días excepcionales próximos.</li>}
          </ul>
        </div>
      </aside>
    </div>
  );
}
