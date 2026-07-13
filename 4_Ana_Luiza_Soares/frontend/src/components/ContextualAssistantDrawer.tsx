import {
  FormEvent,
  useEffect,
  useRef,
  useState,
} from "react";
import {
  confirmContextualAssistantAction,
  sendContextualAssistantMessage,
} from "../api/client";
import type {
  ContextualAssistantAction,
  ContextualAssistantIntent,
  ContextualAssistantResponse,
} from "../types";

type AssistantRoute =
  | "home"
  | "disciplines"
  | "discipline"
  | "study-plan"
  | "calendar"
  | "matricula-import";

type Props = {
  open: boolean;
  route: AssistantRoute;
  disciplineId?: string | null;
  onClose: () => void;
  onNavigatePath: (path: string) => void;
};

type ConversationItem = {
  role: "user" | "assistant";
  content: string;
  response?: ContextualAssistantResponse;
};

const prompts: {
  label: string;
  message: string;
  intent: ContextualAssistantIntent;
}[] = [
  {
    label: "Explicar prioridade",
    message: "Explique a prioridade mais relevante.",
    intent: "explain_priority",
  },
  {
    label: "Sugerir métodos",
    message: "Quais métodos de estudo combinam com este contexto?",
    intent: "recommend_methods",
  },
  {
    label: "Propor bloco",
    message: "Proponha um bloco de estudo validado.",
    intent: "propose_study_block",
  },
  {
    label: "Explicar capacidade",
    message: "Explique a falta de capacidade desta semana.",
    intent: "explain_capacity_shortage",
  },
];

