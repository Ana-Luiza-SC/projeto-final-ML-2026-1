import { useEffect, useMemo, useState, type CSSProperties } from "react";
import {
  cancelCalendarEvent,
  completeCalendarEvent,
  confirmCalendarPreview,
  createCalendarEvent,
  listCalendarEvents,
  listDisciplines,
  previewCalendarExtraction,
} from "../api/client";
import type {
  AcademicEvent,
  CalendarDraftEvent,
  CalendarEventType,
  Discipline,
  RecurrenceRule,
  StudyPlanDay,
} from "../types";

const EVENT_TYPES: { value: CalendarEventType; label: string }[] = [
  { value: "exam", label: "Prova" },
  { value: "assignment", label: "Trabalho" },
  { value: "presentation", label: "Apresentação" },
  { value: "activity", label: "Atividade" },
  { value: "deadline", label: "Prazo" },
  { value: "study_block", label: "Estudo planejado" },
  { value: "other", label: "Outro" },
];

const WEEKDAYS: { value: StudyPlanDay; label: string }[] = [
  { value: "monday", label: "Seg" },
  { value: "tuesday", label: "Ter" },
  { value: "wednesday", label: "Qua" },
  { value: "thursday", label: "Qui" },
  { value: "friday", label: "Sex" },
  { value: "saturday", label: "Sáb" },
  { value: "sunday", label: "Dom" },
];

const HOUR_HEIGHT = 56;

function pad(value: number) {
  return String(value).padStart(2, "0");
}

