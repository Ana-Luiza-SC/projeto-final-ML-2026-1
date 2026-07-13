import { FormEvent, useState } from "react";
import type { StudyTopicInput, TopicDifficulty, TopicStatus } from "../types";

type Props = {
  topics: StudyTopicInput[];
  onChange: (topics: StudyTopicInput[]) => void;
};

export function PendingTopicsForm({ topics, onChange }: Props) {
  const [title, setTitle] = useState("");
  const [difficulty, setDifficulty] = useState<TopicDifficulty>("medium");
  const [status, setStatus] = useState<TopicStatus>("not_started");
  const [error, setError] = useState<string | null>(null);

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    if (!title.trim()) {
      setError("Informe o título do conteúdo pendente.");
      return;
    }
    onChange([...topics, { title: title.trim(), difficulty, status }]);
    setTitle("");
    setDifficulty("medium");
    setStatus("not_started");
  }

  function removeTopic(index: number) {
    onChange(topics.filter((_, currentIndex) => currentIndex !== index));
  }

  return (
    <section className="panel form-grid">
      <div className="panel-heading">
        <h2>Conteúdos pendentes</h2>
        <p>Lista local usada apenas para gerar a recomendação desta sessão.</p>
      </div>
      {error && <p className="message error">{error}</p>}
      <form className="topic-form" onSubmit={handleSubmit}>
        <label>
          Conteúdo
          <input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="GQM" />
        </label>
        <label>
          Dificuldade
          <select value={difficulty} onChange={(event) => setDifficulty(event.target.value as TopicDifficulty)}>
            <option value="low">baixa</option>
            <option value="medium">média</option>
            <option value="high">alta</option>
          </select>
        </label>
        <label>
          Status
          <select value={status} onChange={(event) => setStatus(event.target.value as TopicStatus)}>
            <option value="not_started">não iniciado</option>
            <option value="in_progress">em andamento</option>
            <option value="reviewed">revisado</option>
          </select>
        </label>
        <button type="submit">Adicionar</button>
      </form>
      {topics.length === 0 ? (
        <p className="message muted">Nenhum conteúdo pendente informado.</p>
      ) : (
        <div className="topic-list">
          {topics.map((topic, index) => (
            <div className="topic-item" key={`${topic.title}-${index}`}>
              <div>
                <strong>{topic.title}</strong>
                <span>{topic.difficulty} · {topic.status}</span>
              </div>
              <button type="button" onClick={() => removeTopic(index)}>Remover</button>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
