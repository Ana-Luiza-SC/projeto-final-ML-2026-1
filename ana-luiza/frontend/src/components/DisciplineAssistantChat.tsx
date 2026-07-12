import { FormEvent, useState } from "react";
import { sendDisciplineAssistantMessage } from "../api/client";
import type { AssistantMessage } from "../types";

const suggestions = ["Montar prioridade da semana", "Analisar próxima avaliação", "Explicar minha situação de notas", "Analisar frequência"];
export function DisciplineAssistantChat({ disciplineId, userGoal, initialPrompt }: { disciplineId: string; userGoal: string; initialPrompt?: string }) {
  const [messages, setMessages] = useState<AssistantMessage[]>([]);
  const [text, setText] = useState(initialPrompt ?? ""); const [loading, setLoading] = useState(false); const [error, setError] = useState<string | null>(null);
  async function send(event?: FormEvent) { event?.preventDefault(); const message = text.trim(); if (!message || loading) return; const next = [...messages, { role: "user" as const, content: message }]; setMessages(next); setText(""); setLoading(true); setError(null); try { const result = await sendDisciplineAssistantMessage(disciplineId, message, messages, userGoal); setMessages([...next, { role: "assistant", content: result.answer, evidence: result.evidence, suggested_actions: result.suggested_actions, warnings: result.warnings, source: result.source }]); } catch (err) { setError(err instanceof Error ? err.message : "Não foi possível responder agora."); } finally { setLoading(false); } }
  return <section className="panel assistant-chat"><div className="panel-heading"><h2>Assistente da disciplina</h2><p>Analisa notas, avaliações, plano confirmado e frequência usando apenas os dados cadastrados.</p></div>
    <div className="quick-prompts">{suggestions.map(item => <button className="secondary-button" type="button" key={item} onClick={() => setText(item)}>{item}</button>)}</div>
    <div className="chat-messages" aria-live="polite">{messages.length === 0 && <p className="message muted">Faça uma pergunta sobre esta disciplina.</p>}{messages.map((item, index) => <article className={`chat-message ${item.role}`} key={`${index}-${item.content}`}><strong>{item.role === "user" ? "Você" : "Assistente"}</strong><p>{item.content}</p>{item.source === "fallback" && <span className="status-badge badge-info">Resposta baseada em regras</span>}{item.evidence?.length ? <details><summary>Evidências usadas</summary><ul>{item.evidence.map(e => <li key={e}>{e}</li>)}</ul></details> : null}{item.suggested_actions?.length ? <ul>{item.suggested_actions.map(a => <li key={a}>{a}</li>)}</ul> : null}</article>)}</div>
    {loading && <p className="message muted">Analisando os dados cadastrados...</p>}{error && <p className="message error">{error}</p>}
    <form className="chat-composer" onSubmit={send}><textarea aria-label="Mensagem para o assistente" value={text} maxLength={1000} onChange={event => setText(event.target.value)} placeholder="Como devo estudar para a próxima prova?"/><button disabled={loading || !text.trim()}>Enviar</button></form>
  </section>;
}
