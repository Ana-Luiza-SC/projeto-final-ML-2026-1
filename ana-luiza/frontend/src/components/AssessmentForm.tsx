import { FormEvent, useState } from "react";
import type { AssessmentPayload } from "../types";

type Props = {
  loading?: boolean;
  onSubmit: (payload: AssessmentPayload) => Promise<void>;
};

export function AssessmentForm({ loading = false, onSubmit }: Props) {
  const [name, setName] = useState("");
  const [weight, setWeight] = useState("");
  const [grade, setGrade] = useState("");
  const [date, setDate] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    if (!name.trim()) {
      setError("Nome da avaliação é obrigatório.");
      return;
    }
    const parsedWeight = Number(weight);
    if (!Number.isFinite(parsedWeight) || parsedWeight <= 0) {
      setError("Peso inválido. Use decimal ou porcentagem válida.");
      return;
    }
    const parsedGrade = grade.trim() === "" ? null : Number(grade);
    if (parsedGrade != null && (!Number.isFinite(parsedGrade) || parsedGrade < 0 || parsedGrade > 10)) {
      setError("Nota deve estar entre 0 e 10.");
      return;
    }

    await onSubmit({
      name: name.trim(),
      weight: parsedWeight,
      grade: parsedGrade,
      date: date || null,
      topics: [],
    });
    setName("");
    setWeight("");
    setGrade("");
    setDate("");
  }

  return (
    <form className="panel form-grid" onSubmit={handleSubmit}>
      <div className="panel-heading">
        <h2>Avaliação</h2>
        <p>Cadastre pesos em porcentagem, como 30, ou decimal, como 0.3.</p>
      </div>
      {error && <p className="message error">{error}</p>}
      <label>
        Nome *
        <input value={name} onChange={(event) => setName(event.target.value)} placeholder="Prova 1" />
      </label>
      <label>
        Peso *
        <input type="number" min="0" step="0.01" value={weight} onChange={(event) => setWeight(event.target.value)} placeholder="30" />
      </label>
      <label>
        Nota
        <input type="number" min="0" max="10" step="0.1" value={grade} onChange={(event) => setGrade(event.target.value)} placeholder="8.0" />
      </label>
      <label>
        Data opcional
        <input type="date" value={date} onChange={(event) => setDate(event.target.value)} />
      </label>
      <div className="form-actions">
        <button type="submit" disabled={loading}>{loading ? "Salvando..." : "Cadastrar avaliação"}</button>
      </div>
    </form>
  );
}
