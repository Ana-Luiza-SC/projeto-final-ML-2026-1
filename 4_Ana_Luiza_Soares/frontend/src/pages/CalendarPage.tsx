import { useEffect, useMemo, useState } from "react";
import {
  cancelCalendarEvent,
  completeCalendarEvent,
  confirmCalendarPreview,
  confirmWeeklyPlan,
  createCalendarEvent,
  createWeeklyPlanPreview,
  listCalendarEvents,
  listDisciplines,
  previewCalendarExtraction,
} from "../api/client";
import type { AcademicEvent, CalendarDraftEvent, CalendarEventType, Discipline, PlannedStudyBlockPreview, RecurrenceRule, StudyPlanDay, WeeklyAvailabilityWindow, WeeklyPlanPreview } from "../types";

const EVENT_TYPES: { value: CalendarEventType; label: string }[] = [
  { value: "exam", label: "Prova" },
  { value: "assignment", label: "Trabalho" },
  { value: "presentation", label: "Apresentacao" },
  { value: "activity", label: "Atividade" },
  { value: "deadline", label: "Prazo" },
  { value: "study_block", label: "Estudo planejado" },
  { value: "other", label: "Outro" },
];
const WEEKDAYS: { value: StudyPlanDay; label: string }[] = [
  { value: "monday", label: "Seg" }, { value: "tuesday", label: "Ter" }, { value: "wednesday", label: "Qua" }, { value: "thursday", label: "Qui" }, { value: "friday", label: "Sex" }, { value: "saturday", label: "Sab" }, { value: "sunday", label: "Dom" },
];

