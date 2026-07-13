import type { ReactNode } from "react";

export function PageHeader({ eyebrow, title, description, action }: { eyebrow?: string; title: string; description: string; action?: ReactNode }) {
  return <header className="page-header"><div>{eyebrow && <p className="eyebrow">{eyebrow}</p>}<h1>{title}</h1><p>{description}</p></div>{action && <div className="page-header-action">{action}</div>}</header>;
}

export function EmptyState({ title, description, action }: { title: string; description: string; action?: ReactNode }) {
  return <div className="empty-state"><div className="empty-state-mark" aria-hidden="true">E</div><h2>{title}</h2><p>{description}</p>{action}</div>;
}

export function Alert({ tone = "info", children }: { tone?: "info" | "success" | "warning" | "error"; children: ReactNode }) {
  return <div className={`alert alert-${tone}`} role={tone === "error" ? "alert" : "status"}>{children}</div>;
}

export function LoadingState({ label }: { label: string }) {
  return <div className="loading-state" role="status"><span className="spinner" aria-hidden="true" />{label}</div>;
}

export function StatusBadge({ tone = "neutral", children }: { tone?: "neutral" | "success" | "warning" | "danger" | "info"; children: ReactNode }) {
  return <span className={`status-badge badge-${tone}`}>{children}</span>;
}

export function FormSection({ title, description, children }: { title: string; description?: string; children: ReactNode }) {
  return <fieldset className="form-section"><legend>{title}</legend>{description && <p>{description}</p>}{children}</fieldset>;
}

export function StepIndicator({ steps, current }: { steps: string[]; current: number }) {
  return <ol className="step-indicator" aria-label="Progresso">{steps.map((step, index) => <li key={step} className={index < current ? "done" : index === current ? "active" : ""} aria-current={index === current ? "step" : undefined}><span>{index + 1}</span><strong>{step}</strong></li>)}</ol>;
}
