import { FormEvent, useState } from "react";
import type { DisciplineCreatePayload } from "../types";

type Props = {
  loading?: boolean;
  onSubmit: (payload: DisciplineCreatePayload) => Promise<void>;
};

const initialForm: DisciplineCreatePayload = {
  code: "",
  name: "",
  professor: "",
  class_code: "",
  schedule_code: "",
  local: "",
};

export function DisciplineForm({ loading = false, onSubmit }: Props) {
  const [form, setForm] = useState(initialForm);
  const [error, setError] = useState<string | null>(null);

  function updateField(field: keyof DisciplineCreatePayload, value: string) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    if (!form.code.trim()) {
      setError("Código da disciplina é obrigatório.");
      return;
    }
    if (!form.name.trim()) {
      setError("Nome da disciplina é obrigatório.");
      return;
    }

    await onSubmit({
      code: form.code.trim(),
      name: form.name.trim(),
      professor: form.professor?.trim() || null,
      class_code: form.class_code?.trim() || null,
      schedule_code: form.schedule_code?.trim() || null,
      local: form.local?.trim() || null,
    });
    setForm(initialForm);
  }

  return (
    <form className="panel form-grid" onSubmit={handleSubmit}>
      <div className="panel-heading">
        <h2>Cadastrar disciplina manualmente</h2>
        <p>Fallback obrigatório quando importação ou SIGAA não estiverem disponíveis.</p>
      </div>
      {error && <p className="message error">{error}</p>}
      <label>
        Código *
        <input value={form.code} onChange={(event) => updateField("code", event.target.value)} placeholder="FGA0000" />
      </label>
      <label>
        Nome *
        <input value={form.name} onChange={(event) => updateField("name", event.target.value)} placeholder="Nome da disciplina" />
      </label>
      <label>
        Professor
        <input value={form.professor ?? ""} onChange={(event) => updateField("professor", event.target.value)} placeholder="Docente" />
      </label>
      <label>
        Turma
        <input value={form.class_code ?? ""} onChange={(event) => updateField("class_code", event.target.value)} placeholder="01" />
      </label>
      <label>
        Horário
        <input value={form.schedule_code ?? ""} onChange={(event) => updateField("schedule_code", event.target.value)} placeholder="24M12" />
      </label>
      <label>
        Local
        <input value={form.local ?? ""} onChange={(event) => updateField("local", event.target.value)} placeholder="Sala" />
      </label>
      <div className="form-actions">
        <button type="submit" disabled={loading}>{loading ? "Salvando..." : "Cadastrar disciplina"}</button>
      </div>
    </form>
  );
}