function pad(value: number) { return String(value).padStart(2, "0"); }
function isoDate(date: Date) { return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`; }
function monthStart(date: Date) { return new Date(date.getFullYear(), date.getMonth(), 1); }
function monthEnd(date: Date) { return new Date(date.getFullYear(), date.getMonth() + 1, 0); }
function startOfWeek(date: Date) { const copy = new Date(date); const diff = (copy.getDay() + 6) % 7; copy.setDate(copy.getDate() - diff); return copy; }
function eventDate(event: AcademicEvent) { return event.start_at.slice(0, 10); }
function labelForType(type: CalendarEventType) { return EVENT_TYPES.find((item) => item.value === type)?.label ?? type; }
function timeRange(event: Pick<AcademicEvent, "start_at" | "end_at" | "all_day">) { return event.all_day ? "Dia todo" : `${event.start_at.slice(11, 16)}-${event.end_at?.slice(11, 16) ?? ""}`; }
function sourceLabel(event: AcademicEvent) { if (event.source === "study_plan") return "Estudo"; if (event.source === "assessment") return "Avaliacao"; if (event.source === "course_plan") return "Plano"; return "Manual"; }
function minutesBetween(start: string, end: string) { const [sh, sm] = start.split(":").map(Number); const [eh, em] = end.split(":").map(Number); return (eh * 60 + em) - (sh * 60 + sm); }

export function CalendarPage() {
  const [view, setView] = useState<"month" | "week">("month");
  const [cursor, setCursor] = useState(() => monthStart(new Date()));
  const [disciplines, setDisciplines] = useState<Discipline[]>([]);
  const [events, setEvents] = useState<AcademicEvent[]>([]);
  const [disciplineFilter, setDisciplineFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [selectedEvent, setSelectedEvent] = useState<AcademicEvent | null>(null);
  const [previewDisciplineId, setPreviewDisciplineId] = useState("");
  const [drafts, setDrafts] = useState<CalendarDraftEvent[]>([]);
  const [previewId, setPreviewId] = useState<string | null>(null);
  const [planPreview, setPlanPreview] = useState<WeeklyPlanPreview | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [manualDate, setManualDate] = useState(isoDate(new Date()));
  const [manualTitle, setManualTitle] = useState("");
  const [manualType, setManualType] = useState<CalendarEventType>("other");
  const [recurrenceFrequency, setRecurrenceFrequency] = useState<RecurrenceRule["frequency"]>("none");
  const [recurrenceWeekdays, setRecurrenceWeekdays] = useState<StudyPlanDay[]>(["monday"]);
  const [recurrenceEndMode, setRecurrenceEndMode] = useState<"never" | "on_date" | "after_count">("never");
  const [recurrenceUntil, setRecurrenceUntil] = useState("");
  const [recurrenceCount, setRecurrenceCount] = useState(6);
  const [objectiveText, setObjectiveText] = useState("");
  const [availability, setAvailability] = useState<WeeklyAvailabilityWindow[]>([
    { weekday: "monday", start_time: "18:00", end_time: "20:00", available: true },
    { weekday: "wednesday", start_time: "18:00", end_time: "20:00", available: true },
  ]);

  const range = useMemo(() => {
    if (view === "week") {
      const start = startOfWeek(cursor);
      const end = new Date(start); end.setDate(start.getDate() + 6);
      return { start, end, startIso: `${isoDate(start)}T00:00:00-03:00`, endIso: `${isoDate(end)}T23:59:59-03:00` };
    }
    const start = monthStart(cursor);
    const end = monthEnd(cursor);
    return { start, end, startIso: `${isoDate(start)}T00:00:00-03:00`, endIso: `${isoDate(end)}T23:59:59-03:00` };
  }, [cursor, view]);

  const weekDays = useMemo(() => Array.from({ length: 7 }, (_, index) => { const day = new Date(startOfWeek(cursor)); day.setDate(day.getDate() + index); return day; }), [cursor]);
  const weeklyTotal = useMemo(() => availability.filter((item) => item.available !== false).reduce((total, item) => total + Math.max(0, minutesBetween(item.start_time, item.end_time)), 0), [availability]);

  async function refresh() {
    setLoading(true); setMessage(null);
    try {
      const [disciplinesData, eventData] = await Promise.all([
        listDisciplines(),
        listCalendarEvents({ start_at: range.startIso, end_at: range.endIso, discipline_id: disciplineFilter || undefined, event_type: (typeFilter || undefined) as CalendarEventType | undefined }),
      ]);
      setDisciplines(disciplinesData); setEvents(eventData);
      if (!previewDisciplineId && disciplinesData[0]) setPreviewDisciplineId(disciplinesData[0].id);
    } catch (error) { setMessage(error instanceof Error ? error.message : "Erro ao carregar calendario."); }
    finally { setLoading(false); }
  }
  useEffect(() => { void refresh(); }, [range.startIso, range.endIso, disciplineFilter, typeFilter]);

  const weeks = useMemo(() => {
    const first = monthStart(cursor); const gridStart = new Date(first); gridStart.setDate(first.getDate() - ((first.getDay() + 6) % 7));
    return Array.from({ length: 42 }, (_, index) => { const day = new Date(gridStart); day.setDate(gridStart.getDate() + index); return day; });
  }, [cursor]);
  const eventsByDate = useMemo(() => {
    const map = new Map<string, AcademicEvent[]>();
    for (const event of events) map.set(eventDate(event), [...(map.get(eventDate(event)) ?? []), event]);
    return map;
  }, [events]);

  function recurrencePayload(): RecurrenceRule | null {
    if (recurrenceFrequency === "none") return null;
    const weekly = recurrenceFrequency === "weekly" || recurrenceFrequency === "biweekly" || recurrenceFrequency === "custom_weekly";
    return { frequency: recurrenceFrequency, interval: recurrenceFrequency === "biweekly" ? 2 : 1, weekdays: weekly ? recurrenceWeekdays : [], ends: { mode: recurrenceEndMode, until: recurrenceEndMode === "on_date" ? recurrenceUntil : null, count: recurrenceEndMode === "after_count" ? recurrenceCount : null } };
  }

  async function handleCreateManual() {
    if (!manualTitle.trim()) { setMessage("Informe um titulo para o evento manual."); return; }
    await createCalendarEvent({ discipline_id: disciplineFilter || null, title: manualTitle, event_type: manualType, start_at: `${manualDate}T00:00:00-03:00`, all_day: true, timezone: "America/Sao_Paulo", recurrence: recurrencePayload() });
    setManualTitle(""); setMessage("Evento manual criado."); await refresh();
  }
  async function handlePreviewExtraction() {
    if (!previewDisciplineId) return; setLoading(true); setMessage(null);
    try { const preview = await previewCalendarExtraction(previewDisciplineId); setPreviewId(preview.preview_id); setDrafts(preview.draft_events); setMessage(preview.warnings[0] ?? `${preview.draft_events.length} rascunho(s) extraido(s) para revisao.`); }
    catch (error) { setMessage(error instanceof Error ? error.message : "Nao foi possivel extrair eventos."); }
    finally { setLoading(false); }
  }
  async function handleConfirmPreview() {
    if (!previewId || !previewDisciplineId) return;
    const result = await confirmCalendarPreview(previewDisciplineId, previewId, drafts);
    setPreviewId(null); setDrafts([]); setMessage(`${result.created_count} evento(s) confirmado(s). ${result.skipped_events.length} ignorado(s).`); await refresh();
  }
  async function handleWeeklyPreview() {
    setLoading(true); setMessage(null);
    try { const result = await createWeeklyPlanPreview({ week_start: isoDate(startOfWeek(cursor)), windows: availability, objective_text: objectiveText || null }); setPlanPreview(result); setMessage(`${result.planned_blocks.length} bloco(s) planejado(s) para revisao.`); }
    catch (error) { setMessage(error instanceof Error ? error.message : "Nao foi possivel gerar o planejamento."); }
    finally { setLoading(false); }
  }
  async function handleConfirmWeeklyPlan() {
    if (!planPreview) return;
    const result = await confirmWeeklyPlan(planPreview.study_plan_id);
    setMessage(`${result.created_count} bloco(s) persistido(s) no calendario.`); setPlanPreview(null); await refresh();
  }
  function updateWindow(index: number, patch: Partial<WeeklyAvailabilityWindow>) { setAvailability((items) => items.map((item, i) => i === index ? { ...item, ...patch } : item)); }

  return (
    <section className="page-stack calendar-page">
      <div className="page-header">
        <div><p className="eyebrow">Calendario academico</p><h1>Calendario</h1><p>Eventos, recorrencias e blocos planejados aparecem nas visoes de mes e semana apos confirmacao.</p></div>
        <div className="button-row"><button className={view === "month" ? "primary-button" : "secondary-button"} onClick={() => setView("month")}>Mes</button><button className={view === "week" ? "primary-button" : "secondary-button"} onClick={() => setView("week")}>Semana</button></div>
      </div>
      {message && <div className="status-card">{message}</div>}
      <div className="calendar-toolbar card">
        <button className="secondary-button" onClick={() => setCursor(view === "month" ? new Date(cursor.getFullYear(), cursor.getMonth() - 1, 1) : new Date(cursor.getFullYear(), cursor.getMonth(), cursor.getDate() - 7))}>Anterior</button>
        <strong>{view === "month" ? cursor.toLocaleDateString("pt-BR", { month: "long", year: "numeric" }) : `${isoDate(range.start)} a ${isoDate(range.end)}`}</strong>
        <button className="secondary-button" onClick={() => setCursor(view === "month" ? new Date(cursor.getFullYear(), cursor.getMonth() + 1, 1) : new Date(cursor.getFullYear(), cursor.getMonth(), cursor.getDate() + 7))}>Proximo</button>
        <select value={disciplineFilter} onChange={(event) => setDisciplineFilter(event.target.value)}><option value="">Todas as disciplinas</option>{disciplines.map((discipline) => <option key={discipline.id} value={discipline.id}>{discipline.code} · {discipline.name}</option>)}</select>
        <select value={typeFilter} onChange={(event) => setTypeFilter(event.target.value)}><option value="">Todos os tipos</option>{EVENT_TYPES.map((type) => <option key={type.value} value={type.value}>{type.label}</option>)}</select>
      </div>

      {view === "month" ? <div className="calendar-grid">
        {WEEKDAYS.map((day) => <strong key={day.value} className="calendar-weekday">{day.label}</strong>)}
        {weeks.map((day) => { const key = isoDate(day); const dayEvents = eventsByDate.get(key) ?? []; return <div key={key} className={`calendar-day ${day.getMonth() !== cursor.getMonth() ? "muted" : ""}`}><span className="calendar-date">{day.getDate()}</span>{dayEvents.slice(0, 3).map((event) => <button key={event.occurrence_id ?? event.id} className={`event-pill ${event.event_type} ${event.status}`} onClick={() => setSelectedEvent(event)}><span>{sourceLabel(event)}</span> {event.title}</button>)}{dayEvents.length > 3 && <small>+{dayEvents.length - 3} evento(s)</small>}</div>; })}
      </div> : <div className="weekly-agenda week-calendar-view">
        {weekDays.map((day) => { const key = isoDate(day); const dayEvents = (eventsByDate.get(key) ?? []).sort((a, b) => a.start_at.localeCompare(b.start_at)); return <div key={key} className="week-column"><strong>{day.toLocaleDateString("pt-BR", { weekday: "short", day: "2-digit", month: "2-digit" })}</strong>{dayEvents.map((event) => <button key={event.occurrence_id ?? event.id} className={`event-pill ${event.event_type} ${event.status}`} onClick={() => setSelectedEvent(event)}><span>{timeRange(event)}</span> {event.title}</button>)}{!dayEvents.length && <small>Sem eventos.</small>}</div>; })}
      </div>}

      <div className="two-column">
        <div className="card form-card">
          <h2>Criar evento manual</h2>
          <label>Titulo<input value={manualTitle} onChange={(event) => setManualTitle(event.target.value)} placeholder="Ex.: grupo de estudo" /></label>
          <label>Data<input type="date" value={manualDate} onChange={(event) => setManualDate(event.target.value)} /></label>
          <label>Tipo<select value={manualType} onChange={(event) => setManualType(event.target.value as CalendarEventType)}>{EVENT_TYPES.filter((type) => type.value !== "study_block").map((type) => <option key={type.value} value={type.value}>{type.label}</option>)}</select></label>
          <label>Recorrencia<select value={recurrenceFrequency} onChange={(event) => setRecurrenceFrequency(event.target.value as RecurrenceRule["frequency"])}><option value="none">Nao repete</option><option value="daily">Diaria</option><option value="weekly">Semanal</option><option value="biweekly">A cada duas semanas</option><option value="monthly">Mensal</option><option value="yearly">Anual</option><option value="custom_weekly">Semanal personalizada</option></select></label>
          {recurrenceFrequency !== "none" && <><div className="weekday-picker">{WEEKDAYS.map((day) => <label key={day.value}><input type="checkbox" checked={recurrenceWeekdays.includes(day.value)} onChange={(event) => setRecurrenceWeekdays((items) => event.target.checked ? [...items, day.value] : items.filter((item) => item !== day.value))} /> {day.label}</label>)}</div><label>Termino<select value={recurrenceEndMode} onChange={(event) => setRecurrenceEndMode(event.target.value as "never" | "on_date" | "after_count")}><option value="never">Nunca</option><option value="on_date">Em uma data</option><option value="after_count">Apos ocorrencias</option></select></label>{recurrenceEndMode === "on_date" && <input type="date" value={recurrenceUntil} onChange={(event) => setRecurrenceUntil(event.target.value)} />}{recurrenceEndMode === "after_count" && <input type="number" min="1" max="500" value={recurrenceCount} onChange={(event) => setRecurrenceCount(Number(event.target.value))} />}</>}
          <button className="primary-button" onClick={() => void handleCreateManual()}>Criar evento</button>
        </div>

        <div className="card form-card">
          <h2>Planejamento semanal</h2>
          <p className="muted">Total calculado: {Math.floor(weeklyTotal / 60)}h{weeklyTotal % 60 ? ` ${weeklyTotal % 60}min` : ""}</p>
          {availability.map((window, index) => <div key={index} className="draft-card"><select value={window.weekday} onChange={(event) => updateWindow(index, { weekday: event.target.value as StudyPlanDay })}>{WEEKDAYS.map((day) => <option key={day.value} value={day.value}>{day.label}</option>)}</select><input type="time" value={window.start_time} onChange={(event) => updateWindow(index, { start_time: event.target.value })} /><input type="time" value={window.end_time} onChange={(event) => updateWindow(index, { end_time: event.target.value })} /><label><input type="checkbox" checked={window.available !== false} onChange={(event) => updateWindow(index, { available: event.target.checked })} /> Disponivel</label><button className="secondary-button" onClick={() => setAvailability((items) => items.filter((_, i) => i !== index))}>Remover</button></div>)}
          <button className="secondary-button" onClick={() => setAvailability((items) => [...items, { weekday: "friday", start_time: "18:00", end_time: "20:00", available: true }])}>Adicionar janela</button>
          <label>Objetivo opcional<textarea value={objectiveText} onChange={(event) => setObjectiveText(event.target.value)} /></label>
          <button className="primary-button" disabled={loading || weeklyTotal < 30} onClick={() => void handleWeeklyPreview()}>Gerar preview</button>
        </div>
      </div>

      {planPreview && <div className="card"><h2>Preview do plano</h2><div className="draft-list">{planPreview.planned_blocks.map((block: PlannedStudyBlockPreview) => <div key={block.temporary_id} className="draft-card"><strong>{block.title}</strong><small>{block.start_at.slice(0, 16).replace("T", " ")} - {block.end_at.slice(11, 16)} · prioridade {block.priority_score}</small><small>{block.reason}</small></div>)}</div>{planPreview.unallocated_priorities.map((item) => <p key={item.discipline_id} className="warning-text">Sem capacidade: {item.discipline_code ?? item.discipline_name}</p>)}{planPreview.conflicts.map((item) => <p key={item} className="warning-text">Conflito: {item}</p>)}<div className="button-row"><button className="primary-button" onClick={() => void handleConfirmWeeklyPlan()}>Confirmar blocos</button><button className="secondary-button" onClick={() => setPlanPreview(null)}>Cancelar</button></div></div>}

      <div className="card form-card"><h2>Extrair eventos do plano</h2><p>Selecione uma disciplina com plano confirmado. A extracao gera preview editavel e nao salva automaticamente.</p><select value={previewDisciplineId} onChange={(event) => setPreviewDisciplineId(event.target.value)}>{disciplines.map((discipline) => <option key={discipline.id} value={discipline.id}>{discipline.code} · {discipline.name}</option>)}</select><button className="secondary-button" disabled={loading || !previewDisciplineId} onClick={() => void handlePreviewExtraction()}>Extrair eventos do plano de ensino</button></div>
      {drafts.length > 0 && <div className="card"><h2>Preview de eventos extraidos</h2><div className="draft-list">{drafts.map((draft, index) => <div key={draft.temporary_id} className="draft-card"><input value={draft.title} onChange={(event) => setDrafts((items) => items.map((item, i) => i === index ? { ...item, title: event.target.value } : item))} /><select value={draft.event_type} onChange={(event) => setDrafts((items) => items.map((item, i) => i === index ? { ...item, event_type: event.target.value as CalendarEventType } : item))}>{EVENT_TYPES.filter((type) => type.value !== "study_block").map((type) => <option key={type.value} value={type.value}>{type.label}</option>)}</select><input type="date" value={draft.start_at?.slice(0, 10) ?? ""} onChange={(event) => setDrafts((items) => items.map((item, i) => i === index ? { ...item, start_at: event.target.value ? `${event.target.value}T00:00:00-03:00` : null, ambiguous: !event.target.value } : item))} /><small>Evidencia: {draft.source_evidence}</small><button className="secondary-button" onClick={() => setDrafts((items) => items.filter((_, i) => i !== index))}>Remover</button></div>)}</div><div className="button-row"><button className="primary-button" onClick={() => void handleConfirmPreview()}>Confirmar preview</button><button className="secondary-button" onClick={() => { setDrafts([]); setPreviewId(null); }}>Cancelar</button></div></div>}

      {selectedEvent && <div className="card event-detail"><h2>{selectedEvent.title}</h2><p>{labelForType(selectedEvent.event_type)} · {selectedEvent.status} · {sourceLabel(selectedEvent)}</p><p>{timeRange(selectedEvent)} · {new Date(selectedEvent.start_at).toLocaleString("pt-BR")}</p>{selectedEvent.priority_reason && <p>Prioridade: {selectedEvent.priority_score} · {selectedEvent.priority_reason}</p>}{selectedEvent.source_evidence && <p>Evidencia: {selectedEvent.source_evidence}</p>}<div className="button-row"><button className="secondary-button" onClick={() => void completeCalendarEvent(selectedEvent.id).then(refresh)}>Concluir</button><button className="secondary-button" onClick={() => void cancelCalendarEvent(selectedEvent.id).then(refresh)}>Cancelar</button><button className="secondary-button" onClick={() => setSelectedEvent(null)}>Fechar</button></div></div>}
    </section>
  );
}
