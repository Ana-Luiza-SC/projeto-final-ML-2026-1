import type { Discipline } from "../types";

type Props = {
  disciplines: Discipline[];
  loading?: boolean;
  onOpen: (id: string) => void;
};

export function DisciplineList({ disciplines, loading = false, onOpen }: Props) {
  if (loading) return <p className="message muted">Carregando disciplinas...</p>;

  if (disciplines.length === 0) {
    return <p className="message muted">Nenhuma disciplina cadastrada ainda.</p>;
  }

  return (
    <section className="list-section">
      <h2>Disciplinas cadastradas</h2>
      <div className="discipline-list">
        {disciplines.map((discipline) => (
          <article className="discipline-item" key={discipline.id}>
            <div>
              <strong>{discipline.code}</strong>
              <h3>{discipline.name}</h3>
              <p>{discipline.professor || "Professor não informado"}</p>
              <p className="muted">Turma {discipline.class_code || "-"} · Horário {discipline.schedule_code || "-"}</p>
            </div>
            <button type="button" onClick={() => onOpen(discipline.id)}>Abrir detalhe</button>
          </article>
        ))}
      </div>
    </section>
  );
}
