import { useEffect, useState } from "react";
import type { Discipline, SigaaComponent, SigaaComponentSearchResponse } from "../types";

type Props = {
  discipline: Discipline;
  result: SigaaComponentSearchResponse | null;
  loading?: boolean;
  attaching?: boolean;
  error?: string | null;
  onSearch: (query: string) => void;
  onAttach: (component: SigaaComponent) => void;
};

function emptyText(value?: string | null, fallback = "Não disponível na fonte consultada.") {
  return value && value.trim() ? value : fallback;
}

function hoursText(value?: number | null) {
  return value != null ? `${value}h` : "Não disponível";
}

export function SigaaComponentPanel({
  discipline,
  result,
  loading = false,
  attaching = false,
  error = null,
  onSearch,
  onAttach,
}: Props) {
  const [query, setQuery] = useState(discipline.code ?? "");

  useEffect(() => {
    setQuery(discipline.code ?? "");
  }, [discipline.code]);

  const component = result?.component ?? null;
  const hasAttachedData = Boolean(discipline.sigaa_code || discipline.syllabus || discipline.current_program || discipline.workload_hours);

  return (
    <section className="panel sigaa-panel">
      <div className="panel-heading">
        <h2>Dados públicos do SIGAA</h2>
        <p>Consulta best-effort na fonte pública de componentes curriculares da UnB.</p>
      </div>

      <div className="sigaa-search-row">
        <label>
          Código ou nome
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="FGA0315" />
        </label>
        <button type="button" onClick={() => onSearch(query)} disabled={loading || !query.trim()}>
          {loading ? "Buscando..." : "Buscar dados no SIGAA"}
        </button>
      </div>

      {error && <p className="message error">{error}</p>}
      {result?.status === "not_found" && (
        <p className="message warning">Não foi possível encontrar esse componente na fonte pública consultada.</p>
      )}
      {result?.status === "error" && (
        <p className="message error">A consulta ao SIGAA falhou. Você ainda pode manter os dados cadastrados manualmente.</p>
      )}
      {result?.cached && <p className="message muted">Resultado carregado do cache local.</p>}
      {result?.warnings?.map((warning) => <p className="message warning" key={warning}>{warning}</p>)}

      {component && (
        <div className="sigaa-result">
          <dl>
            <div><dt>Código</dt><dd>{component.code}</dd></div>
            <div><dt>Nome</dt><dd>{component.name}</dd></div>
            <div><dt>Tipo</dt><dd>{component.type || "Não informado"}</dd></div>
            <div><dt>Unidade</dt><dd>{component.unit || "Não informada"}</dd></div>
            <div><dt>Carga horária total</dt><dd>{hoursText(component.workload_hours)}</dd></div>
            <div><dt>Carga teórica</dt><dd>{hoursText(component.theoretical_workload_hours)}</dd></div>
            <div><dt>Carga prática</dt><dd>{hoursText(component.practical_workload_hours)}</dd></div>
            <div><dt>Pré-requisitos</dt><dd>{emptyText(component.prerequisites, "Não disponível")}</dd></div>
          </dl>
          <div className="sigaa-text-block">
            <h3>Ementa</h3>
            <p>{emptyText(component.syllabus, "Ementa não disponível na fonte consultada.")}</p>
          </div>
          <div className="sigaa-text-block">
            <h3>Programa atual</h3>
            <p>{emptyText(component.current_program, "Programa atual não disponível na fonte consultada.")}</p>
          </div>
          <p><a href={component.source_url} target="_blank" rel="noreferrer">Abrir fonte pública</a></p>
          <button type="button" onClick={() => onAttach(component)} disabled={attaching}>
            {attaching ? "Associando..." : "Associar à disciplina"}
          </button>
        </div>
      )}

      {hasAttachedData && (
        <div className="sigaa-attached">
          <h3>Dados associados</h3>
          <p><strong>Código SIGAA:</strong> {discipline.sigaa_code || "Não informado"}</p>
          <p><strong>Carga horária total:</strong> {hoursText(discipline.workload_hours)}</p>
          <p><strong>Ementa:</strong> {emptyText(discipline.syllabus, "Ementa não disponível na fonte consultada.")}</p>
          <p><strong>Programa atual:</strong> {emptyText(discipline.current_program, "Programa atual não disponível na fonte consultada.")}</p>
          {discipline.sigaa_source_url && <p><a href={discipline.sigaa_source_url} target="_blank" rel="noreferrer">Fonte pública associada</a></p>}
        </div>
      )}
    </section>
  );
}