export function ContextualAssistantDrawer({
  open,
  route,
  disciplineId,
  onClose,
  onNavigatePath,
}: Props) {
  const [messages, setMessages] = useState<ConversationItem[]>([]);
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState<ContextualAssistantAction | null>(
    null,
  );
  const [notice, setNotice] = useState<string | null>(null);
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (open) closeRef.current?.focus();
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [onClose, open]);

  async function send(
    message: string,
    intent: ContextualAssistantIntent = "general",
    selectedPriorityId?: string,
  ) {
    const cleaned = message.trim();
    if (!cleaned || loading) return;
    setMessages((current) => [
      ...current,
      { role: "user", content: cleaned },
    ]);
    setText("");
    setLoading(true);
    setError(null);
    setNotice(null);
    try {
      const response = await sendContextualAssistantMessage({
        route,
        message: cleaned,
        intent,
        selected_discipline_id: disciplineId ?? null,
        selected_priority_id: selectedPriorityId ?? null,
      });
      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content: response.message,
          response,
        },
      ]);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Não foi possível consultar o assistente.",
      );
    } finally {
      setLoading(false);
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    void send(text);
  }

  function selectAction(action: ContextualAssistantAction) {
    if (action.requires_confirmation) {
      setPending(action);
      return;
    }
    const path =
      typeof action.payload.path === "string"
        ? action.payload.path
        : null;
    if (path) {
      if (
        action.type === "navigate_to_calendar_date" &&
        typeof action.payload.date === "string"
      ) {
        sessionStorage.setItem(
          "estudaunb_calendar_focus_date",
          action.payload.date,
        );
      }
      onNavigatePath(path);
      return;
    }
    if (action.type === "explain_capacity_shortage") {
      void send(
        "Explique os limites de capacidade desta prioridade.",
        "explain_capacity_shortage",
        typeof action.payload.priority_item_id === "string"
          ? action.payload.priority_item_id
          : undefined,
      );
    }
  }

  async function confirmPending() {
    if (!pending?.action_id) return;
    setLoading(true);
    setError(null);
    try {
      const result = await confirmContextualAssistantAction(
        pending.action_id,
      );
      setNotice(
        result.status === "already_executed"
          ? "Esta ação já estava confirmada."
          : "Bloco adicionado ao calendário.",
      );
      setPending(null);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Não foi possível confirmar a ação.",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      {open && (
        <button
          className="assistant-backdrop"
          type="button"
          aria-label="Fechar assistente"
          onClick={onClose}
        />
      )}
      <aside
        className={`assistant-drawer ${open ? "open" : ""}`}
        aria-hidden={!open}
        aria-label="Assistente contextual"
      >
        <header className="assistant-drawer-header">
          <div>
            <p className="eyebrow">Contexto atual</p>
            <h2>Assistente de estudos</h2>
          </div>
          <button
            ref={closeRef}
            className="secondary-button"
            type="button"
            onClick={onClose}
          >
            Fechar
          </button>
        </header>

        <div className="assistant-drawer-body">
          <div className="quick-prompts" aria-label="Ações rápidas">
            {prompts.map((prompt) => (
              <button
                className="secondary-button"
                type="button"
                key={prompt.intent}
                disabled={loading}
                onClick={() =>
                  void send(prompt.message, prompt.intent)
                }
              >
                {prompt.label}
              </button>
            ))}
          </div>

          <div
            className="assistant-conversation"
            aria-live="polite"
            aria-busy={loading}
          >
            {messages.length === 0 && (
              <p className="message muted">
                As respostas usam somente o contexto acadêmico estruturado
                disponível nesta conta.
              </p>
            )}
            {messages.map((item, index) => (
              <article
                className={`assistant-message ${item.role}`}
                key={`${index}-${item.content}`}
              >
                <strong>
                  {item.role === "user" ? "Você" : "Assistente"}
                </strong>
                <p>{item.content}</p>
                {item.response?.execution_mode ===
                  "deterministic_fallback" && (
                  <span className="status-badge badge-info">
                    Modo determinístico
                  </span>
                )}
                {item.response?.study_method_catalog_version && (
                  <p className="muted">
                    Catálogo de métodos v
                    {item.response.study_method_catalog_version}
                  </p>
                )}
                {item.response?.evidence.length ? (
                  <details>
                    <summary>Evidências usadas</summary>
                    <ul>
                      {item.response.evidence.map((evidence, evidenceIndex) => (
                        <li
                          key={`${evidence.source_type}-${evidence.source_id ?? evidenceIndex}`}
                        >
                          {evidence.summary}
                        </li>
                      ))}
                    </ul>
                  </details>
                ) : null}
                {item.response?.warnings.map((warning) => (
                  <p className="message warning" key={warning}>
                    {warning}
                  </p>
                ))}
                {item.response?.suggested_actions.length ? (
                  <div className="assistant-actions">
                    {item.response.suggested_actions.map(
                      (action, actionIndex) => (
                        <button
                          className="secondary-button"
                          type="button"
                          key={
                            action.action_id ??
                            `${action.type}-${actionIndex}`
                          }
                          onClick={() => selectAction(action)}
                        >
                          {action.label}
                        </button>
                      ),
                    )}
                  </div>
                ) : null}
              </article>
            ))}
            {loading && (
              <p className="message muted">
                Validando o contexto cadastrado...
              </p>
            )}
            {notice && <p className="message success">{notice}</p>}
            {error && <p className="message error">{error}</p>}
          </div>

          {pending && (
            <section
              className="assistant-confirmation"
              aria-labelledby="assistant-confirmation-title"
            >
              <h3 id="assistant-confirmation-title">Confirmar alteração</h3>
              <p>
                {pending.label}. O backend verificará novamente acesso,
                prazo e conflitos antes de persistir.
              </p>
              <div className="button-row">
                <button
                  className="secondary-button"
                  type="button"
                  disabled={loading}
                  onClick={() => setPending(null)}
                >
                  Rejeitar
                </button>
                <button
                  type="button"
                  disabled={loading}
                  onClick={() => void confirmPending()}
                >
                  Confirmar
                </button>
              </div>
            </section>
          )}

          <form className="assistant-composer" onSubmit={submit}>
            <label>
              Mensagem
              <textarea
                value={text}
                maxLength={1000}
                onChange={(event) => setText(event.target.value)}
                placeholder="O que devo estudar no tempo disponível?"
              />
            </label>
            <button disabled={loading || !text.trim()}>Enviar</button>
          </form>
        </div>
      </aside>
    </>
  );
}
