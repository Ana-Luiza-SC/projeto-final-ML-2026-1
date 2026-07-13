import { useEffect, useState } from "react";
import { createDiscipline, listDisciplines } from "../api/client";
import { DisciplineForm } from "../components/DisciplineForm";
import { DisciplineList } from "../components/DisciplineList";
import { Alert, PageHeader } from "../components/ui";
import type { Discipline, DisciplineCreatePayload } from "../types";

type Props = { onOpenDiscipline: (id: string) => void };

export function DisciplinesPage({ onOpenDiscipline }: Props) {
  const [disciplines, setDisciplines] = useState<Discipline[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  async function loadDisciplines() {
    setLoading(true); setError(null);
    try { setDisciplines(await listDisciplines()); }
    catch (err) { setError(err instanceof Error ? err.message : "Não foi possível carregar disciplinas."); }
    finally { setLoading(false); }
  }
  useEffect(() => { void loadDisciplines(); }, []);

  async function handleCreate(payload: DisciplineCreatePayload) {
    setSaving(true); setError(null); setNotice(null);
    try {
      const created = await createDiscipline(payload);
      setDisciplines((current) => [...current, created]);
      setNotice(`${created.code} foi cadastrada.`);
      setShowForm(false);
    } catch (err) { setError(err instanceof Error ? err.message : "Não foi possível cadastrar disciplina."); }
    finally { setSaving(false); }
  }

  return <div className="page disciplines-page">
    <PageHeader eyebrow="Semestre atual" title="Disciplinas" description="Consulte dados acadêmicos, avaliações e recomendações de cada disciplina." action={<button type="button" onClick={() => setShowForm((value) => !value)}>{showForm ? "Fechar cadastro" : "Adicionar disciplina"}</button>} />
    {error && <Alert tone="error">{error}</Alert>}
    {notice && <Alert tone="success">{notice}</Alert>}
    <div className={showForm ? "disciplines-layout form-open" : "disciplines-layout"}>
      <section className="discipline-content"><DisciplineList disciplines={disciplines} loading={loading} onOpen={onOpenDiscipline} /></section>
      {showForm && <aside className="discipline-drawer" aria-label="Adicionar disciplina"><DisciplineForm loading={saving} onSubmit={handleCreate} /></aside>}
    </div>
  </div>;
}
