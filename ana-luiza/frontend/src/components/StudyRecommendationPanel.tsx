import type { StudyRecommendationResponse } from "../types";

type Props = {
  recommendation: StudyRecommendationResponse | null;
  loading?: boolean;
  error?: string | null;
};

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

          <div>
            <h3>Ações recomendadas</h3>
            <ul>{recommendation.recommended_actions.map((action) => <li key={action}>{action}</li>)}</ul>
          </div>
          <div>
            <h3>Motivos</h3>
            <ul>{recommendation.reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul>
          </div>
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
