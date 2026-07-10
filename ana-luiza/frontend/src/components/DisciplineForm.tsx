import { FormEvent, useState } from "react";
import { searchSigaaComponent } from "../api/client";
import type { DisciplineCreatePayload, SigaaComponentSearchResponse } from "../types";

type Props = {
  loading?: boolean;
  onSubmit: (payload: DisciplineCreatePayload) => Promise<void>;
};

const initialForm: DisciplineCreatePayload = {
  code: "",
  name: "",
  professor: "",
  class_code: "",
  schedule_code: "",
  local: "",
};

export function DisciplineForm({ loading = false, onSubmit }: Props) {
  const [form, setForm] = useState<DisciplineCreatePayload>(initialForm);
  const [error, setError] = useState<string | null>(null);
  const [sigaaQuery, setSigaaQuery] = useState("");
  const [sigaaLoading, setSigaaLoading] = useState(false);
  const [sigaaError, setSigaaError] = useState<string | null>(null);
  const [sigaaResult, setSigaaResult] = useState<SigaaComponentSearchResponse | null>(null);

  function updateField(field: keyof DisciplineCreatePayload, value: string) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  async function handleSigaaSearch() {
    const query = sigaaQuery.trim();
    setSigaaError(null);
    setSigaaResult(null);

    if (query.length < 3) {
      setSigaaError("Digite ao menos 3 caracteres para buscar no SIGAA.");
      return;
    }

    setSigaaLoading(true);
    try {
      const result = await searchSigaaComponent(query);
      setSigaaResult(result);
      if (result.status === "not_found") {
        setSigaaError("Não foi possível encontrar esse componente na fonte pública consultada.");
      }
      if (result.status === "error") {
        setSigaaError("A consulta ao SIGAA falhou. Você ainda pode manter o cadastro manual.");
      }
    } catch (err) {
      setSigaaError(err instanceof Error ? err.message : "Não foi possível consultar o SIGAA.");
    } finally {
      setSigaaLoading(false);
    }
  }

  function clearSigaaResult() {
    setSigaaError(null);
    setSigaaResult(null);
  }

  function useSigaaComponent() {
    const component = sigaaResult?.component;
    if (!component) return;

    setForm((current) => ({
      ...current,
      code: component.code,
      name: component.name,
      sigaa_code: component.code,
      sigaa_source_url: component.source_url,
      syllabus: component.syllabus || null,
      current_program: component.current_program || null,
      workload_hours: component.workload_hours ?? null,
    }));
    setError(null);
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    if (!form.code.trim()) {
      setError("Código da disciplina é obrigatório.");
      return;
    }
    if (!form.name.trim()) {
      setError("Nome da disciplina é obrigatório.");
      return;
    }

    await onSubmit({
      code: form.code.trim(),
      name: form.name.trim(),
      professor: form.professor?.trim() || null,
      class_code: form.class_code?.trim() || null,
      schedule_code: form.schedule_code?.trim() || null,
      local: form.local?.trim() || null,
      sigaa_code: form.sigaa_code?.trim() || null,
      sigaa_source_url: form.sigaa_source_url?.trim() || null,
      syllabus: form.syllabus?.trim() || null,
      current_program: form.current_program?.trim() || null,
      workload_hours: form.workload_hours ?? null,
      sigaa_cached_at: form.sigaa_cached_at ?? null,
    });
    setForm(initialForm);
    setSigaaQuery("");
    clearSigaaResult();
  }

  const foundComponent = sigaaResult?.status === "found" ? sigaaResult.component : null;

  return (
    <form className="panel form-grid" onSubmit={handleSubmit}>
      <div className="panel-heading">
        <h2>Cadastrar disciplina</h2>
        <p>Busque dados públicos do SIGAA ou preencha manualmente se a fonte não encontrar o componente.</p>
      </div>

      <section className="sigaa-assisted-search" aria-label="Busca assistida no SIGAA">
        <label>
          Buscar no SIGAA por código ou nome
          <input
            value={sigaaQuery}
            onChange={(event) => setSigaaQuery(event.target.value)}
            placeholder="Ex.: FGA0315 ou Qualidade de Software"
          />
        </label>
        <div className="form-actions sigaa-form-actions">
          {(sigaaResult || sigaaError) && (
            <button type="button" className="secondary-button" onClick={clearSigaaResult}>
              Limpar resultado
            </button>
          )}
          <button type="button" onClick={handleSigaaSearch} disabled={sigaaLoading}>
            {sigaaLoading ? "Buscando..." : "Buscar no SIGAA"}
          </button>
        </div>

        {sigaaError && <p className="message warning">{sigaaError}</p>}

        {foundComponent && (
          <div className="sigaa-result">
            <div className="panel-heading">
              <h3>Componente encontrado</h3>
              {sigaaResult?.cached && <p className="muted">Resultado vindo do cache local.</p>}
            </div>
            <dl>
              <div>
                <dt>Código</dt>
                <dd>{foundComponent.code}</dd>
              </div>
              <div>
                <dt>Nome</dt>
                <dd>{foundComponent.name}</dd>
              </div>
              <div>
                <dt>Tipo</dt>
                <dd>{foundComponent.type || "Não informado"}</dd>
              </div>
              <div>
                <dt>Unidade</dt>
                <dd>{foundComponent.unit || "Não informada"}</dd>
              </div>
              <div>
                <dt>Carga horária</dt>
                <dd>{foundComponent.workload_hours ? `${foundComponent.workload_hours}h` : "Não informada"}</dd>
              </div>
            </dl>
            <div className="sigaa-text-block">
              <strong>Ementa</strong>
              <p>{foundComponent.syllabus || "Ementa não disponível na fonte consultada."}</p>
            </div>
            <div className="sigaa-text-block">
              <strong>Programa atual</strong>
              <p>{foundComponent.current_program || "Programa atual não disponível na fonte consultada."}</p>
            </div>
            <div className="form-actions">
              <button type="button" onClick={useSigaaComponent}>
                Usar esta disciplina
              </button>
            </div>
          </div>
        )}
      </section>

      {error && <p className="message error">{error}</p>}
      <label>
        Código *
        <input value={form.code} onChange={(event) => updateField("code", event.target.value)} placeholder="FGA0000" />
      </label>
      <label>
        Nome *
        <input value={form.name} onChange={(event) => updateField("name", event.target.value)} placeholder="Nome da disciplina" />
      </label>
      <label>
        Professor
        <input value={form.professor ?? ""} onChange={(event) => updateField("professor", event.target.value)} placeholder="Docente" />
      </label>
      <label>
        Turma
        <input value={form.class_code ?? ""} onChange={(event) => updateField("class_code", event.target.value)} placeholder="01" />
      </label>
      <label>
        Horário
        <input value={form.schedule_code ?? ""} onChange={(event) => updateField("schedule_code", event.target.value)} placeholder="24M12" />
      </label>
      <label>
        Local
        <input value={form.local ?? ""} onChange={(event) => updateField("local", event.target.value)} placeholder="Sala" />
      </label>
      <div className="form-actions">
        <button type="submit" disabled={loading}>{loading ? "Salvando..." : "Cadastrar disciplina"}</button>
      </div>
    </form>
  );
}
