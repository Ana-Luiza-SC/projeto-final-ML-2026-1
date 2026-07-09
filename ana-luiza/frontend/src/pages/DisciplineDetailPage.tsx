import { useEffect, useState } from "react";
import { createAssessment, getAcademicSimulation, getDiscipline, updateAttendance } from "../api/client";
import { AcademicSimulationPanel } from "../components/AcademicSimulationPanel";
import { AssessmentForm } from "../components/AssessmentForm";
import { AttendanceForm } from "../components/AttendanceForm";
import type { AcademicSimulation, AssessmentPayload, AttendancePayload, Discipline } from "../types";

type Props = {
  disciplineId: string;
  onBack: () => void;
};

export function DisciplineDetailPage({ disciplineId, onBack }: Props) {
  const [discipline, setDiscipline] = useState<Discipline | null>(null);
  const [simulation, setSimulation] = useState<AcademicSimulation | null>(null);
  const [targetAverage, setTargetAverage] = useState("5.0");
  const [loadingDiscipline, setLoadingDiscipline] = useState(true);
  const [loadingAttendance, setLoadingAttendance] = useState(false);
  const [loadingAssessment, setLoadingAssessment] = useState(false);
  const [loadingSimulation, setLoadingSimulation] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [simulationError, setSimulationError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  async function loadDiscipline() {
    setLoadingDiscipline(true);
    setError(null);
    try {
      setDiscipline(await getDiscipline(disciplineId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível carregar a disciplina.");
    } finally {
      setLoadingDiscipline(false);
    }
  }

  async function loadSimulation() {
    setLoadingSimulation(true);
    setSimulationError(null);
    const parsedTarget = Number(targetAverage);
    if (!Number.isFinite(parsedTarget) || parsedTarget < 0 || parsedTarget > 10) {
      setSimulationError("Média alvo deve estar entre 0 e 10.");
      setLoadingSimulation(false);
      return;
    }
    try {
      setSimulation(await getAcademicSimulation(disciplineId, parsedTarget));
    } catch (err) {
      setSimulationError(err instanceof Error ? err.message : "Não foi possível calcular a simulação.");
    } finally {
      setLoadingSimulation(false);
    }
  }

  useEffect(() => {
    void loadDiscipline();
  }, [disciplineId]);

  useEffect(() => {
    if (discipline) void loadSimulation();
  }, [discipline?.id]);

  async function handleAttendance(payload: AttendancePayload) {
    setLoadingAttendance(true);
    setError(null);
    setNotice(null);
    try {
      const updated = await updateAttendance(disciplineId, payload);
      setDiscipline(updated);
      setNotice("Frequência atualizada.");
      await loadSimulation();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível atualizar frequência.");
    } finally {
      setLoadingAttendance(false);
    }
  }

  async function handleAssessment(payload: AssessmentPayload) {
    setLoadingAssessment(true);
    setError(null);
    setNotice(null);
    try {
      await createAssessment(disciplineId, payload);
      setNotice("Avaliação cadastrada.");
      await loadSimulation();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível cadastrar avaliação.");
    } finally {
      setLoadingAssessment(false);
    }
  }

  if (loadingDiscipline) {
    return <div className="page"><p className="message muted">Carregando detalhe da disciplina...</p></div>;
  }

  if (error && !discipline) {
    return (
      <div className="page narrow-page">
        <p className="message error">{error}</p>
        <button type="button" onClick={onBack}>Voltar para disciplinas</button>
      </div>
    );
  }

  if (!discipline) {
    return (
      <div className="page narrow-page">
        <p className="message error">Disciplina não encontrada.</p>
        <button type="button" onClick={onBack}>Voltar para disciplinas</button>
      </div>
    );
  }

  return (
    <div className="page detail-page">
      <button className="back-button" type="button" onClick={onBack}>Voltar para disciplinas</button>

      <section className="panel discipline-summary">
        <div>
          <p className="eyebrow">Detalhe da disciplina</p>
          <h1>{discipline.code} · {discipline.name}</h1>
        </div>
        <dl>
          <div><dt>Professor</dt><dd>{discipline.professor || "Não informado"}</dd></div>
          <div><dt>Turma</dt><dd>{discipline.class_code || "Não informada"}</dd></div>
          <div><dt>Horário</dt><dd>{discipline.schedule_code || "Não informado"}</dd></div>
          <div><dt>Local</dt><dd>{discipline.local || "Não informado"}</dd></div>
        </dl>
      </section>

      {error && <p className="message error">{error}</p>}
      {notice && <p className="message success">{notice}</p>}

      <div className="detail-grid">
        <div className="stack">
          <AttendanceForm discipline={discipline} loading={loadingAttendance} onSubmit={handleAttendance} />
          <AssessmentForm loading={loadingAssessment} onSubmit={handleAssessment} />
        </div>
        <div className="stack">
          <section className="panel target-panel">
            <label>
              Média alvo
              <input type="number" min="0" max="10" step="0.1" value={targetAverage} onChange={(event) => setTargetAverage(event.target.value)} />
            </label>
            <button type="button" onClick={loadSimulation} disabled={loadingSimulation}>{loadingSimulation ? "Consultando..." : "Consultar simulação"}</button>
          </section>
          <AcademicSimulationPanel simulation={simulation} loading={loadingSimulation} error={simulationError} />
        </div>
      </div>
    </div>
  );
}
