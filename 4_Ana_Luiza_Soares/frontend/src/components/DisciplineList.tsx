import type { Discipline } from "../types";
import { EmptyState, LoadingState, StatusBadge } from "./ui";

type Props = { disciplines: Discipline[]; loading?: boolean; onOpen: (id: string) => void };

export function DisciplineList({ disciplines, loading = false, onOpen }: Props) {
  if (loading) return <LoadingState label="Carregando disciplinas..." />;
  if (disciplines.length === 0) return <EmptyState title="Nenhuma disciplina cadastrada" description="Use o botão Adicionar disciplina ou importe seu comprovante de matrícula." />;

  return <section className="list-section">
    <div className="section-heading"><div><h2>Disciplinas cadastradas</h2><p>{disciplines.length} {disciplines.length === 1 ? "disciplina disponível" : "disciplinas disponíveis"}</p></div></div>
    <div className="discipline-list">{disciplines.map((discipline) => <article className="discipline-item" key={discipline.id}>
      <div className="discipline-main">
        <div className="discipline-meta"><StatusBadge tone="info">{discipline.code}</StatusBadge>{discipline.sigaa_code && <StatusBadge tone="success">SIGAA</StatusBadge>}</div>
        <h3>{discipline.name}</h3>
        <p>{discipline.workload_hours ? `${discipline.workload_hours}h` : "Carga horária não informada"} · Turma {discipline.class_code || "não informada"}</p>
        <p className="muted">{discipline.schedule_display || "Horário não interpretado"}</p>
        {discipline.schedule_code && <p className="muted"><small>Código original: {discipline.schedule_code}</small></p>}
      </div>
      <button className="secondary-button" type="button" onClick={() => onOpen(discipline.id)}>Ver disciplina</button>
    </article>)}</div>
  </section>;
}
