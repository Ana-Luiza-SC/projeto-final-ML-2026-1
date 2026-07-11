import { useMemo, useState } from "react";
import { confirmMatriculaImport, previewMatriculaPdf } from "../api/client";
import type { ImportPreviewItem, MatriculaImportConfirmResponse, MatriculaPdfPreviewResponse } from "../types";
import { PageHeader, StatusBadge, StepIndicator } from "../components/ui";

type Props = {
  onOpenDisciplines: () => void;
};

const STATUS_LABELS: Record<string, string> = {
  recognized: "Válido",
  ambiguous: "Requer correção",
  not_found: "Válido sem confirmação do SIGAA",
  duplicate: "Duplicado",
  activity: "Atividade ignorada",
  rejected: "Inválido",
};

function canSelect(item: ImportPreviewItem) {
  return item.item_type === "discipline" && !["duplicate", "activity", "rejected"].includes(item.status);
}

export function MatriculaImportPage({ onOpenDisciplines }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<MatriculaPdfPreviewResponse | null>(null);
  const [items, setItems] = useState<ImportPreviewItem[]>([]);
  const [result, setResult] = useState<MatriculaImportConfirmResponse | null>(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedCount = useMemo(
    () => items.filter((item) => item.selected && canSelect(item) && item.code && item.name).length,
    [items],
  );

  function updateItem(id: string, patch: Partial<ImportPreviewItem>) {
    setItems((current) => current.map((item) => (item.preview_item_id === id ? { ...item, ...patch } : item)));
  }

  async function handlePreview(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file) {
      setError("Selecione um PDF antes de enviar.");
      return;
    }
    setLoadingPreview(true);
    setError(null);
    setResult(null);
    try {
      const response = await previewMatriculaPdf(file);
      setPreview(response);
      setItems(response.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível processar o PDF.");
    } finally {
      setLoadingPreview(false);
    }
  }

  async function handleConfirm() {
    if (!preview) return;
    setConfirming(true);
    setError(null);
    try {
      const response = await confirmMatriculaImport({
        preview_id: preview.preview_id,
        items: items.map((item) => ({
          preview_item_id: item.preview_item_id,
          selected: item.selected,
          code: item.code,
          name: item.name,
          class_code: item.class_code,
          schedule_code: item.schedule_code,
          local: item.local,
        })),
      });
      setResult(response);
      if (response.created.length > 0) {
        setPreview(null);
        setItems([]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível confirmar a importação.");
    } finally {
      setConfirming(false);
    }
  }

  return (
    <div className="page import-page">
      <PageHeader eyebrow="Importação" title="Importar comprovante" description="Envie o PDF, revise os componentes reconhecidos e confirme apenas o que deseja cadastrar." />

      <StepIndicator steps={["Selecionar arquivo", "Revisar componentes", "Confirmar cadastro", "Resultado"]} current={result ? 3 : preview ? 1 : 0} />
      {error && <p className="message error">{error}</p>}

      <section className="panel import-upload-panel">
        <form className="form-grid" onSubmit={handlePreview}>
          <label>
            PDF do comprovante
            <input
              type="file"
              accept="application/pdf,.pdf"
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            />
          </label>
          <p className="muted">Limite do MVP: um PDF por envio, até 10 MiB. O upload não cadastra disciplinas.</p>
          <div className="form-actions import-actions import-action-bar">
            <button type="button" className="secondary-button" onClick={onOpenDisciplines}>Cadastro manual</button>
            <button type="submit" disabled={loadingPreview}>{loadingPreview ? "Processando..." : "Gerar pré-visualização"}</button>
          </div>
        </form>
      </section>

      {preview && (
        <section className="panel import-preview-panel">
          <div className="panel-heading">
            <p className="eyebrow">Pré-visualização</p>
            <h2>Revise antes de confirmar</h2>
            <p>Expira em {new Date(preview.expires_at).toLocaleTimeString()}. Itens duplicados ou atividades não serão cadastrados.</p>
          </div>

          <p className="message muted"><strong>Nenhuma disciplina foi cadastrada ainda.</strong> Esta pré-visualização fica apenas na memória do servidor por tempo limitado; o PDF já foi descartado.</p>
          <div className="import-summary" aria-label="Resumo da pré-visualização">
            <span><strong>{preview.summary.recognized_count + preview.summary.not_found_count}</strong> válidas</span>
            <span><strong>{preview.summary.ambiguous_count}</strong> requerem correção</span>
            <span><strong>{preview.summary.duplicate_count}</strong> duplicadas</span>
            <span><strong>{preview.summary.activity_count}</strong> ignoradas</span>
            <span><strong>{preview.summary.rejected_count}</strong> inválidas</span>
          </div>
          {preview.warnings.map((warning) => <p key={warning} className="message warning">{warning}</p>)}

          <div className="import-items">
            {items.length === 0 && <p className="message warning">Nenhuma disciplina reconhecida. Use o cadastro manual.</p>}
            {items.map((item) => (
              <div className={`import-item status-${item.status}`} key={item.preview_item_id}>
                <label className="checkbox-row">
                  <input
                    type="checkbox"
                    checked={item.selected}
                    disabled={!canSelect(item)}
                    onChange={(event) => updateItem(item.preview_item_id, { selected: event.target.checked })}
                  />
                  <StatusBadge tone={item.status === "recognized" ? "success" : item.status === "ambiguous" ? "warning" : item.status === "activity" ? "neutral" : "danger"}>{STATUS_LABELS[item.status]}</StatusBadge>
                </label>
                <div className="import-item-grid">
                  <label>
                    Código
                    <input aria-invalid={!item.code} disabled={item.item_type === "activity"} value={item.code ?? ""} onChange={(event) => updateItem(item.preview_item_id, { code: event.target.value })} />
                  </label>
                  <label>
                    Nome
                    <input aria-invalid={!item.name} disabled={item.item_type === "activity"} value={item.name ?? ""} onChange={(event) => updateItem(item.preview_item_id, { name: event.target.value })} />
                  </label>
                  <label>
                    Turma
                    <input disabled={item.item_type === "activity"} value={item.class_code ?? ""} onChange={(event) => updateItem(item.preview_item_id, { class_code: event.target.value })} />
                  </label>
                  <label>
                    Horário
                    <input disabled={item.item_type === "activity"} value={item.schedule_code ?? ""} onChange={(event) => updateItem(item.preview_item_id, { schedule_code: event.target.value })} />
                  </label>
                </div>
                <div className="import-item-footer">
                  <span>Origem: {item.source === "pdf_local_sigaa_enriched" ? "PDF + SIGAA público" : "PDF local"}</span>
                  <button type="button" className="secondary-button" onClick={() => updateItem(item.preview_item_id, { selected: false })}>Remover item</button>
                </div>
                {item.warnings.map((warning) => <p key={warning} className="muted">{warning}</p>)}
              </div>
            ))}
          </div>

          <div className="form-actions import-actions import-action-bar">
            <button type="button" className="secondary-button" onClick={onOpenDisciplines}>Cadastro manual</button>
            <button type="button" onClick={handleConfirm} disabled={confirming || selectedCount === 0}>
              {confirming ? "Confirmando..." : `Confirmar disciplinas (${selectedCount})`}
            </button>
          </div>
        </section>
      )}

      {result && (
        <section className="panel import-result-panel">
          <p className="eyebrow">Relatório</p>
          <h2>Resultado da importação</h2>
          <div className="metrics-grid">
            <div><span>Cadastradas</span><strong>{result.summary.created_count}</strong></div>
            <div><span>Duplicadas</span><strong>{result.summary.duplicate_count}</strong></div>
            <div><span>Rejeitadas</span><strong>{result.summary.rejected_count}</strong></div>
            <div><span>Ignoradas</span><strong>{result.summary.skipped_count}</strong></div>
          </div>
          {result.warnings.map((warning) => <p key={warning} className="message warning">{warning}</p>)}
          <div className="import-report-grid">
            <div>
              <h3>Cadastradas</h3>
              {result.created.length === 0 ? <p className="muted">Nenhum item cadastrado.</p> : result.created.map((item) => <p key={item.preview_item_id}>{item.code} · {item.name}</p>)}
            </div>
            <div>
              <h3>Duplicadas e rejeitadas</h3>
              {[...result.duplicates, ...result.rejected].length === 0 ? <p className="muted">Sem bloqueios.</p> : [...result.duplicates, ...result.rejected].map((item) => <p key={item.preview_item_id}>{item.code ?? "Sem código"} · {item.reason}</p>)}
            </div>
          </div>
          <div className="form-actions import-actions import-action-bar">
            <button type="button" onClick={onOpenDisciplines}>Ver disciplinas</button>
          </div>
        </section>
      )}
    </div>
  );
}
