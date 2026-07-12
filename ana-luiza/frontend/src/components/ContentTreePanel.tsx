import { FormEvent, useMemo, useState } from "react";
import { confirmContentExtraction, createContentNode, deleteContentNode, previewContentExtraction, updateContentNode } from "../api/client";
import type { ContentDraftNode, ContentExtractionPreview, ContentNode, ContentNodePayload } from "../types";

type Editor = { parentId?: string | null; node?: ContentNode | null } | null;

const statusLabels = { not_started: "Não iniciado", in_progress: "Em andamento", studied: "Estudado", reviewed: "Revisado" };
const difficultyLabels = { low: "Baixa", medium: "Média", high: "Alta" };

function flatten(nodes: ContentNode[]): ContentNode[] { return nodes.flatMap((node) => [node, ...flatten(node.children)]); }
function subtreeIds(node: ContentNode): Set<string> { return new Set([node.id, ...flatten(node.children).map((item) => item.id)]); }

export function ContentTreePanel({ disciplineId, nodes, hasConfirmedPlan, loading = false, onChanged }: { disciplineId: string; nodes: ContentNode[]; hasConfirmedPlan: boolean; loading?: boolean; onChanged: () => Promise<void> }) {
  const [editor, setEditor] = useState<Editor>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [extracting, setExtracting] = useState(false);
  const [preview, setPreview] = useState<ContentExtractionPreview | null>(null);
  const allNodes = useMemo(() => flatten(nodes), [nodes]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editor) return;
    const data = new FormData(event.currentTarget);
    const payload: ContentNodePayload = {
      parent_id: editor.node ? (String(data.get("parent_id") ?? "") || null) : editor.parentId,
      title: String(data.get("title") ?? "").trim(),
      description: String(data.get("description") ?? "").trim() || null,
      difficulty: (String(data.get("difficulty") ?? "") || null) as ContentNodePayload["difficulty"],
      status: String(data.get("status")) as ContentNodePayload["status"],
    };
    setSaving(true); setError(null); setNotice(null);
    try {
      if (editor.node) await updateContentNode(disciplineId, editor.node.id, payload);
      else await createContentNode(disciplineId, payload, editor.parentId);
      setEditor(null); setNotice("Conteúdo salvo.");
      await onChanged();
    } catch (err) { setError(err instanceof Error ? err.message : "Não foi possível salvar o conteúdo."); }
    finally { setSaving(false); }
  }

  async function remove(node: ContentNode) {
    setError(null); setNotice(null);
    try { await deleteContentNode(disciplineId, node.id); setNotice("Conteúdo excluído."); await onChanged(); }
    catch (err) { setError(err instanceof Error ? err.message : "Não foi possível excluir. Remova filhos e associações primeiro."); }
  }

  async function extractPreview() {
    if (!hasConfirmedPlan) return;
    setExtracting(true); setError(null); setNotice(null);
    try { setPreview(await previewContentExtraction(disciplineId)); }
    catch (err) { setError(err instanceof Error ? err.message : "Não foi possível extrair os conteúdos. Use o cadastro manual."); }
    finally { setExtracting(false); }
  }

  function updateDraft(id: string, patch: Partial<ContentDraftNode>) {
    setPreview((current) => current ? { ...current, draft_nodes: current.draft_nodes.map((item) => item.temporary_id === id ? { ...item, ...patch } : item) } : current);
  }

  function removeDraft(id: string) {
    setPreview((current) => current ? { ...current, draft_nodes: current.draft_nodes.filter((item) => item.temporary_id !== id).map((item) => item.parent_temporary_id === id ? { ...item, parent_temporary_id: null } : item) } : current);
  }

  async function confirmPreview() {
    if (!preview) return;
    setSaving(true); setError(null); setNotice(null);
    try {
      const result = await confirmContentExtraction(disciplineId, preview.preview_id, preview.draft_nodes);
      setPreview(null); setNotice(`${result.created_count} conteúdo(s) confirmado(s) e salvos.`);
      await onChanged();
    } catch (err) { setError(err instanceof Error ? err.message : "Não foi possível confirmar a árvore. Revise a hierarquia."); }
    finally { setSaving(false); }
  }

  function branch(node: ContentNode, depth = 0) {
    return <div className="content-tree-node" key={node.id} style={{ marginLeft: depth ? 18 : 0 }}>
      <details open><summary><strong>{node.title}</strong> · {statusLabels[node.status]}{node.difficulty ? ` · dificuldade ${difficultyLabels[node.difficulty].toLowerCase()}` : ""}</summary>
        {node.description && <p>{node.description}</p>}
        <div className="button-row"><button type="button" onClick={() => setEditor({ parentId: node.id })}>Adicionar filho</button><button className="secondary-button" type="button" onClick={() => setEditor({ node })}>Editar ou mover</button><button className="secondary-button" type="button" onClick={() => void remove(node)}>Excluir</button></div>
        {node.children.map((child) => branch(child, depth + 1))}
      </details>
    </div>;
  }

  const unavailableParents = editor?.node ? subtreeIds(editor.node) : new Set<string>();
  return <section className="panel stack">
    <div className="section-heading"><div><h2>Mapa de conteúdos</h2><p>A hierarquia registra organização, não pré-requisitos automáticos.</p></div><div className="button-row"><button type="button" disabled={extracting || !hasConfirmedPlan} onClick={() => void extractPreview()}>{extracting ? "Extraindo..." : "Extrair do plano de ensino"}</button><button className="secondary-button" type="button" onClick={() => setEditor({ parentId: null })}>Adicionar conteúdo manualmente</button></div></div>
    {!hasConfirmedPlan && <p className="message muted">Confirme um plano de ensino para usar a extração assistida. O cadastro manual continua disponível.</p>}
    {error && <p className="message error">{error}</p>}
    {notice && <p className="message success">{notice}</p>}
    {loading ? <p className="message muted">Carregando conteúdos...</p> : nodes.length === 0 ? <p className="message muted">Nenhum conteúdo cadastrado.</p> : <div className="content-tree">{nodes.map((node) => branch(node))}</div>}

    {preview && <section className="stack" aria-label="Prévia da extração de conteúdos">
      <div><h3>Revisar proposta do plano de ensino</h3><p>Nenhum conteúdo foi salvo. Edite ou remova itens antes de confirmar.</p></div>
      {preview.used_fallback && <p className="message warning">Fallback identificado: {preview.fallback_reason}. Revise a proposta com atenção.</p>}
      {preview.warnings.map((warning) => <p className="message warning" key={warning}>{warning}</p>)}
      {preview.draft_nodes.length === 0 && <p className="message muted">Nenhum conteúdo explícito foi encontrado. Use o cadastro manual.</p>}
      {preview.draft_nodes.map((draft) => <div className="status-box form-grid" key={draft.temporary_id}>
        <label>Título<input maxLength={120} value={draft.title} onChange={(event) => updateDraft(draft.temporary_id, { title: event.target.value })} /></label>
        <label>Descrição<textarea maxLength={500} value={draft.description ?? ""} onChange={(event) => updateDraft(draft.temporary_id, { description: event.target.value || null })} /></label>
        <label>Pai<select value={draft.parent_temporary_id ?? ""} onChange={(event) => updateDraft(draft.temporary_id, { parent_temporary_id: event.target.value || null })}><option value="">Nó raiz</option>{preview.draft_nodes.filter((candidate) => candidate.temporary_id !== draft.temporary_id).map((candidate) => <option key={candidate.temporary_id} value={candidate.temporary_id}>{candidate.title}</option>)}</select></label>
        <details><summary>Ver evidência e confiança</summary><p>{draft.source_evidence}</p><p>Confiança: {Math.round(draft.confidence * 100)}%{draft.confidence < .7 ? " · ambíguo" : ""}</p>{draft.warnings.map((warning) => <p className="message warning" key={warning}>{warning}</p>)}</details>
        <button className="secondary-button" type="button" onClick={() => removeDraft(draft.temporary_id)}>Remover da proposta</button>
      </div>)}
      <div className="form-actions"><button className="secondary-button" type="button" onClick={() => setPreview(null)}>Cancelar</button><button type="button" disabled={saving || preview.draft_nodes.length === 0} onClick={() => void confirmPreview()}>{saving ? "Salvando..." : "Confirmar e salvar árvore"}</button></div>
    </section>}

    {editor && <form className="form-grid" onSubmit={submit}>
      <h3>{editor.node ? "Editar ou mover conteúdo" : editor.parentId ? "Adicionar conteúdo filho" : "Adicionar conteúdo raiz"}</h3>
      <label>Título<input name="title" required maxLength={120} defaultValue={editor.node?.title ?? ""} /></label>
      <label>Descrição<textarea name="description" maxLength={500} defaultValue={editor.node?.description ?? ""} /></label>
      {editor.node && <label>Pai<select name="parent_id" defaultValue={editor.node.parent_id ?? ""}><option value="">Nó raiz</option>{allNodes.filter((candidate) => !unavailableParents.has(candidate.id)).map((candidate) => <option key={candidate.id} value={candidate.id}>{candidate.title}</option>)}</select></label>}
      <label>Dificuldade<select name="difficulty" defaultValue={editor.node?.difficulty ?? ""}><option value="">Não informada</option><option value="low">Baixa</option><option value="medium">Média</option><option value="high">Alta</option></select></label>
      <label>Estado<select name="status" defaultValue={editor.node?.status ?? "not_started"}>{Object.entries(statusLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
      <div className="form-actions"><button className="secondary-button" type="button" onClick={() => setEditor(null)}>Cancelar</button><button disabled={saving}>{saving ? "Salvando..." : "Salvar"}</button></div>
    </form>}
  </section>;
}
