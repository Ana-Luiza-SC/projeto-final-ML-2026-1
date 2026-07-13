import { useEffect, useState } from "react";
import { listDisciplines } from "../api/client";
import { ApiStatus } from "../components/ApiStatus";
import { Alert, EmptyState, LoadingState, PageHeader } from "../components/ui";
import type { Discipline } from "../types";

type Props = { onOpenDisciplines: () => void; onOpenMatriculaImport?: () => void; onOpenStudyPlan: () => void };

export function HomePage({ onOpenDisciplines, onOpenMatriculaImport, onOpenStudyPlan }: Props) {
  const [disciplines, setDisciplines] = useState<Discipline[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listDisciplines().then(setDisciplines).catch((err) => setError(err instanceof Error ? err.message : "Não foi possível carregar seu resumo.")).finally(() => setLoading(false));
  }, []);

  return <div className="page dashboard-page">
    <PageHeader eyebrow="Visão geral" title="Organize seu semestre" description="Acompanhe disciplinas, simule seu desempenho e transforme sua disponibilidade em um plano de estudos." />
    {error && <Alert tone="error">{error}</Alert>}
    {loading ? <LoadingState label="Carregando seu semestre..." /> : <>
      <section className="dashboard-stats" aria-label="Resumo acadêmico">
        <article className="stat-card"><span>Disciplinas cadastradas</span><strong>{disciplines.length}</strong><p>{disciplines.length ? "Disponíveis para simulações e planejamento." : "Comece adicionando sua primeira disciplina."}</p></article>
        <article className="quick-action"><div><span className="action-kicker">Planejamento</span><h2>Monte sua semana de estudos</h2><p>Distribua o tempo disponível entre as disciplinas cadastradas.</p></div><button type="button" onClick={onOpenStudyPlan}>Criar planejamento</button></article>
        <article className="quick-action accent"><div><span className="action-kicker">Importação</span><h2>Adicione sua grade pelo comprovante</h2><p>Revise os componentes antes de confirmar qualquer cadastro.</p></div>{onOpenMatriculaImport && <button type="button" onClick={onOpenMatriculaImport}>Importar comprovante</button>}</article>
      </section>
      <section className="dashboard-section"><div className="section-heading"><div><p className="eyebrow">Próximos passos</p><h2>Continue sua organização</h2></div><ApiStatus /></div>
        {disciplines.length === 0 ? <EmptyState title="Seu semestre começa aqui" description="Importe o comprovante de matrícula ou cadastre uma disciplina manualmente. Você poderá revisar tudo antes de avançar." action={<div className="button-row"><button onClick={onOpenDisciplines}>Adicionar manualmente</button>{onOpenMatriculaImport && <button className="secondary-button" onClick={onOpenMatriculaImport}>Importar PDF</button>}</div>} /> : <div className="next-steps"><button className="next-step" onClick={onOpenDisciplines}><strong>Revise suas disciplinas</strong><span>Confira horários, frequência e avaliações.</span></button><button className="next-step" onClick={onOpenStudyPlan}><strong>Gere um plano semanal</strong><span>Use as {disciplines.length} disciplinas cadastradas.</span></button></div>}
      </section>
    </>}
  </div>;
}
