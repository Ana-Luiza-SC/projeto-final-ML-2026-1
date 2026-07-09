import { FormEvent, useState } from "react";
import type { AttendancePayload, Discipline } from "../types";

type Props = {
  discipline: Discipline;
  loading?: boolean;
  onSubmit: (payload: AttendancePayload) => Promise<void>;
};

function toInput(value?: number | null) {
  return value == null ? "" : String(value);
}

function numberOrNull(value: string): number | null {
  if (value.trim() === "") return null;
  return Number(value);
}

export function AttendanceForm({ discipline, loading = false, onSubmit }: Props) {
  const [totalClasses, setTotalClasses] = useState(toInput(discipline.total_classes));
  const [missedClasses, setMissedClasses] = useState(toInput(discipline.missed_classes));
  const [totalClassHours, setTotalClassHours] = useState(toInput(discipline.total_class_hours));
  const [missedClassHours, setMissedClassHours] = useState(toInput(discipline.missed_class_hours));
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    const payload = {
      total_classes: numberOrNull(totalClasses),
      missed_classes: numberOrNull(missedClasses),
      total_class_hours: numberOrNull(totalClassHours),
      missed_class_hours: numberOrNull(missedClassHours),
    };
    if (payload.total_classes != null && payload.missed_classes != null && payload.missed_classes > payload.total_classes) {
      setError("Faltas não podem ser maiores que o total de aulas.");
      return;
    }
    if (payload.total_class_hours != null && payload.missed_class_hours != null && payload.missed_class_hours > payload.total_class_hours) {
      setError("Horas-aula perdidas não podem ser maiores que o total de horas-aula.");
      return;
    }
    await onSubmit(payload);
  }

  return (
    <form className="panel form-grid" onSubmit={handleSubmit}>
      <div className="panel-heading">
        <h2>Frequência e faltas</h2>
        <p>Informe aulas ou horas-aula para avaliar risco por falta.</p>
      </div>
      {error && <p className="message error">{error}</p>}
      <label>
        Total de aulas
        <input type="number" min="0" value={totalClasses} onChange={(event) => setTotalClasses(event.target.value)} />
      </label>
      <label>
        Faltas
        <input type="number" min="0" value={missedClasses} onChange={(event) => setMissedClasses(event.target.value)} />
      </label>
      <label>
        Total de horas-aula
        <input type="number" min="0" value={totalClassHours} onChange={(event) => setTotalClassHours(event.target.value)} />
      </label>
      <label>
        Horas-aula perdidas
        <input type="number" min="0" value={missedClassHours} onChange={(event) => setMissedClassHours(event.target.value)} />
      </label>
      <div className="form-actions">
        <button type="submit" disabled={loading}>{loading ? "Atualizando..." : "Atualizar frequência"}</button>
      </div>
    </form>
  );
}