function isoDate(date: Date) {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

function monthStart(date: Date) {
  return new Date(date.getFullYear(), date.getMonth(), 1);
}

function monthEnd(date: Date) {
  return new Date(date.getFullYear(), date.getMonth() + 1, 0);
}

function startOfWeek(date: Date) {
  const copy = new Date(date);
  const offset = (copy.getDay() + 6) % 7;
  copy.setDate(copy.getDate() - offset);
  return copy;
}

function eventDate(event: AcademicEvent) {
  return event.start_at.slice(0, 10);
}

function minutesOfDay(value: string) {
  const hour = Number(value.slice(11, 13));
  const minute = Number(value.slice(14, 16));
  return hour * 60 + minute;
}

function labelForType(type: CalendarEventType) {
  return EVENT_TYPES.find((item) => item.value === type)?.label ?? type;
}

function timeRange(
  event: Pick<AcademicEvent, "start_at" | "end_at" | "all_day">,
) {
  return event.all_day
    ? "Dia todo"
    : `${event.start_at.slice(11, 16)}–${event.end_at?.slice(11, 16) ?? ""}`;
}

function sourceLabel(event: AcademicEvent) {
  if (event.source === "study_plan") return "Estudo";
  if (event.source === "assessment") return "Avaliação";
  if (event.source === "course_plan") return "Plano de ensino";
  return "Manual";
}

function eventKey(event: AcademicEvent) {
  return event.occurrence_id ?? event.id;
}

function laneLayout(events: AcademicEvent[]) {
  const ordered = [...events].sort((a, b) => a.start_at.localeCompare(b.start_at));
  const laneEnds: number[] = [];
  const assigned = ordered.map((event) => {
    const start = minutesOfDay(event.start_at);
    const end = event.end_at ? minutesOfDay(event.end_at) : start + 30;
    let lane = laneEnds.findIndex((laneEnd) => laneEnd <= start);
    if (lane < 0) {
      lane = laneEnds.length;
      laneEnds.push(end);
    } else {
      laneEnds[lane] = end;
    }
    return { event, lane };
  });
  const laneCount = Math.max(1, laneEnds.length);
  return assigned.map((item) => ({ ...item, laneCount }));
}

export function CalendarPage({ onAdjustPlan }: { onAdjustPlan: () => void }) {
  const [view, setView] = useState<"month" | "week">("month");
  const [cursor, setCursor] = useState(() => new Date());
  const [disciplines, setDisciplines] = useState<Discipline[]>([]);
  const [events, setEvents] = useState<AcademicEvent[]>([]);
  const [disciplineFilter, setDisciplineFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [selectedEvent, setSelectedEvent] = useState<AcademicEvent | null>(null);
  const [selectedDay, setSelectedDay] = useState(isoDate(new Date()));
  const [previewDisciplineId, setPreviewDisciplineId] = useState("");
  const [drafts, setDrafts] = useState<CalendarDraftEvent[]>([]);
  const [previewId, setPreviewId] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [manualDate, setManualDate] = useState(isoDate(new Date()));
  const [manualTitle, setManualTitle] = useState("");
  const [manualType, setManualType] = useState<CalendarEventType>("other");
  const [manualAllDay, setManualAllDay] = useState(true);
  const [manualStart, setManualStart] = useState("18:00");
  const [manualEnd, setManualEnd] = useState("19:00");
  const [recurrenceFrequency, setRecurrenceFrequency] =
    useState<RecurrenceRule["frequency"]>("none");
  const [recurrenceWeekdays, setRecurrenceWeekdays] = useState<StudyPlanDay[]>([
    "monday",
  ]);
  const [recurrenceEndMode, setRecurrenceEndMode] = useState<
    "never" | "on_date" | "after_count"
  >("never");
  const [recurrenceUntil, setRecurrenceUntil] = useState("");
  const [recurrenceCount, setRecurrenceCount] = useState(6);

  const range = useMemo(() => {
    if (view === "week") {
      const start = startOfWeek(cursor);
      const end = new Date(start);
      end.setDate(start.getDate() + 6);
      return {
        start,
        end,
        startIso: `${isoDate(start)}T00:00:00-03:00`,
        endIso: `${isoDate(end)}T23:59:59-03:00`,
      };
    }
    const start = monthStart(cursor);
    const end = monthEnd(cursor);
    return {
      start,
      end,
      startIso: `${isoDate(start)}T00:00:00-03:00`,
      endIso: `${isoDate(end)}T23:59:59-03:00`,
    };
  }, [cursor, view]);

  const weekDays = useMemo(
    () =>
      Array.from({ length: 7 }, (_, index) => {
        const day = new Date(startOfWeek(cursor));
        day.setDate(day.getDate() + index);
        return day;
      }),
    [cursor],
  );

  async function refresh() {
    setLoading(true);
    setMessage(null);
    try {
      const [disciplineData, eventData] = await Promise.all([
        listDisciplines(),
        listCalendarEvents({
          start_at: range.startIso,
          end_at: range.endIso,
          discipline_id: disciplineFilter || undefined,
          event_type: (typeFilter || undefined) as CalendarEventType | undefined,
        }),
      ]);
      setDisciplines(disciplineData);
      setEvents(eventData);
      if (!previewDisciplineId && disciplineData[0]) {
        setPreviewDisciplineId(disciplineData[0].id);
      }
    } catch (reason) {
      setMessage(
        reason instanceof Error ? reason.message : "Erro ao carregar o calendário.",
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refresh();
  }, [range.startIso, range.endIso, disciplineFilter, typeFilter]);

  const monthDays = useMemo(() => {
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

  const timedEvents = useMemo(
    () => events.filter((event) => !event.all_day),
    [events],
  );
  const firstHour = useMemo(
    () =>
      Math.max(
        0,
        Math.min(7, ...timedEvents.map((event) => Math.floor(minutesOfDay(event.start_at) / 60))),
      ),
    [timedEvents],
  );
  const lastHour = useMemo(
    () =>
      Math.min(
        24,
        Math.max(
          22,
          ...timedEvents.map((event) =>
            Math.ceil(
              minutesOfDay(event.end_at ?? event.start_at) / 60,
            ),
          ),
        ),
      ),
    [timedEvents],
  );
  const hours = useMemo(
    () => Array.from({ length: lastHour - firstHour + 1 }, (_, index) => firstHour + index),
    [firstHour, lastHour],
  );

  const currentTime = new Date();
  const currentDayKey = isoDate(currentTime);
  const currentMinute = currentTime.getHours() * 60 + currentTime.getMinutes();
  const showCurrentTime =
    view === "week" &&
    currentDayKey >= isoDate(range.start) &&
    currentDayKey <= isoDate(range.end) &&
    currentMinute >= firstHour * 60 &&
    currentMinute <= lastHour * 60;

  function recurrencePayload(): RecurrenceRule | null {
    if (recurrenceFrequency === "none") return null;
    const weekly = ["weekly", "biweekly", "custom_weekly"].includes(
      recurrenceFrequency,
    );
    return {
      frequency: recurrenceFrequency,
      interval: recurrenceFrequency === "biweekly" ? 2 : 1,
      weekdays: weekly ? recurrenceWeekdays : [],
      ends: {
        mode: recurrenceEndMode,
        until: recurrenceEndMode === "on_date" ? recurrenceUntil : null,
        count: recurrenceEndMode === "after_count" ? recurrenceCount : null,
      },
    };
  }

  async function handleCreateManual() {
    if (!manualTitle.trim()) {
      setMessage("Informe um título para o evento manual.");
      return;
    }
    if (!manualAllDay && manualStart >= manualEnd) {
      setMessage("O horário final deve ser posterior ao horário inicial.");
      return;
    }
    if (
      ["weekly", "biweekly", "custom_weekly"].includes(recurrenceFrequency) &&
      recurrenceWeekdays.length === 0
    ) {
      setMessage("Selecione ao menos um dia para a recorrência semanal.");
      return;
    }
    await createCalendarEvent({
      discipline_id: disciplineFilter || null,
      title: manualTitle.trim(),
      event_type: manualType,
      start_at: `${manualDate}T${manualAllDay ? "00:00" : manualStart}:00-03:00`,
      end_at: manualAllDay
        ? null
        : `${manualDate}T${manualEnd}:00-03:00`,
      all_day: manualAllDay,
      timezone: "America/Sao_Paulo",
      recurrence: recurrencePayload(),
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
      setMessage(
        preview.warnings[0] ??
          `${preview.draft_events.length} rascunho(s) extraído(s) para revisão.`,
      );
    } catch (reason) {
      setMessage(
        reason instanceof Error
          ? reason.message
          : "Não foi possível extrair eventos.",
      );
    } finally {
      setLoading(false);
    }
  }

  async function handleConfirmPreview() {
    if (!previewId || !previewDisciplineId) return;
    const result = await confirmCalendarPreview(
      previewDisciplineId,
      previewId,
      drafts,
    );
    setPreviewId(null);
    setDrafts([]);
    setMessage(
      `${result.created_count} evento(s) confirmado(s). ${result.skipped_events.length} ignorado(s).`,
    );
    await refresh();
  }

  function moveCursor(direction: -1 | 1) {
    if (view === "month") {
      setCursor(
        new Date(cursor.getFullYear(), cursor.getMonth() + direction, 1),
      );
    } else {
      const next = new Date(cursor);
      next.setDate(next.getDate() + direction * 7);
      setCursor(next);
    }
  }

  function renderEventButton(event: AcademicEvent, className = "event-pill") {
    return (
      <button
        key={eventKey(event)}
        type="button"
        className={`${className} ${event.event_type} ${event.status}`}
        onClick={() => setSelectedEvent(event)}
        aria-label={`${event.title}, ${timeRange(event)}, ${labelForType(event.event_type)}`}
      >
        <span>{sourceLabel(event)}</span> {event.title}
      </button>
    );
  }

  return (
    <section className="page-stack calendar-page">
      <div className="page-header">
        <div>
          <p className="eyebrow">Calendário acadêmico</p>
          <h1>Calendário</h1>
          <p>Eventos confirmados e blocos planejados nas posições reais de data e hora.</p>
        </div>
        <div className="calendar-header-actions">
          <button className="secondary-button" onClick={onAdjustPlan}>
            Ajustar plano semanal
          </button>
          <div className="segmented-control" aria-label="Visualização do calendário">
            <button
              aria-pressed={view === "month"}
              className={view === "month" ? "active" : ""}
              onClick={() => setView("month")}
            >
              Mês
            </button>
            <button
              aria-pressed={view === "week"}
              className={view === "week" ? "active" : ""}
              onClick={() => setView("week")}
            >
              Semana
            </button>
          </div>
        </div>
      </div>

      {message && <div className="status-card" role="status">{message}</div>}

      <div className="calendar-toolbar">
        <button className="secondary-button" onClick={() => moveCursor(-1)}>
          Anterior
        </button>
        <strong>
          {view === "month"
            ? cursor.toLocaleDateString("pt-BR", {
                month: "long",
                year: "numeric",
              })
            : `${range.start.toLocaleDateString("pt-BR")} a ${range.end.toLocaleDateString("pt-BR")}`}
        </strong>
        <button className="secondary-button" onClick={() => moveCursor(1)}>
          Próximo
        </button>
        <select
          aria-label="Filtrar por disciplina"
          value={disciplineFilter}
          onChange={(event) => setDisciplineFilter(event.target.value)}
        >
          <option value="">Todas as disciplinas</option>
          {disciplines.map((discipline) => (
            <option key={discipline.id} value={discipline.id}>
              {discipline.code} · {discipline.name}
            </option>
          ))}
        </select>
        <select
          aria-label="Filtrar por tipo"
          value={typeFilter}
          onChange={(event) => setTypeFilter(event.target.value)}
        >
          <option value="">Todos os tipos</option>
          {EVENT_TYPES.map((type) => (
            <option key={type.value} value={type.value}>
              {type.label}
            </option>
          ))}
        </select>
      </div>

      {loading && <p className="message muted">Atualizando calendário...</p>}

      {view === "month" ? (
        <>
          <div className="calendar-month-scroll">
            <div className="calendar-grid">
              {WEEKDAYS.map((day) => (
                <strong key={day.value} className="calendar-weekday">
                  {day.label}
                </strong>
              ))}
              {monthDays.map((day) => {
                const key = isoDate(day);
                const dayEvents = eventsByDate.get(key) ?? [];
                return (
                  <div
                    key={key}
                    className={[
                      "calendar-day",
                      day.getMonth() !== cursor.getMonth() ? "muted" : "",
                      selectedDay === key ? "selected" : "",
                    ].join(" ")}
                  >
                    <button
                      type="button"
                      className="calendar-date"
                      aria-label={`Inspecionar ${day.toLocaleDateString("pt-BR")}`}
                      onClick={() => setSelectedDay(key)}
                    >
                      {day.getDate()}
                    </button>
                    {dayEvents.slice(0, 3).map((event) => renderEventButton(event))}
                    {dayEvents.length > 3 && (
                      <button
                        type="button"
                        className="calendar-more"
                        onClick={() => setSelectedDay(key)}
                      >
                        +{dayEvents.length - 3} evento(s)
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
          <section className="day-event-details" aria-labelledby="selected-day-title">
            <h2 id="selected-day-title">
              {new Date(`${selectedDay}T12:00:00`).toLocaleDateString("pt-BR", {
                weekday: "long",
                day: "numeric",
                month: "long",
              })}
            </h2>
            {(eventsByDate.get(selectedDay) ?? []).length ? (
              <div className="day-event-list">
                {(eventsByDate.get(selectedDay) ?? [])
                  .sort((a, b) => a.start_at.localeCompare(b.start_at))
                  .map((event) => (
                    <button
                      type="button"
                      key={eventKey(event)}
                      className={`day-event-row ${event.event_type}`}
                      onClick={() => setSelectedEvent(event)}
                    >
                      <span>{timeRange(event)}</span>
                      <strong>{event.title}</strong>
                      <small>{sourceLabel(event)}</small>
                    </button>
                  ))}
              </div>
            ) : (
              <p className="message muted">Nenhum evento confirmado neste dia.</p>
            )}
          </section>
        </>
      ) : (
        <div className="week-calendar-scroll" aria-label="Agenda temporal da semana">
          <div className="week-calendar">
            <div className="week-day-headers">
              <span aria-hidden="true" />
              {weekDays.map((day) => (
                <strong key={isoDate(day)}>
                  {day.toLocaleDateString("pt-BR", {
                    weekday: "short",
                    day: "2-digit",
                    month: "2-digit",
                  })}
                </strong>
              ))}
            </div>
            <div className="week-all-day">
              <span>Dia todo</span>
              {weekDays.map((day) => (
                <div key={isoDate(day)}>
                  {(eventsByDate.get(isoDate(day)) ?? [])
                    .filter((event) => event.all_day)
                    .map((event) => renderEventButton(event, "week-all-day-event"))}
                </div>
              ))}
            </div>
            <div
              className="week-time-grid"
              style={{ height: (lastHour - firstHour) * HOUR_HEIGHT }}
            >
              <div className="week-time-axis">
                {hours.map((hour) => (
                  <span
                    key={hour}
                    style={{ top: (hour - firstHour) * HOUR_HEIGHT }}
                  >
                    {pad(hour)}:00
                  </span>
                ))}
              </div>
              {weekDays.map((day) => {
                const dayKey = isoDate(day);
                const dayEvents = (eventsByDate.get(dayKey) ?? []).filter(
                  (event) => !event.all_day,
                );
                return (
                  <div className="week-day-track" key={dayKey}>
                    {hours.map((hour) => (
                      <span
                        className="week-hour-line"
                        key={hour}
                        style={{ top: (hour - firstHour) * HOUR_HEIGHT }}
                      />
                    ))}
                    {laneLayout(dayEvents).map(({ event, lane, laneCount }) => {
                      const start = minutesOfDay(event.start_at);
                      const end = event.end_at
                        ? minutesOfDay(event.end_at)
                        : start + 30;
                      const style = {
                        top:
                          ((start - firstHour * 60) / 60) * HOUR_HEIGHT,
                        height: Math.max(
                          26,
                          ((end - start) / 60) * HOUR_HEIGHT,
                        ),
                        left: `calc(${(lane / laneCount) * 100}% + 2px)`,
                        width: `calc(${100 / laneCount}% - 4px)`,
                      } as CSSProperties;
                      return (
                        <button
                          type="button"
                          key={eventKey(event)}
                          style={style}
                          className={`week-timed-event ${event.event_type} ${event.status}`}
                          onClick={() => setSelectedEvent(event)}
                          aria-label={`${event.title}, ${timeRange(event)}, ${labelForType(event.event_type)}`}
                        >
                          <span>{timeRange(event)}</span>
                          <strong>{event.title}</strong>
                        </button>
                      );
                    })}
                    {showCurrentTime && currentDayKey === dayKey && (
                      <span
                        className="current-time-line"
                        aria-label="Horário atual"
                        style={{
                          top:
                            ((currentMinute - firstHour * 60) / 60) *
                            HOUR_HEIGHT,
                        }}
                      />
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      <section className="card form-card calendar-event-form">
        <h2>Criar evento manual</h2>
        <div className="form-grid compact-grid">
          <label>
            Título
            <input
              value={manualTitle}
              onChange={(event) => setManualTitle(event.target.value)}
              placeholder="Ex.: grupo de estudo"
            />
          </label>
          <label>
            Data
            <input
              type="date"
              value={manualDate}
              onChange={(event) => setManualDate(event.target.value)}
            />
          </label>
          <label>
            Tipo
            <select
              value={manualType}
              onChange={(event) =>
                setManualType(event.target.value as CalendarEventType)
              }
            >
              {EVENT_TYPES.filter((type) => type.value !== "study_block").map(
                (type) => (
                  <option key={type.value} value={type.value}>
                    {type.label}
                  </option>
                ),
              )}
            </select>
          </label>
          <label className="checkbox-row">
            <input
              type="checkbox"
              checked={manualAllDay}
              onChange={(event) => setManualAllDay(event.target.checked)}
            />
            Dia todo
          </label>
          {!manualAllDay && (
            <>
              <label>
                Início
                <input
                  type="time"
                  value={manualStart}
                  onChange={(event) => setManualStart(event.target.value)}
                />
              </label>
              <label>
                Fim
                <input
                  type="time"
                  value={manualEnd}
                  onChange={(event) => setManualEnd(event.target.value)}
                />
              </label>
            </>
          )}
          <label>
            Recorrência
            <select
              value={recurrenceFrequency}
              onChange={(event) =>
                setRecurrenceFrequency(
                  event.target.value as RecurrenceRule["frequency"],
                )
              }
            >
              <option value="none">Não repete</option>
              <option value="daily">Diária</option>
              <option value="weekly">Semanal</option>
              <option value="biweekly">A cada duas semanas</option>
              <option value="monthly">Mensal</option>
              <option value="yearly">Anual</option>
              <option value="custom_weekly">Semanal personalizada</option>
            </select>
          </label>
        </div>
        {["weekly", "biweekly", "custom_weekly"].includes(
          recurrenceFrequency,
        ) && (
          <fieldset className="weekday-picker">
            <legend>Dias da semana</legend>
            {WEEKDAYS.map((day) => (
              <label key={day.value}>
                <input
                  type="checkbox"
                  checked={recurrenceWeekdays.includes(day.value)}
                  onChange={(event) =>
                    setRecurrenceWeekdays((items) =>
                      event.target.checked
                        ? [...items, day.value]
                        : items.filter((item) => item !== day.value),
                    )
                  }
                />
                {day.label}
              </label>
            ))}
          </fieldset>
        )}
        {recurrenceFrequency !== "none" && (
          <div className="form-grid compact-grid">
            <label>
              Término
              <select
                value={recurrenceEndMode}
                onChange={(event) =>
                  setRecurrenceEndMode(
                    event.target.value as
                      | "never"
                      | "on_date"
                      | "after_count",
                  )
                }
              >
                <option value="never">Nunca</option>
                <option value="on_date">Em uma data</option>
                <option value="after_count">Após ocorrências</option>
              </select>
            </label>
            {recurrenceEndMode === "on_date" && (
              <label>
                Data final
                <input
                  type="date"
                  value={recurrenceUntil}
                  onChange={(event) => setRecurrenceUntil(event.target.value)}
                />
              </label>
            )}
            {recurrenceEndMode === "after_count" && (
              <label>
                Número de ocorrências
                <input
                  type="number"
                  min="1"
                  max="500"
                  value={recurrenceCount}
                  onChange={(event) =>
                    setRecurrenceCount(Number(event.target.value))
                  }
                />
              </label>
            )}
          </div>
        )}
        <button className="primary-button" onClick={() => void handleCreateManual()}>
          Criar evento
        </button>
      </section>

      <section className="card form-card">
        <h2>Extrair eventos do plano</h2>
        <p>
          Selecione uma disciplina com plano confirmado. A extração gera um preview
          editável e não salva automaticamente.
        </p>
        <select
          value={previewDisciplineId}
          onChange={(event) => setPreviewDisciplineId(event.target.value)}
        >
          {disciplines.map((discipline) => (
            <option key={discipline.id} value={discipline.id}>
              {discipline.code} · {discipline.name}
            </option>
          ))}
        </select>
        <button
          className="secondary-button"
          disabled={loading || !previewDisciplineId}
          onClick={() => void handlePreviewExtraction()}
        >
          Extrair eventos do plano de ensino
        </button>
      </section>

      {drafts.length > 0 && (
        <section className="card">
          <h2>Preview de eventos extraídos</h2>
          <div className="draft-list">
            {drafts.map((draft, index) => (
              <div key={draft.temporary_id} className="draft-card">
                <input
                  value={draft.title}
                  onChange={(event) =>
                    setDrafts((items) =>
                      items.map((item, itemIndex) =>
                        itemIndex === index
                          ? { ...item, title: event.target.value }
                          : item,
                      ),
                    )
                  }
                />
                <select
                  value={draft.event_type}
                  onChange={(event) =>
                    setDrafts((items) =>
                      items.map((item, itemIndex) =>
                        itemIndex === index
                          ? {
                              ...item,
                              event_type: event.target.value as CalendarEventType,
                            }
                          : item,
                      ),
                    )
                  }
                >
                  {EVENT_TYPES.filter((type) => type.value !== "study_block").map(
                    (type) => (
                      <option key={type.value} value={type.value}>
                        {type.label}
                      </option>
                    ),
                  )}
                </select>
                <input
                  type="date"
                  value={draft.start_at?.slice(0, 10) ?? ""}
                  onChange={(event) =>
                    setDrafts((items) =>
                      items.map((item, itemIndex) =>
                        itemIndex === index
                          ? {
                              ...item,
                              start_at: event.target.value
                                ? `${event.target.value}T00:00:00-03:00`
                                : null,
                              ambiguous: !event.target.value,
                            }
                          : item,
                      ),
                    )
                  }
                />
                <small>Evidência: {draft.source_evidence}</small>
                <button
                  className="secondary-button"
                  onClick={() =>
                    setDrafts((items) =>
                      items.filter((_, itemIndex) => itemIndex !== index),
                    )
                  }
                >
                  Remover
                </button>
              </div>
            ))}
          </div>
          <div className="button-row">
            <button className="primary-button" onClick={() => void handleConfirmPreview()}>
              Confirmar preview
            </button>
            <button
              className="secondary-button"
              onClick={() => {
                setDrafts([]);
                setPreviewId(null);
              }}
            >
              Cancelar
            </button>
          </div>
        </section>
      )}

      {selectedEvent && (
        <section className="card event-detail" role="dialog" aria-modal="false">
          <h2>{selectedEvent.title}</h2>
          <p>
            {labelForType(selectedEvent.event_type)} · {selectedEvent.status} ·{" "}
            {sourceLabel(selectedEvent)}
          </p>
          <p>
            {timeRange(selectedEvent)} ·{" "}
            {new Date(selectedEvent.start_at).toLocaleString("pt-BR")}
          </p>
          {selectedEvent.priority_reason && (
            <p>
              Prioridade: {selectedEvent.priority_score} ·{" "}
              {selectedEvent.priority_reason}
            </p>
          )}
          {selectedEvent.source_evidence && (
            <p>Evidência: {selectedEvent.source_evidence}</p>
          )}
          <div className="button-row">
            <button
              className="secondary-button"
              onClick={() =>
                void completeCalendarEvent(selectedEvent.id).then(refresh)
              }
            >
              Concluir
            </button>
            <button
              className="secondary-button"
              onClick={() =>
                void cancelCalendarEvent(selectedEvent.id).then(refresh)
              }
            >
              Cancelar
            </button>
            <button
              className="secondary-button"
              onClick={() => setSelectedEvent(null)}
            >
              Fechar
            </button>
          </div>
        </section>
      )}
    </section>
  );
}
