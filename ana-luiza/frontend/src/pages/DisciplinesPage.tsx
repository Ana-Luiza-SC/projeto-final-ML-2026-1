import { useEffect, useState } from "react";
import { createDiscipline, listDisciplines } from "../api/client";
import { DisciplineForm } from "../components/DisciplineForm";
import { DisciplineList } from "../components/DisciplineList";
import type { Discipline, DisciplineCreatePayload } from "../types";

type Props = {
  onOpenDiscipline: (id: string) => void;
};

export function DisciplinesPage({ onOpenDiscipline }: Props) {
  const [disciplines, setDisciplines] = useState<Discipline[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function loadDisciplines() {
    setLoading(true);
    setError(null);
    try {
      setDisciplines(await listDisciplines());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível carregar disciplinas.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadDisciplines();
  }, []);

  async function handleCreate(payload: DisciplineCreatePayload) {
    setSaving(true);
    setError(null);
    try {
      const created = await createDiscipline(payload);
      setDisciplines((current) => [...current, created]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível cadastrar disciplina.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="page two-column">
      <section>
        <div className="page-heading">
          <p className="eyebrow">Disciplinas</p>
          <h1>Cadastro manual</h1>
          <p>Use esta tela para demonstrar o fluxo principal sem PDF, SIGAA ou LLM.</p>
        </div>
        {error && <p className="message error">{error}</p>}
        <DisciplineList disciplines={disciplines} loading={loading} onOpen={onOpenDiscipline} />
      </section>
      <DisciplineForm loading={saving} onSubmit={handleCreate} />
    </div>
  );
}
