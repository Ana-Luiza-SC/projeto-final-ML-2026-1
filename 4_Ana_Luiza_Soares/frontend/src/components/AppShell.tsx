import { useState, type ReactNode } from "react";
import { getApiBaseUrl, type AuthUser } from "../api/client";
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
};
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
}: Props) {
  const [open, setOpen] = useState(false);
  const api = getApiBaseUrl();
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
        <div className="user-session">
          <span>{user.email}</span>
          <button className="secondary-button" onClick={onLogout}>
            Sair
          </button>
        </div>
      </header>
      <main>{children}</main>
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
