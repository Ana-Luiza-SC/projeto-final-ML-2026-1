import { useState, type ReactNode } from "react";
import { getApiBaseUrl } from "../api/client";

type Page = "home" | "disciplines" | "discipline" | "study-plan" | "matricula-import";
type Props = { activePage: Page; onNavigate: (page: Exclude<Page, "discipline">) => void; children: ReactNode };

const items: { page: Exclude<Page, "discipline">; label: string }[] = [
  { page: "home", label: "Início" }, { page: "disciplines", label: "Disciplinas" },
  { page: "study-plan", label: "Planejamento" }, { page: "matricula-import", label: "Importar comprovante" },
];

export function AppShell({ activePage, onNavigate, children }: Props) {
  const [open, setOpen] = useState(false);
  const api = getApiBaseUrl();
  return <div className="app-shell">
    <header className="topbar">
      <button className="brand-button" onClick={() => onNavigate("home")} aria-label="Ir para o início"><span className="brand-mark">E</span><span><strong>EstudaUnB</strong><small>Organização acadêmica</small></span></button>
      <button className="menu-button" type="button" aria-expanded={open} aria-controls="main-navigation" onClick={() => setOpen((value) => !value)}>{open ? "Fechar" : "Menu"}</button>
      <nav id="main-navigation" className={open ? "open" : ""} aria-label="Navegação principal">
        {items.map((item) => <button key={item.page} className={(activePage === item.page || (activePage === "discipline" && item.page === "disciplines")) ? "active" : ""} aria-current={(activePage === item.page || (activePage === "discipline" && item.page === "disciplines")) ? "page" : undefined} onClick={() => { onNavigate(item.page); setOpen(false); }}>{item.label}</button>)}
      </nav>
    </header>
    <main>{children}</main>
    <footer className="app-footer"><span>EstudaUnB · Universidade de Brasília</span><details><summary>Desenvolvedor</summary><a href={`${api}/docs`} target="_blank" rel="noreferrer">Swagger</a><a href={`${api}/redoc`} target="_blank" rel="noreferrer">ReDoc</a></details></footer>
  </div>;
}
