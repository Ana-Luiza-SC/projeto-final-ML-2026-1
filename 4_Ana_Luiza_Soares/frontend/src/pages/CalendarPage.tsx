import { useEffect, useMemo, useState } from "react";
import {
  cancelCalendarEvent,
  completeCalendarEvent,
  confirmCalendarPreview,
  createCalendarEvent,
  createStudyPlan,
  listCalendarEvents,
  listDisciplines,
  previewCalendarExtraction,
} from "../api/client";
import type { AcademicEvent, CalendarDraftEvent, CalendarEventType, Discipline, StudyPlanResponse } from "../types";

const EVENT_TYPES: { value: CalendarEventType; label: string }[] = [
  { value: "exam", label: "Prova" },
  { value: "assignment", label: "Trabalho" },
  { value: "presentation", label: "Apresentação" },
  { value: "activity", label: "Atividade" },
  { value: "deadline", label: "Prazo" },
  { value: "other", label: "Outro" },
];

function pad(value: number) { return String(value).padStart(2, "0"); }
function isoDate(date: Date) { return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`; }
function monthStart(date: Date) { return new Date(date.getFullYear(), date.getMonth(), 1); }
function monthEnd(date: Date) { return new Date(date.getFullYear(), date.getMonth() + 1, 0); }
function eventDate(event: AcademicEvent) { return event.start_at.slice(0, 10); }
function labelForType(type: CalendarEventType) { return EVENT_TYPES.find((item) => item.value === type)?.label ?? type; }
function startOfWeek(date: Date) { const copy = new Date(date); const diff = (copy.getDay() + 6) % 7; copy.setDate(copy.getDate() - diff); return copy; }

export function CalendarPage() {
  const [cursor, setCursor] = useState(() => monthStart(new Date()));
  const [disciplines, setDisciplines] = useState<Discipline[]>([]);
  const [events, setEvents] = useState<AcademicEvent[]>([]);
  const [disciplineFilter, setDisciplineFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [selectedEvent, setSelectedEvent] = useState<AcademicEvent | null>(null);
  const [previewDisciplineId, setPreviewDisciplineId] = useState("");
  const [drafts, setDrafts] = useState<CalendarDraftEvent[]>([]);
  const [previewId, setPreviewId] = useState<string | null>(null);
  const [studyPlan, setStudyPlan] = useState<StudyPlanResponse | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [manualDate, setManualDate] = useState(isoDate(new Date()));
  const [manualTitle, setManualTitle] = useState("");
  const [manualType, setManualType] = useState<CalendarEventType>("other");

  const range = useMemo(() => {
    const start = monthStart(cursor);
    const end = monthEnd(cursor);
    return { start, end, startIso: `${isoDate(start)}T00:00:00-03:00`, endIso: `${isoDate(end)}T23:59:59-03:00` };
  }, [cursor]);

  async function refresh() {
    setLoading(true);
    setMessage(null);
    try {
      const [disciplinesData, eventData] = await Promise.all([
        listDisciplines(),
        listCalendarEvents({ start_at: range.startIso, end_at: range.endIso, discipline_id: disciplineFilter || undefined, event_type: (typeFilter || undefined) as CalendarEventType | undefined }),
      ]);
      setDisciplines(disciplinesData);
      setEvents(eventData);
      if (!previewDisciplineId && disciplinesData[0]) setPreviewDisciplineId(disciplinesData[0].id);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Erro ao carregar calendário.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void refresh(); }, [range.startIso, range.endIso, disciplineFilter, typeFilter]);

  const weeks = useMemo(() => {
    const first = monthStart(cursor);
    const gridStart = new Date(first);
    gridStart.setDate(first.getDate() - ((first.getDay() + 6) % 7));
    return Array.from({ length: 42 }, (_, index) => {
      const day = new Date(gridStart);
      day.setDate(gridStart.getDate() + index);
      return day;
    });
  }, [cursor]);

  const eventsByDate = useMemo(() => {
    const map = new Map<string, AcademicEvent[]>();
    for (const event of events) {
      const key = eventDate(event);
      map.set(key, [...(map.get(key) ?? []), event]);
    }
    return map;
  }, [events]);

  const weekStart = startOfWeek(new Date());
  const weekDays = Array.from({ length: 7 }, (_, index) => { const day = new Date(weekStart); day.setDate(weekStart.getDate() + index); return day; });

  async function handleCreateManual() {
    if (!manualTitle.trim()) { setMessage("Informe um título para o evento manual."); return; }
    await createCalendarEvent({
      discipline_id: disciplineFilter || null,
      title: manualTitle,
      event_type: manualType,
      start_at: `${manualDate}T00:00:00-03:00`,
      all_day: true,
      timezone: "America/Sao_Paulo",
    });
    setManualTitle("");
    setMessage("Evento manual criado.");
    await refresh();
  }

  async function handlePreviewExtraction() {
    if (!previewDisciplineId) return;
    setLoading(true);
    setMessage(null);
    try {
      const preview = await previewCalendarExtraction(previewDisciplineId);
      setPreviewId(preview.preview_id);
      setDrafts(preview.draft_events);
      setMessage(preview.warnings[0] ?? `${preview.draft_events.length} rascunho(s) extraído(s) para revisão.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Não foi possível extrair eventos.");
    } finally { setLoading(false); }
  }

  async function handleConfirmPreview() {
    if (!previewId || !previewDisciplineId) return;
    const result = await confirmCalendarPreview(previewDisciplineId, previewId, drafts);
    setPreviewId(null);
    setDrafts([]);
    setMessage(`${result.created_count} evento(s) confirmado(s). ${result.skipped_events.length} ignorado(s).`);
    await refresh();
  }

  async function handleStudyPlan() {
    if (!disciplines.length) return;
    const result = await createStudyPlan({
      discipline_ids: disciplines.map((item) => item.id),
      availability: {
        available_hours_per_week: 4.5,
        days_available: ["monday", "wednesday", "friday"],
        time_windows: [
          { day: "monday", start_time: "18:00", end_time: "19:30" },
          { day: "wednesday", start_time: "18:00", end_time: "19:30" },
          { day: "friday", start_time: "18:00", end_time: "19:30" },
        ],
      },
      max_session_minutes: 90,
      priorities: [],
      objective_text: "montar agenda semanal respeitando provas e prazos",
    });
    setStudyPlan(result);
  }

  return (
    <section className="page-stack calendar-page">
      <div className="page-header">
        <div>
          <p className="eyebrow">Calendário acadêmico</p>
          <h1>Eventos e agenda semanal</h1>
          <p>Eventos manuais, avaliações sincronizadas e eventos extraídos do plano só entram após confirmação humana.</p>
        </div>
        <button className="primary-button" onClick={() => void handleStudyPlan()}>Gerar agenda semanal</button>
      </div>

      {message && <div className="status-card">{message}</div>}

      <div className="calendar-toolbar card">
        <button className="secondary-button" onClick={() => setCursor(new Date(cursor.getFullYear(), cursor.getMonth() - 1, 1))}>Mês anterior</button>
        <strong>{cursor.toLocaleDateString("pt-BR", { month: "long", year: "numeric" })}</strong>
        <button className="secondary-button" onClick={() => setCursor(new Date(cursor.getFullYear(), cursor.getMonth() + 1, 1))}>Próximo mês</button>
        <select value={disciplineFilter} onChange={(event) => setDisciplineFilter(event.target.value)}>
          <option value="">Todas as disciplinas</option>
          {disciplines.map((discipline) => <option key={discipline.id} value={discipline.id}>{discipline.code} · {discipline.name}</option>)}
        </select>
        <select value={typeFilter} onChange={(event) => setTypeFilter(event.target.value)}>
          <option value="">Todos os tipos</option>
          {EVENT_TYPES.map((type) => <option key={type.value} value={type.value}>{type.label}</option>)}
        </select>
      </div>

      <div className="calendar-grid">
        {["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"].map((day) => <strong key={day} className="calendar-weekday">{day}</strong>)}
        {weeks.map((day) => {
          const key = isoDate(day);
          const dayEvents = eventsByDate.get(key) ?? [];
          return (
            <div key={key} className={`calendar-day ${day.getMonth() !== cursor.getMonth() ? "muted" : ""}`}>
              <span className="calendar-date">{day.getDate()}</span>
              {dayEvents.slice(0, 3).map((event) => (
                <button key={event.id} className={`event-pill ${event.event_type} ${event.status}`} onClick={() => setSelectedEvent(event)}>
                  <span>{labelForType(event.event_type)}</span> {event.title}
                </button>
              ))}
              {dayEvents.length > 3 && <small>+{dayEvents.length - 3} evento(s)</small>}
            </div>
          );
        })}
      </div>

      <div className="two-column">
        <div className="card form-card">
          <h2>Criar evento manual</h2>
          <label>Título<input value={manualTitle} onChange={(event) => setManualTitle(event.target.value)} placeholder="Ex.: prazo de lista" /></label>
          <label>Data<input type="date" value={manualDate} onChange={(event) => setManualDate(event.target.value)} /></label>
          <label>Tipo<select value={manualType} onChange={(event) => setManualType(event.target.value as CalendarEventType)}>{EVENT_TYPES.map((type) => <option key={type.value} value={type.value}>{type.label}</option>)}</select></label>
          <button className="primary-button" onClick={() => void handleCreateManual()}>Criar evento</button>
        </div>

        <div className="card form-card">
          <h2>Extrair eventos do plano</h2>
          <p>Selecione uma disciplina com plano confirmado. A extração gera preview editável e não salva automaticamente.</p>
          <select value={previewDisciplineId} onChange={(event) => setPreviewDisciplineId(event.target.value)}>
            {disciplines.map((discipline) => <option key={discipline.id} value={discipline.id}>{discipline.code} · {discipline.name}</option>)}
          </select>
          <button className="secondary-button" disabled={loading || !previewDisciplineId} onClick={() => void handlePreviewExtraction()}>Extrair eventos do plano de ensino</button>
        </div>
      </div>

      {drafts.length > 0 && (
        <div className="card">
          <h2>Preview de eventos extraídos</h2>
          <div className="draft-list">
            {drafts.map((draft, index) => (
              <div key={draft.temporary_id} className="draft-card">
                <input value={draft.title} onChange={(event) => setDrafts((items) => items.map((item, i) => i === index ? { ...item, title: event.target.value } : item))} />
                <select value={draft.event_type} onChange={(event) => setDrafts((items) => items.map((item, i) => i === index ? { ...item, event_type: event.target.value as CalendarEventType } : item))}>{EVENT_TYPES.map((type) => <option key={type.value} value={type.value}>{type.label}</option>)}</select>
                <input type="date" value={draft.start_at?.slice(0, 10) ?? ""} onChange={(event) => setDrafts((items) => items.map((item, i) => i === index ? { ...item, start_at: event.target.value ? `${event.target.value}T00:00:00-03:00` : null, ambiguous: !event.target.value } : item))} />
                <input type="number" min="0" max="100" value={draft.weight ?? ""} onChange={(event) => setDrafts((items) => items.map((item, i) => i === index ? { ...item, weight: event.target.value ? Number(event.target.value) : null } : item))} placeholder="Peso" />
                <small>Evidência: {draft.source_evidence} · confiança {Math.round(draft.confidence * 100)}%</small>
                {draft.warnings.map((warning) => <small key={warning} className="warning-text">{warning}</small>)}
                <button className="secondary-button" onClick={() => setDrafts((items) => items.filter((_, i) => i !== index))}>Remover</button>
              </div>
            ))}
          </div>
          <div className="button-row"><button className="primary-button" onClick={() => void handleConfirmPreview()}>Confirmar preview</button><button className="secondary-button" onClick={() => { setDrafts([]); setPreviewId(null); }}>Cancelar</button></div>
        </div>
      )}

      <div className="card">
        <h2>Agenda semanal</h2>
        <div className="weekly-agenda">
          {weekDays.map((day) => {
            const key = isoDate(day);
            const dayEvents = events.filter((event) => eventDate(event) === key);
            const sessions = studyPlan?.plan.filter((session) => session.scheduled_date === key) ?? [];
            return (
              <div key={key} className="week-column">
                <strong>{day.toLocaleDateString("pt-BR", { weekday: "short", day: "2-digit", month: "2-digit" })}</strong>
                {dayEvents.map((event) => <p key={event.id} className="agenda-event">Evento: {event.title} · {event.discipline_code ?? "sem disciplina"}</p>)}
                {sessions.map((session) => <p key={`${session.day}-${session.sequence}`} className="agenda-study">Estudo: {session.discipline_code} · {session.duration_minutes} min · {session.activity}{session.assessment_name ? ` · prepara ${session.assessment_name}` : ""}</p>)}
                {!dayEvents.length && !sessions.length && <small>Sem itens.</small>}
              </div>
            );
          })}
        </div>
        {studyPlan?.warnings.map((warning) => <p key={warning} className="warning-text">Pendente/guardrail: {warning}</p>)}
      </div>

      {selectedEvent && (
        <div className="card event-detail">
          <h2>{selectedEvent.title}</h2>
          <p>{labelForType(selectedEvent.event_type)} · {selectedEvent.status} · {selectedEvent.source}</p>
          <p>{new Date(selectedEvent.start_at).toLocaleString("pt-BR")}</p>
          {selectedEvent.source_evidence && <p>Evidência: {selectedEvent.source_evidence}</p>}
          <div className="button-row">
            <button className="secondary-button" onClick={() => void completeCalendarEvent(selectedEvent.id).then(refresh)}>Concluir</button>
            <button className="secondary-button" onClick={() => void cancelCalendarEvent(selectedEvent.id).then(refresh)}>Cancelar</button>
            <button className="secondary-button" onClick={() => setSelectedEvent(null)}>Fechar</button>
          </div>
        </div>
      )}
    </section>
  );
}
