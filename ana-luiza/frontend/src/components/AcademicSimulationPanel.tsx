import type { AcademicSimulation } from "../types";

type Props = {
  simulation: AcademicSimulation | null;
  loading?: boolean;
  error?: string | null;
};

function formatNumber(value?: number | null, digits = 2) {
  if (value == null || Number.isNaN(value)) return "Dados insuficientes";
  return value.toLocaleString("pt-BR", { maximumFractionDigits: digits, minimumFractionDigits: digits });
}

function formatPercent(value?: number | null) {
  if (value == null || Number.isNaN(value)) return "Não informado";
  return `${(value * 100).toLocaleString("pt-BR", { maximumFractionDigits: 1 })}%`;
}

function labelRisk(value?: string | null) {
  if (!value) return "Não avaliado";
  const labels: Record<string, string> = {
    low: "baixo",
    medium: "médio",
    high: "alto",
    unknown: "desconhecido",
  };
  return labels[value] ?? value;
}

export function AcademicSimulationPanel({ simulation, loading = false, error = null }: Props) {
  const attendance = simulation?.attendance ?? null;
  const academicStatus = simulation?.academic_status ?? null;
  const warnings = Array.from(new Set([...(simulation?.warnings ?? []), ...(attendance?.warnings ?? []), ...(academicStatus?.warnings ?? [])]));
  const reasons = simulation?.reasons ?? [];
  const hasUnknownAttendance = attendance?.status === "unknown" || attendance?.frequency == null;
  const hasPendingAssessments = (simulation?.remaining_weight ?? 0) > 0;

  return (
    <section className="panel simulation-panel">
      <div className="panel-heading">
        <h2>Situação simulada</h2>
        <p>A simulação não substitui o resultado oficial do SIGAA.</p>
      </div>
      {loading && <p className="message muted">Calculando simulação...</p>}
      {error && <p className="message error">{error}</p>}
      {!simulation && !loading && !error && (
        <p className="message muted">Cadastre ao menos uma avaliação para simular a menção. Informe frequência ou faltas para avaliar risco por falta.</p>
      )}
      {simulation && (
        <>
          <div className="metrics-grid">
            <div><span>Contribuição atual</span><strong>{formatNumber(simulation.current_contribution)}</strong></div>
            <div><span>Média parcial</span><strong>{formatNumber(simulation.partial_average)}</strong></div>
            <div><span>Peso concluído</span><strong>{formatPercent(simulation.completed_weight)}</strong></div>
            <div><span>Peso restante</span><strong>{formatPercent(simulation.remaining_weight)}</strong></div>
            <div><span>Média alvo</span><strong>{formatNumber(simulation.target_average)}</strong></div>
            <div><span>Nota necessária</span><strong>{formatNumber(simulation.required_average_on_remaining)}</strong></div>
            <div><span>Menção atual</span><strong className="mention">{simulation.current_mention ?? "Dados insuficientes"}</strong></div>
            <div><span>Menção projetada</span><strong className="mention">{simulation.projected_mention ?? "Dados insuficientes"}</strong></div>
            <div><span>Risco por nota</span><strong>{labelRisk(simulation.grade_risk_level)}</strong></div>
            <div><span>Frequência informada</span><strong>{formatPercent(attendance?.frequency)}</strong></div>
            <div><span>Percentual de faltas</span><strong>{formatPercent(attendance?.absence_percentage)}</strong></div>
            <div><span>Risco por falta</span><strong>{labelRisk(attendance?.risk_level)}</strong></div>
          </div>

          <div className="status-box">
            <span>Status acadêmico</span>
            <strong>{academicStatus?.message ?? "Dados insuficientes para conclusão final."}</strong>
            {(hasUnknownAttendance || hasPendingAssessments) && (
              <p>Dados insuficientes para conclusão final. Não há afirmação de aprovação definitiva.</p>
            )}
          </div>

          {reasons.length > 0 && (
            <div>
              <h3>Reasons</h3>
              <ul>{reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul>
            </div>
          )}

          {warnings.length > 0 ? (
            <div className="warnings">
              <h3>Warnings</h3>
              <ul>{warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul>
            </div>
          ) : (
            <p className="message muted">Nenhum warning retornado pela simulação.</p>
          )}
        </>
      )}
    </section>
  );
}
