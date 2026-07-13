import { useEffect, useMemo, useState } from "react";
import {
  confirmWeeklyPlan,
  createWeeklyPlanPreview,
  listDisciplines,
} from "../api/client";
import { EmptyState, PageHeader } from "../components/ui";
import type {
  Discipline,
  PriorityCapacityAnalysis,
  StudyPlanDay,
  WeeklyAvailabilityWindow,
  WeeklyPlanPreview,
} from "../types";

const DAYS: { value: StudyPlanDay; label: string }[] = [
  { value: "monday", label: "Segunda" },
  { value: "tuesday", label: "Terça" },
  { value: "wednesday", label: "Quarta" },
  { value: "thursday", label: "Quinta" },
  { value: "friday", label: "Sexta" },
  { value: "saturday", label: "Sábado" },
  { value: "sunday", label: "Domingo" },
];

function pad(value: number) {
  return String(value).padStart(2, "0");
}

function isoDate(date: Date) {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

function currentWeekStart() {
  const date = new Date();
  const offset = (date.getDay() + 6) % 7;
  date.setDate(date.getDate() - offset);
  return isoDate(date);
}

function minutesBetween(start: string, end: string) {
  const [startHour, startMinute] = start.split(":").map(Number);
  const [endHour, endMinute] = end.split(":").map(Number);
  return Math.max(0, endHour * 60 + endMinute - startHour * 60 - startMinute);
}

function durationText(minutes: number) {
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return [hours ? `${hours}h` : "", rest ? `${rest}min` : ""]
    .filter(Boolean)
    .join(" ") || "0min";
}

function localDateTime(value: string) {
  return new Date(value).toLocaleString("pt-BR", {
    weekday: "short",
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function capacityTone(item: PriorityCapacityAnalysis) {
  return item.reason_code === "fully_allocated"
    ? "capacity-ok"
    : item.allocated_minutes > 0
      ? "capacity-partial"
      : "capacity-missing";
}

export function StudyPlanPage({
  onOpenCalendar,
}: {
  onOpenCalendar: () => void;
}) {
  const [weekStart, setWeekStart] = useState(currentWeekStart);
  const [disciplines, setDisciplines] = useState<Discipline[]>([]);
  const [windows, setWindows] = useState<WeeklyAvailabilityWindow[]>([
    { weekday: "monday", start_time: "18:00", end_time: "20:00", available: true },
    { weekday: "wednesday", start_time: "18:00", end_time: "20:00", available: true },
  ]);
  const [excludedIds, setExcludedIds] = useState<string[]>([]);
  const [objective, setObjective] = useState("");
  const [preview, setPreview] = useState<WeeklyPlanPreview | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [confirmed, setConfirmed] = useState(false);

  useEffect(() => {
    listDisciplines()
      .then(setDisciplines)
      .catch((reason) =>
        setError(
          reason instanceof Error
            ? reason.message
            : "Não foi possível carregar as disciplinas.",
        ),
      );
  }, []);

  const dailyTotals = useMemo(() => {
    const totals = Object.fromEntries(DAYS.map((day) => [day.value, 0])) as Record<
      StudyPlanDay,
      number
    >;
    for (const window of windows) {
      if (window.available !== false) {
        totals[window.weekday] += minutesBetween(window.start_time, window.end_time);
      }
    }
    return totals;
  }, [windows]);

  const weeklyTotal = useMemo(
    () => Object.values(dailyTotals).reduce((total, minutes) => total + minutes, 0),
    [dailyTotals],
  );

  function updateWindow(
    index: number,
    patch: Partial<WeeklyAvailabilityWindow>,
  ) {
    setWindows((current) =>
      current.map((window, itemIndex) =>
        itemIndex === index ? { ...window, ...patch } : window,
      ),
    );
    setPreview(null);
    setConfirmed(false);
  }

  function addWindow(day: StudyPlanDay = "friday") {
    setWindows((current) => [
      ...current,
      { weekday: day, start_time: "18:00", end_time: "20:00", available: true },
    ]);
    setPreview(null);
    setConfirmed(false);
  }

  async function generatePreview() {
    if (weeklyTotal < 30) {
      setError("Adicione ao menos uma janela útil de 30 minutos.");
      return;
    }
    setLoading(true);
    setError(null);
    setNotice(null);
    setConfirmed(false);
    try {
      const result = await createWeeklyPlanPreview({
        week_start: weekStart,
        windows,
        excluded_discipline_ids: excludedIds,
        objective_text: objective.trim() || null,
      });
      setPreview(result);
      setNotice(
        `${result.planned_blocks.length} bloco(s) proposto(s) para revisão antes da confirmação.`,
      );
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Não foi possível gerar o planejamento.",
      );
    } finally {
      setLoading(false);
    }
  }

  async function confirmPreview() {
    if (!preview) return;
    setLoading(true);
    setError(null);
    try {
      const result = await confirmWeeklyPlan(preview.study_plan_id);
      setConfirmed(true);
      setNotice(
        `${result.created_count} bloco(s) confirmado(s). ${result.skipped_blocks.length} bloco(s) precisaram ser ignorados por conflito.`,
      );
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Não foi possível confirmar os blocos.",
      );
    } finally {
      setLoading(false);
    }
  }

  function togglePriority(disciplineId: string) {
    setExcludedIds((current) =>
      current.includes(disciplineId)
        ? current.filter((id) => id !== disciplineId)
        : [...current, disciplineId],
    );
    setPreview(null);
    setConfirmed(false);
  }

  return (
    <div className="page study-plan-page">
      <PageHeader
        eyebrow="Planejamento semanal"
        title="Planeje sua semana"
        description="Informe quando você pode estudar. As prioridades e os blocos são calculados com evidências acadêmicas e revisados antes de entrar no calendário."
      />

      {error && <p className="message error">{error}</p>}
      {notice && <p className="message success">{notice}</p>}

      <section className="panel planning-availability" aria-labelledby="availability-title">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Etapa 1</p>
            <h2 id="availability-title">Disponibilidade semanal</h2>
          </div>
          <label className="week-field">
            Semana iniciada em
            <input
              type="date"
              value={weekStart}
              onChange={(event) => {
                setWeekStart(event.target.value);
                setPreview(null);
                setConfirmed(false);
              }}
            />
          </label>
        </div>

        <div className="availability-days">
          {DAYS.map((day) => {
            const dayWindows = windows
              .map((window, index) => ({ window, index }))
              .filter((item) => item.window.weekday === day.value);
            return (
              <section className="availability-day" key={day.value}>
                <div className="availability-day-heading">
                  <strong>{day.label}</strong>
                  <span>{durationText(dailyTotals[day.value])}</span>
                </div>
                {dayWindows.map(({ window, index }) => (
                  <div className="availability-window" key={index}>
                    <input
                      aria-label={`Início em ${day.label}`}
                      type="time"
                      value={window.start_time}
                      onChange={(event) =>
                        updateWindow(index, { start_time: event.target.value })
                      }
                    />
                    <span>até</span>
                    <input
                      aria-label={`Fim em ${day.label}`}
                      type="time"
                      value={window.end_time}
                      onChange={(event) =>
                        updateWindow(index, { end_time: event.target.value })
                      }
                    />
                    <label className="availability-toggle">
                      <input
                        type="checkbox"
                        checked={window.available !== false}
                        onChange={(event) =>
                          updateWindow(index, { available: event.target.checked })
                        }
                      />
                      Disponível
                    </label>
                    <button
                      type="button"
                      className="text-button"
                      aria-label={`Remover janela de ${day.label}`}
                      onClick={() =>
                        setWindows((current) =>
                          current.filter((_, itemIndex) => itemIndex !== index),
                        )
                      }
                    >
                      Remover
                    </button>
                  </div>
                ))}
                <button
                  type="button"
                  className="secondary-button add-window-button"
                  onClick={() => addWindow(day.value)}
                >
                  Adicionar janela
                </button>
              </section>
            );
          })}
        </div>

        <div className="availability-total" aria-live="polite">
          <span>Total derivado da semana</span>
          <strong>{durationText(weeklyTotal)}</strong>
        </div>
        <label>
          Objetivo opcional da semana
          <textarea
            value={objective}
            maxLength={500}
            onChange={(event) => setObjective(event.target.value)}
            placeholder="Ex.: revisar as unidades ligadas à próxima avaliação"
          />
        </label>
        <div className="form-actions">
          <button
            type="button"
            disabled={loading || disciplines.length === 0}
            onClick={() => void generatePreview()}
          >
            {loading ? "Calculando..." : preview ? "Atualizar preview" : "Gerar preview"}
          </button>
        </div>
      </section>

      {disciplines.length === 0 && (
        <EmptyState
          title="Nenhuma disciplina cadastrada"
          description="Cadastre ou importe disciplinas antes de montar o planejamento."
        />
      )}

      {preview && (
        <>
          <section className="panel" aria-labelledby="priority-title">
            <div className="panel-heading">
              <p className="eyebrow">Etapa 2</p>
              <h2 id="priority-title">Prioridades calculadas</h2>
              <p>Você pode incluir ou excluir itens, mas a pontuação permanece autoritativa.</p>
            </div>
            <div className="priority-list">
              {preview.ranked_priorities.map((priority) => (
                <article className="priority-item" key={priority.priority_item_id}>
                  <label className="priority-include">
                    <input
                      type="checkbox"
                      checked={!excludedIds.includes(priority.discipline_id)}
                      onChange={() => togglePriority(priority.discipline_id)}
                    />
                    Incluir
                  </label>
                  <div>
                    <div className="priority-title-row">
                      <strong>
                        {priority.discipline_code} · {priority.discipline_name}
                      </strong>
                      <span className={`priority-band ${priority.priority_band}`}>
                        {priority.priority_band === "high"
                          ? "Alta"
                          : priority.priority_band === "medium"
                            ? "Média"
                            : "Baixa"}{" "}
                        {priority.priority_score}
                      </span>
                    </div>
                    <p>{priority.reason}</p>
                    <div className="priority-facts">
                      <span>
                        Demanda estimada:{" "}
                        {priority.estimated_demand_minutes != null
                          ? durationText(priority.estimated_demand_minutes)
                          : "evidência insuficiente"}
                      </span>
                      {priority.assessment_name && (
                        <span>
                          {priority.assessment_name}
                          {priority.deadline_at
                            ? ` · ${new Date(priority.deadline_at).toLocaleDateString("pt-BR")}`
                            : ""}
                        </span>
                      )}
                    </div>
                    <details>
                      <summary>Por quê?</summary>
                      <p>{priority.demand_reason}</p>
                      {priority.evidence_used.length > 0 && (
                        <ul>
                          {priority.evidence_used.map((evidence) => (
                            <li key={`${evidence.source_type}-${evidence.source_id}-${evidence.summary}`}>
                              {evidence.summary}
                            </li>
                          ))}
                        </ul>
                      )}
                      {priority.missing_evidence.length > 0 && (
                        <p className="message warning">
                          Faltam dados: {priority.missing_evidence.join(" ")}
                        </p>
                      )}
                    </details>
                  </div>
                </article>
              ))}
            </div>
          </section>

          <section className="panel" aria-labelledby="preview-title">
            <div className="panel-heading">
              <p className="eyebrow">Etapa 3</p>
              <h2 id="preview-title">Preview de blocos</h2>
              <p>Os blocos reservam tempo e não definem o método de estudo.</p>
            </div>
            {preview.planned_blocks.length ? (
              <div className="planned-block-list">
                {[...preview.planned_blocks]
                  .sort((a, b) => a.start_at.localeCompare(b.start_at))
                  .map((block) => (
                    <article className="planned-block" key={block.temporary_id}>
                      <time>{localDateTime(block.start_at)}</time>
                      <div>
                        <strong>{block.title}</strong>
                        <p>
                          {block.start_at.slice(11, 16)}–{block.end_at.slice(11, 16)}
                        </p>
                        <small>{block.reason}</small>
                      </div>
                    </article>
                  ))}
              </div>
            ) : (
              <EmptyState
                title="Nenhum bloco pôde ser proposto"
                description="Revise as explicações de capacidade abaixo."
              />
            )}

            <div className="capacity-list">
              {preview.capacity_analysis.map((item) => (
                <article
                  className={`capacity-item ${capacityTone(item)}`}
                  key={item.priority_item_id}
                >
                  <strong>{item.discipline_name}</strong>
                  <p>{item.reason}</p>
                  <dl>
                    <div>
                      <dt>Solicitado</dt>
                      <dd>
                        {item.requested_minutes == null
                          ? "Desconhecido"
                          : durationText(item.requested_minutes)}
                      </dd>
                    </div>
                    <div>
                      <dt>Alocado</dt>
                      <dd>{durationText(item.allocated_minutes)}</dd>
                    </div>
                    <div>
                      <dt>Utilizável antes do prazo</dt>
                      <dd>{durationText(item.usable_minutes_before_deadline)}</dd>
                    </div>
                    <div>
                      <dt>Bloqueado por eventos</dt>
                      <dd>{durationText(item.blocked_minutes)}</dd>
                    </div>
                    <div>
                      <dt>Mínimo útil</dt>
                      <dd>{durationText(item.minimum_useful_block_minutes)}</dd>
                    </div>
                  </dl>
                  {item.blocking_events.length > 0 && (
                    <details>
                      <summary>Eventos que bloquearam tempo</summary>
                      <ul>
                        {item.blocking_events.map((event) => (
                          <li key={event.event_id}>
                            {event.title}: {durationText(event.blocked_minutes)}
                          </li>
                        ))}
                      </ul>
                    </details>
                  )}
                </article>
              ))}
            </div>

            <div className="form-actions plan-confirm-actions">
              <button
                type="button"
                className="secondary-button"
                onClick={() => setPreview(null)}
              >
                Descartar preview
              </button>
              <button
                type="button"
                disabled={loading || confirmed || preview.planned_blocks.length === 0}
                onClick={() => void confirmPreview()}
              >
                {confirmed ? "Blocos confirmados" : "Confirmar blocos"}
              </button>
              {confirmed && (
                <button type="button" className="secondary-button" onClick={onOpenCalendar}>
                  Ver no calendário
                </button>
              )}
            </div>
          </section>
        </>
      )}
    </div>
  );
}
