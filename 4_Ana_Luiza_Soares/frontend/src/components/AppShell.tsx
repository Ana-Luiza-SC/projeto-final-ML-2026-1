import { useCallback, useEffect, useState, type ReactNode } from "react";
import { getApiBaseUrl, type AuthUser } from "../api/client";
import { ContextualAssistantDrawer } from "./ContextualAssistantDrawer";
type Page =
  | "home"
  | "disciplines"
  | "discipline"
  | "study-plan"
  | "calendar"
  | "matricula-import";
type Props = {
  activePage: Page;
  onNavigate: (page: Exclude<Page, "discipline">) => void;
  children: ReactNode;
  user: AuthUser;
  onLogout: () => void;
  selectedDisciplineId?: string | null;
  onNavigatePath: (path: string) => void;
};
const ASSISTANT_OPEN_KEY = "estudaunb_assistant_open";
const items: { page: Exclude<Page, "discipline">; label: string }[] = [
  { page: "home", label: "Início" },
  { page: "disciplines", label: "Disciplinas" },
  { page: "study-plan", label: "Planejamento" },
  { page: "calendar", label: "Calendário" },
  { page: "matricula-import", label: "Importar comprovante" },
];
export function AppShell({
  activePage,
  onNavigate,
  children,
  user,
  onLogout,
  selectedDisciplineId,
  onNavigatePath,
}: Props) {
  const [open, setOpen] = useState(false);
  const [assistantOpen, setAssistantOpen] = useState(
    () => localStorage.getItem(ASSISTANT_OPEN_KEY) === "true",
  );
  const api = getApiBaseUrl();
  const closeAssistant = useCallback(() => setAssistantOpen(false), []);

  useEffect(() => {
    localStorage.setItem(
      ASSISTANT_OPEN_KEY,
      assistantOpen ? "true" : "false",
    );
  }, [assistantOpen]);

  useEffect(() => {
    const showAssistant = () => setAssistantOpen(true);
    window.addEventListener("estudaunb:open-assistant", showAssistant);
    return () =>
      window.removeEventListener(
        "estudaunb:open-assistant",
        showAssistant,
      );
  }, []);
  return (
    <div className="app-shell">
      <header className="topbar">
        <button
          className="brand-button"
          onClick={() => onNavigate("home")}
          aria-label="Ir para o início"
        >
          <span className="brand-mark">E</span>
          <span>
            <strong>EstudaUnB</strong>
            <small>Organização acadêmica</small>
          </span>
        </button>
        <button
          className="menu-button"
          type="button"
          aria-expanded={open}
          onClick={() => setOpen((v) => !v)}
        >
          {open ? "Fechar" : "Menu"}
        </button>
        <nav
          id="main-navigation"
          className={open ? "open" : ""}
          aria-label="Navegação principal"
        >
          {items.map((item) => (
            <button
              key={item.page}
              className={
                activePage === item.page ||
                (activePage === "discipline" && item.page === "disciplines")
                  ? "active"
                  : ""
              }
              onClick={() => {
                onNavigate(item.page);
                setOpen(false);
              }}
            >
              {item.label}
            </button>
          ))}
        </nav>
        <button
          className="assistant-toggle"
          type="button"
          aria-expanded={assistantOpen}
          onClick={() => setAssistantOpen((current) => !current)}
        >
          Assistente
        </button>
        <div className="user-session">
          <span>{user.display_name || user.email}</span>
          <button className="secondary-button" onClick={onLogout}>
            Sair
          </button>
        </div>
      </header>
      <main>{children}</main>
      <ContextualAssistantDrawer
        open={assistantOpen}
        route={activePage}
        disciplineId={selectedDisciplineId}
        onClose={closeAssistant}
        onNavigatePath={(path) => {
          onNavigatePath(path);
          closeAssistant();
        }}
      />
      <footer className="app-footer">
        <span>EstudaUnB · Universidade de Brasília</span>
        <details>
          <summary>Desenvolvedor</summary>
          <a href={`${api}/docs`} target="_blank" rel="noreferrer">
            Swagger
          </a>
          <a href={`${api}/redoc`} target="_blank" rel="noreferrer">
            ReDoc
          </a>
        </details>
      </footer>
    </div>
  );
}
