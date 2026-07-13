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

const levelLabels = {
  insufficient_evidence: "Evidência insuficiente",
  low: "Baixa",
  moderate: "Moderada",
  high: "Alta",
} as const;

const factorLabels = {
  conceptual_breadth: "Amplitude conceitual",
  prerequisite_depth: "Profundidade de pré-requisitos",
  mathematical_or_algorithmic_density: "Densidade matemática ou algorítmica",
  project_workload: "Carga de projeto",
  assessment_concentration: "Concentração de avaliações",
} as const;

const factorValueLabels = {
  unknown: "desconhecida",
  low: "baixa",
  moderate: "moderada",
  high: "alta",
} as const;

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
          Analisar demanda
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
            Demanda estimada de estudo · regra determinística
          </span>
          <strong>
            {levelLabels[analysis.demand_level]} · cobertura de evidências{" "}
            {Math.round(analysis.evidence_coverage * 100)}%
          </strong>
          <details>
            <summary>Por quê?</summary>
            <dl className="demand-factors">
              {Object.entries(analysis.factors).map(([factor, level]) => (
                <div key={factor}>
                  <dt>{factorLabels[factor as keyof typeof factorLabels]}</dt>
                  <dd>{factorValueLabels[level]}</dd>
                </div>
              ))}
            </dl>
            {analysis.evidence_used.length > 0 && (
              <>
                <h3>Evidências usadas</h3>
                <ul>
                  {analysis.evidence_used.map((item) => (
                    <li key={`${item.type}-${item.summary}`}>{item.summary}</li>
                  ))}
                </ul>
              </>
            )}
            {analysis.missing_evidence.length > 0 && (
              <p>Dados ausentes: {analysis.missing_evidence.join(", ")}.</p>
            )}
            <h3>Dificuldade específica para você</h3>
            <p>
              {levelLabels[analysis.learner_specific_difficulty.level]} · cobertura{" "}
              {Math.round(analysis.learner_specific_difficulty.confidence * 100)}%
            </p>
          </details>
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
