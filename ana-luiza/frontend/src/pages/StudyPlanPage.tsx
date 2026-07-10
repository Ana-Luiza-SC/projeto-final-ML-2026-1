import { useEffect, useMemo, useState } from "react";
import { createStudyPlan, listDisciplines } from "../api/client";
import type { Discipline, StudyPlanDay, StudyPlanResponse, StudyPlanTimeWindow } from "../types";

const DAYS: { value: StudyPlanDay; label: string }[] = [
  { value: "monday", label: "Segunda" },
  { value: "tuesday", label: "Terça" },
  { value: "wednesday", label: "Quarta" },
  { value: "thursday", label: "Quinta" },
  { value: "friday", label: "Sexta" },
  { value: "saturday", label: "Sábado" },
  { value: "sunday", label: "Domingo" },
];

function dayLabel(day: StudyPlanDay) {
  return DAYS.find((item) => item.value === day)?.label ?? day;
}

export function StudyPlanPage() {
  const [disciplines, setDisciplines] = useState<Discipline[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [priorities, setPriorities] = useState<Record<string, number>>({});
  const [availableHours, setAvailableHours] = useState("6");
  const [selectedDays, setSelectedDays] = useState<StudyPlanDay[]>(["monday", "wednesday", "friday"]);
  const [maxSession, setMaxSession] = useState("90");
  const [objective, setObjective] = useState("");
  const [windows, setWindows] = useState<StudyPlanTimeWindow[]>([]);
  const [windowDraft, setWindowDraft] = useState<StudyPlanTimeWindow>({ day: "monday", start_time: "18:00", end_time: "20:00" });
  const [loadingDisciplines, setLoadingDisciplines] = useState(true);
  const [loadingPlan, setLoadingPlan] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [plan, setPlan] = useState<StudyPlanResponse | null>(null);

  useEffect(() => {
    async function load() {
      setLoadingDisciplines(true);
      setError(null);
      try {
        const response = await listDisciplines();
        setDisciplines(response);
        setPriorities(Object.fromEntries(response.map((discipline) => [discipline.id, 3])));
      } catch (err) {
        setError(err instanceof Error ? err.message : "Não foi possível carregar disciplinas.");
      } finally {
        setLoadingDisciplines(false);
      }
    }
    void load();
  }, []);

  const groupedPlan = useMemo(() => {
    if (!plan) return [];
    return DAYS.map((day) => ({
      day,
      sessions: plan.plan.filter((session) => session.day === day.value),
    })).filter((item) => item.sessions.length > 0);
  }, [plan]);

  function toggleDiscipline(id: string) {
    setSelectedIds((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id]);
  }

  function toggleDay(day: StudyPlanDay) {
    setSelectedDays((current) => current.includes(day) ? current.filter((item) => item !== day) : [...current, day]);
  }

  function addWindow() {
    if (!selectedDays.includes(windowDraft.day)) {
      setError("A janela precisa pertencer a um dia selecionado.");
      return;
    }
    setWindows((current) => [...current, windowDraft]);
    setError(null);
  }

  async function handleSubmit() {
    const parsedHours = Number(availableHours);
    const parsedSession = Number(maxSession);
    if (!selectedIds.length) {
      setError("Selecione ao menos uma disciplina.");
      return;
    }
    if (!selectedDays.length) {
      setError("Selecione ao menos um dia disponível.");
      return;
    }
    if (!Number.isFinite(parsedHours) || parsedHours <= 0) {
      setError("Horas semanais devem ser maiores que zero.");
      return;
    }
    if (!Number.isFinite(parsedSession) || parsedSession < 30) {
      setError("Duração máxima deve ser de pelo menos 30 minutos.");
      return;
    }

    setLoadingPlan(true);
    setError(null);
    try {
      const response = await createStudyPlan({
        discipline_ids: selectedIds,
        availability: {
          available_hours_per_week: parsedHours,
          days_available: selectedDays,
          time_windows: windows.length ? windows : undefined,
        },
        max_session_minutes: parsedSession,
        priorities: selectedIds.map((disciplineId) => ({
          discipline_id: disciplineId,
          priority: priorities[disciplineId] ?? 3,
        })),
        objective_text: objective.trim() || null,
      });
      setPlan(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível gerar o plano.");
    } finally {
      setLoadingPlan(false);
    }
  }

  return (
    <div className="page study-plan-page">
      <section className="page-heading">
        <p className="eyebrow">Planejamento semanal</p>
        <h1>Plano de estudos</h1>
        <p>Selecione disciplinas cadastradas e distribua a disponibilidade semanal em sessões de estudo.</p>
      </section>

      {error && <p className="message error">{error}</p>}

      <div className="study-plan-grid">
        <section className="panel study-plan-form">
          <div className="panel-heading">
            <h2>Disciplinas e disponibilidade</h2>
            <p>O plano usa apenas disciplinas já cadastradas.</p>
          </div>

          {loadingDisciplines && <p className="message muted">Carregando disciplinas...</p>}
          {!loadingDisciplines && disciplines.length === 0 && <p className="message warning">Cadastre disciplinas antes de gerar um plano.</p>}

          <div className="discipline-selector">
            {disciplines.map((discipline) => (
              <div className="study-plan-discipline" key={discipline.id}>
                <label className="checkbox-row">
                  <input type="checkbox" checked={selectedIds.includes(discipline.id)} onChange={() => toggleDiscipline(discipline.id)} />
                  <span>{discipline.code} · {discipline.name}</span>
                </label>
                <label>
                  Prioridade
                  <select value={priorities[discipline.id] ?? 3} onChange={(event) => setPriorities((current) => ({ ...current, [discipline.id]: Number(event.target.value) }))} disabled={!selectedIds.includes(discipline.id)}>
                    <option value={1}>1</option>
                    <option value={2}>2</option>
                    <option value={3}>3</option>
                    <option value={4}>4</option>
                    <option value={5}>5</option>
                  </select>
                </label>
              </div>
            ))}
          </div>

          <div className="form-grid compact-grid">
            <label>
              Horas semanais
              <input type="number" min="0.5" step="0.5" value={availableHours} onChange={(event) => setAvailableHours(event.target.value)} />
            </label>
            <label>
              Duração máxima por sessão
              <select value={maxSession} onChange={(event) => setMaxSession(event.target.value)}>
                <option value="30">30 min</option>
                <option value="60">60 min</option>
                <option value="90">90 min</option>
                <option value="120">120 min</option>
              </select>
            </label>
          </div>

          <div className="day-selector">
            {DAYS.map((day) => (
              <label className="checkbox-row" key={day.value}>
                <input type="checkbox" checked={selectedDays.includes(day.value)} onChange={() => toggleDay(day.value)} />
                <span>{day.label}</span>
              </label>
            ))}
          </div>

          <div className="window-editor">
            <h3>Janelas horárias opcionais</h3>
            <div className="window-row">
              <label>
                Dia
                <select value={windowDraft.day} onChange={(event) => setWindowDraft((current) => ({ ...current, day: event.target.value as StudyPlanDay }))}>
                  {DAYS.map((day) => <option key={day.value} value={day.value}>{day.label}</option>)}
                </select>
              </label>
              <label>
                Início
                <input type="time" value={windowDraft.start_time} onChange={(event) => setWindowDraft((current) => ({ ...current, start_time: event.target.value }))} />
              </label>
              <label>
                Fim
                <input type="time" value={windowDraft.end_time} onChange={(event) => setWindowDraft((current) => ({ ...current, end_time: event.target.value }))} />
              </label>
              <button type="button" className="secondary-button" onClick={addWindow}>Adicionar</button>
            </div>
            {windows.length > 0 && (
              <ul className="window-list">
                {windows.map((window, index) => (
                  <li key={`${window.day}-${window.start_time}-${window.end_time}-${index}`}>
                    {dayLabel(window.day)} · {window.start_time} às {window.end_time}
                    <button type="button" onClick={() => setWindows((current) => current.filter((_, itemIndex) => itemIndex !== index))}>Remover</button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <label>
            Objetivo opcional
            <input value={objective} maxLength={500} onChange={(event) => setObjective(event.target.value)} placeholder="ex.: revisar para a prova da próxima semana" />
          </label>

          <div className="form-actions">
            <button type="button" onClick={handleSubmit} disabled={loadingPlan || loadingDisciplines || disciplines.length === 0}>
              {loadingPlan ? "Gerando..." : "Gerar plano"}
            </button>
          </div>
        </section>

        <section className="panel study-plan-result">
          <div className="panel-heading">
            <h2>Plano gerado</h2>
            <p>{plan ? (plan.source === "llm_assisted" ? "Explicação assistida por IA validada." : "Fallback determinístico em uso.") : "Nenhum plano gerado ainda."}</p>
          </div>

          {loadingPlan && <p className="message muted">Gerando plano semanal...</p>}
          {plan && (
            <div className="study-plan-output">
              <p>{plan.summary}</p>
              <div className="metrics-grid">
                <div><span>Minutos alocados</span><strong>{plan.metrics.allocated_minutes}</strong></div>
                <div><span>Sessões</span><strong>{plan.metrics.session_count}</strong></div>
                <div><span>Origem</span><strong>{plan.source === "llm_assisted" ? "IA validada" : "Fallback"}</strong></div>
              </div>
              {plan.warnings.length > 0 && (
                <div className="warnings">
                  <h3>Avisos</h3>
                  <ul>{plan.warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul>
                </div>
              )}
              <div className="study-plan-days">
                {groupedPlan.map(({ day, sessions }) => (
                  <section className="study-day" key={day.value}>
                    <h3>{day.label}</h3>
                    {sessions.map((session) => (
                      <div className="study-session" key={`${session.day}-${session.sequence}-${session.discipline_id}-${session.duration_minutes}`}>
                        <strong>{session.discipline_code} · {session.discipline_name}</strong>
                        <span>{session.start_time && session.end_time ? `${session.start_time} às ${session.end_time}` : `Sessão ${session.sequence}`} · {session.duration_minutes} min</span>
                        <p>{session.activity}</p>
                      </div>
                    ))}
                  </section>
                ))}
              </div>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
