import type { StudyRecommendationResponse } from "../types";

type Props = {
  recommendation: StudyRecommendationResponse | null;
  loading?: boolean;
  error?: string | null;
};

const strategyLabels: Record<string, string> = { retrieval_practice: "Prática de recuperação", spaced_practice: "Prática distribuída", interleaving: "Intercalação", concrete_examples: "Exemplos concretos ou resolvidos", self_explanation: "Autoexplicação" };
const dedicationLabels = {
  low: "baixa",
  medium: "média",
  high: "alta",
};

export function StudyRecommendationPanel({ recommendation, loading = false, error = null }: Props) {
  return (
    <section className="panel recommendation-panel">
      <div className="panel-heading">
        <h2>Recomendação de estudo</h2>
        <p>Esta recomendação é uma simulação e não substitui o resultado oficial do SIGAA.</p>
      </div>
      {loading && <p className="message muted">Gerando recomendação...</p>}
      {error && <p className="message error">{error}</p>}
      {!recommendation && !loading && !error && (
        <p className="message muted">Informe um objetivo da semana e conteúdos pendentes, se houver, para gerar uma recomendação.</p>
      )}
      {recommendation && (
        <div className="recommendation-content">
          {recommendation.used_fallback && (
            <p className="message warning">Fallback por regras usado. O backend funciona mesmo sem GOOGLE_API_KEY.</p>
          )}
          <div className="metrics-grid">
            <div><span>Dedicação recomendada</span><strong>{dedicationLabels[recommendation.dedication_level]}</strong></div>
            <div><span>Confiança</span><strong>{Math.round(recommendation.confidence * 100)}%</strong></div>
            <div><span>Provider</span><strong>{recommendation.provider}</strong></div>
            <div><span>Latência</span><strong>{recommendation.latency_ms} ms</strong></div>
          </div>

          <div className="status-box">
            <span>Resumo da situação acadêmica</span>
            <strong>{recommendation.academic_situation_summary}</strong>
          </div>
          <div className="status-box">
            <span>Situação por menção</span>
            <strong>{recommendation.grade_status}</strong>
          </div>
          <div className="status-box">
            <span>Situação por falta</span>
            <strong>{recommendation.attendance_status}</strong>
          </div>

          {(recommendation.study_actions?.length ?? 0) > 0 && <div><h3>Atividades de estudo fundamentadas</h3>{recommendation.study_actions?.map((item, index) => <article className="status-box" key={`${item.strategy_id}-${item.topic}-${index}`}><span>{strategyLabels[item.strategy_id] ?? item.strategy_id}</span><strong>{item.action}</strong>{item.topic && <p><b>Conteúdo:</b> {item.topic}</p>}<p><b>Motivo:</b> {item.reason}</p><p><b>Evidência usada:</b> {item.evidence}</p>{item.estimated_minutes && <p><b>Duração derivada:</b> {item.estimated_minutes} min</p>}<details><summary>Por que esta estratégia?</summary>{item.reference_ids.map(id => recommendation.strategy_references?.find(ref => ref.id === id)).filter(Boolean).map(ref => <p key={ref!.id}><a href={ref!.url} target="_blank" rel="noreferrer">{ref!.short_citation}</a> — {ref!.title}</p>)}</details></article>)}</div>}
          {(recommendation.study_actions?.length ?? 0) === 0 && <div>
            <h3>Ações recomendadas</h3>
            <ul>{recommendation.recommended_actions.map((action) => <li key={action}>{action}</li>)}</ul>
          </div>}
          <div>
            <h3>Motivos</h3>
            <ul>{recommendation.reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul>
          </div>
          {(recommendation.warnings?.length ?? 0) > 0 && <div><h3>Avisos</h3><ul>{recommendation.warnings?.map((item) => <li key={item}>{item}</li>)}</ul></div>}
          {(recommendation.used_evidence?.length ?? 0) > 0 && (
            <div>
              <h3>Evidências usadas</h3>
              <ul>{recommendation.used_evidence?.map((item) => <li key={item}>{item}</li>)}</ul>
            </div>
          )}
          {(recommendation.influencing_assessments?.length ?? 0) > 0 && (
            <div>
              <h3>Avaliações consideradas</h3>
              <ul>{recommendation.influencing_assessments?.map((item) => <li key={item}>{item}</li>)}</ul>
            </div>
          )}
          {recommendation.missing_information.length > 0 && (
            <div>
              <h3>Informações ausentes</h3>
              <ul>{recommendation.missing_information.map((item) => <li key={item}>{item}</li>)}</ul>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
