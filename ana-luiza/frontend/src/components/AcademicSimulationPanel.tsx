import type { AcademicSimulation } from "../types";

type Props = { simulation: AcademicSimulation | null; loading?: boolean; error?: string | null };
const number = (value?: number | null) => value == null ? "Não calculado" : value.toLocaleString("pt-BR", { maximumFractionDigits: 3 });
const percentage = (value?: number | null) => value == null ? "Não calculado" : `${(value * 100).toLocaleString("pt-BR", { maximumFractionDigits: 1 })}%`;
const risk: Record<string, string> = { low: "Baixo", medium: "Médio", high: "Alto", unknown: "Não calculado" };

export function AcademicSimulationPanel({ simulation, loading = false, error = null }: Props) {
  const warnings = Array.from(new Set(simulation?.warnings ?? []));
  return <section className="panel simulation-panel">
    <div className="panel-heading"><h2>Simulação por nota</h2><p>Projeção acadêmica; frequência é analisada na aba própria.</p></div>
    {loading && <p className="message muted">Calculando...</p>}{error && <p className="message error">{error}</p>}
    {!simulation && !loading && <p className="message muted">Cadastre avaliações para iniciar a simulação.</p>}
    {simulation && <>
      <div className="simulation-summary">
        <div><span>Média parcial</span><strong>{number(simulation.partial_average)}</strong></div>
        <div><span>Peso concluído</span><strong>{percentage(simulation.completed_weight)}</strong></div>
        <div><span>Peso restante</span><strong>{percentage(simulation.remaining_weight)}</strong></div>
        <div><span>Nota necessária</span><strong>{number(simulation.required_average_on_remaining)}</strong></div>
      </div>
      {warnings.length > 0 && <div className="warnings"><h3>Avisos</h3><ul>{warnings.map(item => <li key={item}>{item}</li>)}</ul></div>}
      <details className="simulation-details"><summary>Ver cálculo completo</summary><dl>
        <div><dt>Contribuição atual</dt><dd>{number(simulation.current_contribution)}</dd></div>
        <div><dt>Média alvo</dt><dd>{number(simulation.target_average)}</dd></div>
        <div><dt>Menção final</dt><dd>{simulation.current_mention ?? "Ainda não calculável"}</dd></div>
        <div><dt>Projeção para a meta</dt><dd>{simulation.projected_mention ?? "Não calculado"}</dd></div>
        <div><dt>Risco por nota</dt><dd>{risk[simulation.grade_risk_level ?? "unknown"] ?? "Não calculado"}</dd></div>
      </dl></details>
      {(simulation.group_results?.length ?? 0) > 0 && <div className="warnings"><h3>Resultados por grupo</h3><ul>{simulation.group_results?.map(group => <li key={group.code}><strong>{group.code} — {group.name}:</strong> {group.average == null ? "Dados insuficientes" : number(group.average) + " · mínimo 5: " + (group.meets_minimum_5 ? "atingido" : "não atingido")}</li>)}</ul><p>O resultado de cada grupo não representa aprovação final.</p></div>}
    </>}
  </section>;
}
