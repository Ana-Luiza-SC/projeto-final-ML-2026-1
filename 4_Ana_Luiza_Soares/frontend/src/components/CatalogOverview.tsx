import { useState } from "react";
import {
  analyzeDisciplineComplexity,
  refreshDisciplineCatalog,
  type ComplexityAnalysis,
} from "../api/client";
import type { Discipline } from "../types";

function hoursText(value?: number | null) {
  return value != null ? `${value}h` : "Não disponível";
}

export function CatalogOverview({
  discipline,
  onRefresh,
}: {
  discipline: Discipline;
  onRefresh: (value: Discipline) => void;
}) {
  const [analysis, setAnalysis] = useState<ComplexityAnalysis | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  async function analyze(reanalyze = false) {
    setLoading(true);
    setMessage(null);
    try {
      setAnalysis(await analyzeDisciplineComplexity(discipline.id, reanalyze));
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Análise indisponível.");
    } finally {
      setLoading(false);
    }
  }
  async function refresh() {
    setLoading(true);
    setMessage(null);
    try {
      onRefresh(await refreshDisciplineCatalog(discipline.id));
    } catch (e) {
      setMessage(
        e instanceof Error
          ? e.message
          : "Catálogo indisponível; seus dados foram preservados.",
      );
    } finally {
      setLoading(false);
    }
  }
  return (
    <section className="panel stack">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Catálogo acadêmico local</p>
          <h2>Ementa</h2>
        </div>
        <button
          className="secondary-button"
          disabled={loading}
          onClick={refresh}
        >
          Atualizar catálogo
        </button>
      </div>
      <dl className="compact-grid">
        <div><dt>Carga horária total</dt><dd>{hoursText(discipline.workload_hours)}</dd></div>
        <div><dt>Ementa</dt><dd>{discipline.syllabus || "Não disponível"}</dd></div>
      </dl>
      <p className="muted">
        Origem:{" "}
        {discipline.sigaa_source_url ? "SIGAA público" : "cadastro manual"}
        {discipline.sigaa_cached_at
          ? ` · sincronizado em ${new Date(discipline.sigaa_cached_at).toLocaleString("pt-BR")}`
          : ""}
      </p>
      <div className="button-row">
        <button disabled={loading} onClick={() => void analyze(false)}>
          Analisar complexidade
        </button>
        {analysis && (
          <button
            className="secondary-button"
            disabled={loading}
            onClick={() => void analyze(true)}
          >
            Reanalisar
          </button>
        )}
      </div>
      {message && <p className="message warning">{message}</p>}
      {analysis && (
        <div className="status-box">
          <span>
            Complexidade estimada ·{" "}
            {analysis.mode === "llm" ? "análise assistida" : "regra local"}
          </span>
          <strong>
            {
              ({ low: "Baixa", medium: "Média", high: "Alta" } as const)[
                analysis.estimated_level
              ]
            }{" "}
            · confiança {Math.round(analysis.confidence * 100)}%
          </strong>
          <p>{analysis.factors.join("; ")}</p>
          {analysis.syllabus_evidence.length > 0 && (
            <details>
              <summary>Evidências da ementa</summary>
              <ul>
                {analysis.syllabus_evidence.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </details>
          )}
          {analysis.warnings.map((w) => (
            <p className="message warning" key={w}>
              {w}
            </p>
          ))}
        </div>
      )}
    </section>
  );
}
