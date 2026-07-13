import { FormEvent, type ReactNode, useEffect, useMemo, useState } from "react";
import {
  attachSigaaComponent,
  completeAssessment,
  confirmCoursePlan,
  createAbsence,
  createAssessment,
  createStudyRecommendation,
  deleteAbsence,
  deleteAssessment,
  deleteCoursePlan,
  getAcademicSimulation,
  getAttendanceSummary,
  getCoursePlan,
  getDiscipline,
  listAbsences,
  listAssessments,
  listContentNodes,
  getAssessmentContentAssociation,
  setAssessmentContentAssociation,
  previewCoursePlan,
  searchSigaaComponent,
  updateAbsence,
  updateAssessment,
} from "../api/client";
import { AcademicSimulationPanel } from "../components/AcademicSimulationPanel";
import { DisciplineAssistantChat } from "../components/DisciplineAssistantChat";
import { PendingTopicsForm } from "../components/PendingTopicsForm";
import { SigaaComponentPanel } from "../components/SigaaComponentPanel";
import { StudyRecommendationPanel } from "../components/StudyRecommendationPanel";
import { ContentTreePanel } from "../components/ContentTreePanel";
import type {
  Absence,
  AbsencePayload,
  AcademicSimulation,
  Assessment,
  AssessmentPayload,
  CoursePlanData,
  CoursePlanPreviewResponse,
  Discipline,
  SigaaComponent,
  SigaaComponentSearchResponse,
  StudyRecommendationResponse,
  StudyTopicInput,
  AttendanceSummary,
  ContentNode,
  AssessmentContentSelection,
  AssessmentContentAssociation,
} from "../types";

type Props = { disciplineId: string; onBack: () => void };
type Tab = "overview" | "contents" | "assessments" | "attendance" | "coursePlan" | "recommendations";
type AssessmentAction = "planned" | "completed" | "grade" | "edit" | null;
type AbsenceAction = "create" | "edit" | null;

const tabLabels: Record<Tab, string> = {
  overview: "Visão geral",
  assessments: "Avaliações",
  attendance: "Frequência",
  coursePlan: "Plano de ensino",
  contents: "Conteúdos",
  recommendations: "Recomendações",
};

function percent(value?: number | null) {
  if (value == null) return "Não calculado";
  return `${(value * 100).toFixed(1)}%`;
}

function numberText(value?: number | null, suffix = "") {
  return value == null ? "Não informado" : `${Number(value).toFixed(2).replace(/\.00$/, "")}${suffix}`;
}

function effectiveWeight(item: Assessment) {
  if (item.group_final_weight != null && item.group_weight != null) return item.group_final_weight * item.group_weight / 100;
  return item.weight ?? null;
}

function topicsToText(topics?: string[]) {
  return (topics ?? []).join(", ");
}

function textToTopics(value: string) {
  return value.split(",").map((item) => item.trim()).filter(Boolean);
}

function ContentSelectionEditor({ nodes, selections, onChange }: { nodes: ContentNode[]; selections: AssessmentContentSelection[]; onChange: (value: AssessmentContentSelection[]) => void }) {
  const selected = new Map(selections.map((item) => [item.content_node_id, item]));
  function update(nodeId: string, checked: boolean, includeDescendants = false) {
    const rest = selections.filter((item) => item.content_node_id !== nodeId);
    onChange(checked ? [...rest, { content_node_id: nodeId, include_descendants: includeDescendants }] : rest);
  }
  function rows(items: ContentNode[], depth = 0): ReactNode[] {
    return items.flatMap((node) => {
      const selection = selected.get(node.id);
      return [<div className={`content-selection-row content-selection-depth-${Math.min(depth, 5)}`} key={node.id}>
        <label className="content-selection-label"><input className="content-checkbox" type="checkbox" checked={Boolean(selection)} onChange={(event) => update(node.id, event.target.checked, selection?.include_descendants)} /> {node.title}</label>
        {selection && node.children.length > 0 && <label className="content-selection-label"><input className="content-checkbox" type="checkbox" checked={selection.include_descendants} onChange={(event) => update(node.id, true, event.target.checked)} /> incluir descendentes</label>}
      </div>, ...rows(node.children, depth + 1)];
    });
  }
  return <fieldset><legend>Conteúdos associados</legend>{nodes.length ? rows(nodes) : <p className="message muted">Cadastre conteúdos na aba Conteúdos para associá-los.</p>}<p className="muted">{selections.length ? `${selections.length} seleção(ões) original(is).` : "Nenhum conteúdo associado."}</p></fieldset>;
}

function AssessmentEditor({
  action,
  assessment,
  loading,
  contentNodes,
  initialSelections,
  onCancel,
  onSubmit,
}: {
  action: Exclude<AssessmentAction, null>;
  assessment?: Assessment | null;
  loading: boolean;
  contentNodes: ContentNode[];
  initialSelections: AssessmentContentSelection[];
  onCancel: () => void;
  onSubmit: (payload: AssessmentPayload, selections: AssessmentContentSelection[]) => Promise<void>;
}) {
  const [name, setName] = useState(assessment?.name ?? "");
  const [date, setDate] = useState(assessment?.date ?? "");
  const [weight, setWeight] = useState(assessment?.weight == null ? "" : String(assessment.weight));
  const [grade, setGrade] = useState(assessment?.grade == null ? "" : String(assessment.grade));
  const [topics, setTopics] = useState(topicsToText(assessment?.topics));
  const [notes, setNotes] = useState(assessment?.notes ?? "");
  const [error, setError] = useState<string | null>(null);
  const [contentSelections, setContentSelections] = useState<AssessmentContentSelection[]>(initialSelections);

  const isGradeOnly = action === "grade";
  const isCompleted = action === "completed" || action === "grade" || (action === "edit" && assessment?.status === "completed");

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    if (!isGradeOnly && !name.trim()) return setError("Nome da avaliação é obrigatório.");
    const parsedWeight = weight.trim() === "" ? null : Number(weight);
    if (parsedWeight != null && (!Number.isFinite(parsedWeight) || parsedWeight <= 0 || parsedWeight > 100)) {
      return setError("Peso deve ser maior que 0 e no máximo 100.");
    }
    const parsedGrade = grade.trim() === "" ? null : Number(grade);
    if (isCompleted && parsedGrade == null) return setError("Informe a nota da avaliação realizada.");
    if (parsedGrade != null && (!Number.isFinite(parsedGrade) || parsedGrade < 0 || parsedGrade > 10)) {
      return setError("Nota deve estar entre 0 e 10.");
    }
    await onSubmit({
      name: isGradeOnly ? assessment?.name ?? "Avaliação" : name.trim(),
      date: date || null,
      weight: parsedWeight,
      grade: parsedGrade,
      topics: textToTopics(topics),
      notes: notes.trim() || null,
      source: assessment?.source ?? "manual",
      status: isCompleted ? "completed" : "planned",
    }, contentSelections);
  }

  return (
    <form className="panel form-grid" onSubmit={submit}>
      <div className="panel-heading">
        <h3>{action === "planned" ? "Adicionar avaliação futura" : action === "completed" ? "Registrar avaliação realizada" : action === "grade" ? "Adicionar nota" : "Editar avaliação"}</h3>
        <p>Peso em porcentagem. Avaliação planejada fica sem nota até a realização.</p>
      </div>
      {error && <p className="message error">{error}</p>}
      {!isGradeOnly && <label>Nome<input value={name} onChange={(event) => setName(event.target.value)} /></label>}
      <label>Data<input type="date" value={date ?? ""} onChange={(event) => setDate(event.target.value)} /></label>
      <label>Peso (%)<input type="number" min="0" max="100" step="0.01" value={weight} onChange={(event) => setWeight(event.target.value)} /></label>
      {isCompleted && <label>Nota<input type="number" min="0" max="10" step="0.1" value={grade} onChange={(event) => setGrade(event.target.value)} /></label>}
      <label>Conteúdo<input value={topics} onChange={(event) => setTopics(event.target.value)} placeholder="Unidade 1, exercícios" /></label>
      <label>Observação<input value={notes} onChange={(event) => setNotes(event.target.value)} /></label>
      <ContentSelectionEditor nodes={contentNodes} selections={contentSelections} onChange={setContentSelections} />
      <div className="form-actions">
        <button className="secondary-button" type="button" onClick={onCancel}>Cancelar</button>
        <button type="submit" disabled={loading}>{loading ? "Salvando..." : "Salvar"}</button>
      </div>
    </form>
  );
}

function AbsenceEditor({
  absence,
  loading,
  onCancel,
  onSubmit,
}: {
  absence?: Absence | null;
  loading: boolean;
  onCancel: () => void;
  onSubmit: (payload: AbsencePayload) => Promise<void>;
}) {
  const [date, setDate] = useState(absence?.date ?? "");
  const [classHours, setClassHours] = useState(absence ? String(absence.class_hours) : "");
  const [notes, setNotes] = useState(absence?.notes ?? "");
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    const parsed = Number(classHours);
    if (!date) return setError("Data é obrigatória.");
    if (!Number.isFinite(parsed) || parsed <= 0) return setError("Informe horas-aula positivas.");
    await onSubmit({ date, class_hours: parsed, notes: notes.trim() || null });
  }

  return (
    <form className="panel form-grid" onSubmit={submit}>
      <div className="panel-heading"><h3>{absence ? "Editar falta" : "Registrar falta"}</h3><p>Unidade: hora-aula. Não informe encontros.</p></div>
      {error && <p className="message error">{error}</p>}
      <label>Data<input type="date" value={date} onChange={(event) => setDate(event.target.value)} /></label>
      <label>Horas-aula perdidas<input type="number" min="0" step="0.5" value={classHours} onChange={(event) => setClassHours(event.target.value)} /></label>
      <label>Observação<input value={notes} onChange={(event) => setNotes(event.target.value)} /></label>
      <div className="form-actions">
        <button className="secondary-button" type="button" onClick={onCancel}>Cancelar</button>
        <button type="submit" disabled={loading}>{loading ? "Salvando..." : "Salvar falta"}</button>
      </div>
    </form>
  );
}

function CoursePlanEditor({ data, onChange }: { data: CoursePlanData; onChange: (data: CoursePlanData) => void }) {
  function listField(key: keyof Pick<CoursePlanData, "objectives" | "contents" | "schedule" | "bibliography">, value: string) {
    onChange({ ...data, [key]: value.split("\n").map((item) => item.trim()).filter(Boolean) });
  }
  function updateAssessment(index: number, patch: Partial<CoursePlanData["assessments"][number]>) {
    const assessments = [...data.assessments];
    const next = { ...assessments[index], ...patch };
    if (next.name.trim()) next.status = "recognized";
    assessments[index] = next;
    onChange({ ...data, assessments });
  }
  return (
    <div className="form-grid">
      <div className="manual-fields">
        <label>Código<input value={data.code ?? ""} onChange={(e) => onChange({ ...data, code: e.target.value || null })} /></label>
        <label>Nome<input value={data.name ?? ""} onChange={(e) => onChange({ ...data, name: e.target.value || null })} /></label>
        <label>Carga horária<input type="number" value={data.workload_hours ?? ""} onChange={(e) => onChange({ ...data, workload_hours: e.target.value ? Number(e.target.value) : null })} /></label>
        <label>Semestre<input value={data.semester ?? ""} onChange={(e) => onChange({ ...data, semester: e.target.value || null })} /></label>
      </div>
      <label>Objetivos<textarea value={data.objectives.join("\n")} onChange={(e) => listField("objectives", e.target.value)} /></label>
      <label>Conteúdos/unidades<textarea value={data.contents.join("\n")} onChange={(e) => listField("contents", e.target.value)} /></label>
      <label>Cronograma<textarea value={data.schedule.join("\n")} onChange={(e) => listField("schedule", e.target.value)} /></label>
      <div className="stack">
        <h3>Avaliações extraídas</h3>
        {data.assessments.length === 0 && <p className="message muted">Nenhuma avaliação explícita foi extraída.</p>}
        {data.assessments.map((assessment, index) => (
          <div className="panel" key={assessment.name + "-" + index}><p className="muted">Origem: plano de ensino · {assessment.date ? "Data confirmada" : "Data não informada; poderá ser adicionada depois"}</p>
            <div className="manual-fields">
              <label>Nome<input value={assessment.name} onChange={(e) => updateAssessment(index, { name: e.target.value })} /></label>
              <label>Data<input type="date" value={assessment.date ?? ""} onChange={(e) => updateAssessment(index, { date: e.target.value || null })} /></label>
              <label>Grupo<input value={assessment.group_code ?? ""} onChange={(e) => updateAssessment(index, { group_code: e.target.value || null })} /></label><label>Peso do grupo na nota final (%)<input type="number" min="0" max="100" step="0.01" value={assessment.group_final_weight ?? assessment.weight ?? ""} onChange={(e) => updateAssessment(index, { group_final_weight: e.target.value ? Number(e.target.value) : null })} /></label><label>Peso dentro do grupo (%)<input type="number" min="0" max="100" step="0.01" value={assessment.group_weight ?? ""} onChange={(e) => updateAssessment(index, { group_weight: e.target.value ? Number(e.target.value) : null })} /></label>
              <label>Status<select value={assessment.status} onChange={(e) => updateAssessment(index, { status: e.target.value as CoursePlanData["assessments"][number]["status"] })}><option value="recognized">revisada</option><option value="requires_review">requer revisão</option></select></label>
            </div>
            <label>Descrição<textarea value={assessment.description ?? ""} onChange={(e) => updateAssessment(index, { description: e.target.value || null })} /></label><label>Conteúdo<input value={topicsToText(assessment.topics)} onChange={(e) => updateAssessment(index, { topics: textToTopics(e.target.value) })} /></label><p className="muted">{assessment.source_page ? "Fonte: página " + assessment.source_page : "Página de origem não identificada"}</p>
          </div>
        ))}
      </div>
      <label>Bibliografia<textarea value={data.bibliography.join("\n")} onChange={(e) => listField("bibliography", e.target.value)} /></label>
    </div>
  );
}

export function DisciplineDetailPage({ disciplineId, onBack }: Props) {
  const [discipline, setDiscipline] = useState<Discipline | null>(null);
  const [assessments, setAssessments] = useState<Assessment[]>([]);
  const [contentNodes, setContentNodes] = useState<ContentNode[]>([]);
  const [contentAssociations, setContentAssociations] = useState<Record<string, AssessmentContentAssociation>>({});
  const [absences, setAbsences] = useState<Absence[]>([]);
  const [attendanceSummary, setAttendanceSummary] = useState<AttendanceSummary | null>(null);
  const [coursePlan, setCoursePlan] = useState<CoursePlanData | null>(null);
  const [preview, setPreview] = useState<CoursePlanPreviewResponse | null>(null);
  const [previewData, setPreviewData] = useState<CoursePlanData | null>(null);
  const [simulation, setSimulation] = useState<AcademicSimulation | null>(null);
  const [recommendation, setRecommendation] = useState<StudyRecommendationResponse | null>(null);
  const [sigaaResult, setSigaaResult] = useState<SigaaComponentSearchResponse | null>(null);
  const [pendingTopics, setPendingTopics] = useState<StudyTopicInput[]>([]);
  const [userGoal, setUserGoal] = useState("");
  const [targetAverage, setTargetAverage] = useState("5.0");
  const [activeTab, setActiveTab] = useState<Tab>("overview");
  const [assessmentAction, setAssessmentAction] = useState<AssessmentAction>(null);
  const [selectedAssessment, setSelectedAssessment] = useState<Assessment | null>(null);
  const [absenceAction, setAbsenceAction] = useState<AbsenceAction>(null);
  const [selectedAbsence, setSelectedAbsence] = useState<Absence | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [loadingRecommendation, setLoadingRecommendation] = useState(false);
  const [loadingSigaa, setLoadingSigaa] = useState(false);
  const [attachingSigaa, setAttachingSigaa] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [recommendationError, setRecommendationError] = useState<string | null>(null);
  const [sigaaError, setSigaaError] = useState<string | null>(null);

  const plannedAssessments = useMemo(() => assessments.filter((item) => item.status === "planned" && item.date).sort((a, b) => String(a.date).localeCompare(String(b.date))), [assessments]);
  const undatedAssessments = useMemo(() => assessments.filter((item) => item.status === "planned" && !item.date), [assessments]);
  const completedAssessments = useMemo(() => assessments.filter((item) => item.status === "completed"), [assessments]);
  const nextAssessment = plannedAssessments[0];

  async function loadContentData(assessmentData: Assessment[]) {
    const [nodes, associations] = await Promise.all([
      listContentNodes(disciplineId),
      Promise.all(assessmentData.map((item) => getAssessmentContentAssociation(disciplineId, item.id))),
    ]);
    setContentNodes(nodes);
    setContentAssociations(Object.fromEntries(associations.map((item) => [item.assessment_id, item])));
  }

  async function loadAll() {
    setLoading(true);
    setError(null);
    try {
      const [disciplineData, assessmentData, absenceData, attendanceData, coursePlanData] = await Promise.all([
        getDiscipline(disciplineId), listAssessments(disciplineId), listAbsences(disciplineId), getAttendanceSummary(disciplineId), getCoursePlan(disciplineId),
      ]);
      setDiscipline(disciplineData);
      setAssessments(assessmentData);
      await loadContentData(assessmentData);
      setAbsences(absenceData);
      setAttendanceSummary(attendanceData);
      setCoursePlan(coursePlanData);
      await loadSimulation(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível carregar a disciplina.");
    } finally {
      setLoading(false);
    }
  }

  async function loadSimulation(showErrors = true) {
    const parsedTarget = Number(targetAverage);
    if (!Number.isFinite(parsedTarget) || parsedTarget < 0 || parsedTarget > 10) {
      if (showErrors) setError("Média alvo deve estar entre 0 e 10.");
      return;
    }
    setSimulation(await getAcademicSimulation(disciplineId, parsedTarget));
  }

  useEffect(() => { void loadAll(); }, [disciplineId]);

  async function refreshRecords(message?: string) {
    const [assessmentData, absenceData, attendanceData, coursePlanData, simulationData] = await Promise.all([
      listAssessments(disciplineId), listAbsences(disciplineId), getAttendanceSummary(disciplineId), getCoursePlan(disciplineId), getAcademicSimulation(disciplineId, Number(targetAverage) || 5),
    ]);
    setAssessments(assessmentData);
    await loadContentData(assessmentData);
    setAbsences(absenceData);
    setAttendanceSummary(attendanceData);
    setCoursePlan(coursePlanData);
    setSimulation(simulationData);
    if (message) setNotice(message);
  }

  async function submitAssessment(payload: AssessmentPayload, selections: AssessmentContentSelection[]) {
    if (!assessmentAction) return;
    setSaving(true); setError(null); setNotice(null);
    try {
      let saved: Assessment;
      if (assessmentAction === "grade" && selectedAssessment) {
        if (payload.grade == null) throw new Error("Informe a nota.");
        saved = await completeAssessment(disciplineId, selectedAssessment.id, { grade: payload.grade, date: payload.date, topics: payload.topics, notes: payload.notes });
      } else if (assessmentAction === "edit" && selectedAssessment) {
        saved = await updateAssessment(disciplineId, selectedAssessment.id, payload);
      } else {
        saved = await createAssessment(disciplineId, payload);
      }
      await setAssessmentContentAssociation(disciplineId, saved.id, selections);
      setAssessmentAction(null); setSelectedAssessment(null);
      await refreshRecords("Avaliação salva.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível salvar avaliação.");
    } finally { setSaving(false); }
  }

  async function submitAbsence(payload: AbsencePayload) {
    setSaving(true); setError(null); setNotice(null);
    try {
      if (absenceAction === "edit" && selectedAbsence) await updateAbsence(disciplineId, selectedAbsence.id, payload);
      else await createAbsence(disciplineId, payload);
      setAbsenceAction(null); setSelectedAbsence(null);
      await refreshRecords("Falta registrada.");
    } catch (err) { setError(err instanceof Error ? err.message : "Não foi possível salvar falta."); }
    finally { setSaving(false); }
  }

  async function handleRecommendation() {
    setLoadingRecommendation(true); setRecommendationError(null);
    try {
      const parsedTarget = Number(targetAverage);
      const response = await createStudyRecommendation({ discipline_id: disciplineId, target_average: parsedTarget, pending_topics: pendingTopics, user_goal: userGoal.trim() || null });
      setRecommendation(response);
    } catch (err) { setRecommendationError(err instanceof Error ? err.message : "Não foi possível gerar recomendação."); }
    finally { setLoadingRecommendation(false); }
  }

  async function handlePlanPreview(file?: File) {
    if (!file) return;
    setSaving(true); setError(null); setNotice(null);
    try {
      const response = await previewCoursePlan(disciplineId, file);
      setPreview(response);
      setPreviewData(response.data);
      setNotice("Pré-visualização gerada. Revise antes de confirmar.");
    } catch (err) { setError(err instanceof Error ? err.message : "Não foi possível extrair o plano."); }
    finally { setSaving(false); }
  }

  async function handlePlanConfirm() {
    if (!preview || !previewData) return;
    setSaving(true); setError(null); setNotice(null);
    try {
      await confirmCoursePlan(disciplineId, preview.preview_id, previewData);
      setPreview(null); setPreviewData(null);
      await refreshRecords("Plano de ensino confirmado e dados estruturados salvos.");
    } catch (err) { setError(err instanceof Error ? err.message : "Revise os campos incertos antes de confirmar."); }
    finally { setSaving(false); }
  }

  async function handleSigaaSearch(query: string) { setLoadingSigaa(true); setSigaaError(null); try { setSigaaResult(await searchSigaaComponent(query)); } catch (err) { setSigaaError(err instanceof Error ? err.message : "A consulta ao SIGAA falhou."); } finally { setLoadingSigaa(false); } }
  async function handleSigaaAttach(component: SigaaComponent) { setAttachingSigaa(true); setSigaaError(null); try { setDiscipline(await attachSigaaComponent(disciplineId, component)); setNotice("Dados públicos do SIGAA associados."); } catch (err) { setSigaaError(err instanceof Error ? err.message : "Não foi possível associar SIGAA."); } finally { setAttachingSigaa(false); } }

  if (loading) return <div className="page"><p className="message muted">Carregando detalhe da disciplina...</p></div>;
  if (!discipline) return <div className="page narrow-page"><p className="message error">{error ?? "Disciplina não encontrada."}</p><button type="button" onClick={onBack}>Voltar</button></div>;

  return (
    <div className="page detail-page">
      <button className="back-button" type="button" onClick={onBack}>Voltar para disciplinas</button>
      <section className="panel discipline-summary">
        <div><p className="eyebrow">Detalhe da disciplina</p><h1>{discipline.code} · {discipline.name}</h1></div>
        <dl>
          <div><dt>Carga horária</dt><dd>{numberText(discipline.workload_hours ?? discipline.total_class_hours, " h/a")}</dd></div>
          <div><dt>Próxima avaliação</dt><dd>{nextAssessment ? `${nextAssessment.name} · ${nextAssessment.date ?? "sem data"}` : "Não informada"}</dd></div>
          <div><dt>Média parcial</dt><dd>{numberText(simulation?.partial_average)}</dd></div>
          <div><dt>Frequência</dt><dd>{percent(attendanceSummary?.frequency)}</dd></div>
        </dl>
      </section>
      {error && <p className="message error">{error}</p>}
      {notice && <p className="message success">{notice}</p>}

      <div className="segmented-control detail-tabs">
        {(Object.keys(tabLabels) as Tab[]).map((tab) => <button key={tab} className={activeTab === tab ? "active" : ""} type="button" onClick={() => setActiveTab(tab)}>{tabLabels[tab]}</button>)}
      </div>

      {activeTab === "overview" && (
        <div className="stack">
          <section className="panel overview-assistant">
            <div><p className="eyebrow">Próxima ação</p><h2>{nextAssessment ? `Prepare-se para ${nextAssessment.name}` : "Organize sua próxima etapa"}</h2><p>{nextAssessment?.date ? `Avaliação prevista para ${nextAssessment.date}.` : "Converse com o assistente usando os dados cadastrados."}</p></div>
            <button type="button" onClick={() => setActiveTab("recommendations")}>Conversar com o assistente</button>
          </section>
          <section className="overview-cards">
            <div><span>Próxima avaliação</span><strong>{nextAssessment ? `${nextAssessment.name} · ${nextAssessment.date ?? "Sem data"}` : "Não informada"}</strong></div>
            <div><span>Desempenho</span><strong>{simulation?.partial_average == null ? "Não calculado" : `Média ${numberText(simulation.partial_average)}`}</strong></div>
            <div><span>Frequência e saldo</span><strong>{percent(attendanceSummary?.frequency)} · {numberText(attendanceSummary?.remaining_class_hours, " h/a")}</strong></div>
            <div><span>Principal risco</span><strong>{({ low: "Baixo", medium: "Médio", high: "Alto", unknown: "Não calculado" } as Record<string, string>)[attendanceSummary?.risk_level === "high" ? "high" : simulation?.grade_risk_level ?? attendanceSummary?.risk_level ?? "unknown"]}</strong></div>
          </section>
          <div className="button-row overview-actions"><button className="secondary-button" type="button" onClick={() => { setActiveTab("assessments"); setAssessmentAction("planned"); }}>Adicionar avaliação</button><button className="secondary-button" type="button" onClick={() => { setActiveTab("attendance"); setAbsenceAction("create"); }}>Registrar falta</button></div>
        </div>
      )}

      {activeTab === "contents" && (
        <ContentTreePanel disciplineId={disciplineId} nodes={contentNodes} hasConfirmedPlan={coursePlan != null} loading={loading} onChanged={async () => { setContentNodes(await listContentNodes(disciplineId)); }} />
      )}

      {activeTab === "assessments" && (
        <div className="detail-grid">
          <div className="stack">
            <section className="panel stack">
              <div className="section-heading"><div><h2>Próximas avaliações</h2><p>Ordenadas cronologicamente. Nota vazia até a realização.</p></div><button type="button" onClick={() => { setSelectedAssessment(null); setAssessmentAction("planned"); }}>Adicionar avaliação</button></div>
              {plannedAssessments.length === 0 && <p className="message muted">Nenhuma avaliação futura cadastrada.</p>}
              {plannedAssessments.map((item) => <div className="status-box" key={item.id}><span>{item.source === "course_plan" ? "Plano de ensino" : "Cadastro manual"}</span><strong>{item.name} · {item.date ?? "sem data"} · {numberText(item.weight, "%")}</strong><p>{topicsToText(item.topics) || "Conteúdo não informado"}</p><div className="button-row"><button type="button" onClick={() => { setSelectedAssessment(item); setAssessmentAction("grade"); }}>Adicionar nota</button><button className="secondary-button" type="button" onClick={() => { setSelectedAssessment(item); setAssessmentAction("edit"); }}>Editar</button><button className="secondary-button" type="button" onClick={async () => { await updateAssessment(disciplineId, item.id, { status: "cancelled" }); await refreshRecords("Avaliação cancelada."); }}>Cancelar</button><button className="secondary-button" type="button" onClick={async () => { await deleteAssessment(disciplineId, item.id); await refreshRecords("Avaliação excluída."); }}>Excluir</button></div></div>)}
            <section className="panel stack">
              <div><h2>Avaliações sem data definida</h2><p>Continuam planejadas, mas não influenciam prioridade por proximidade.</p></div>
              {undatedAssessments.length === 0 && <p className="message muted">Nenhuma avaliação aguardando definição de data.</p>}
              {undatedAssessments.map((item) => <div className="status-box" key={item.id}><span>{item.source === "course_plan" ? "Plano de ensino · Data não informada" : "Cadastro manual · Data não informada"}</span><strong>{item.name} · {numberText(item.weight, "%")}</strong><p>{topicsToText(item.topics) || "Conteúdo não informado"}</p><div className="button-row"><button type="button" onClick={() => { setSelectedAssessment(item); setAssessmentAction("edit"); }}>Definir data</button><button className="secondary-button" type="button" onClick={() => { setSelectedAssessment(item); setAssessmentAction("edit"); }}>Editar</button><button className="secondary-button" type="button" onClick={async () => { await updateAssessment(disciplineId, item.id, { status: "cancelled" }); await refreshRecords("Avaliação cancelada."); }}>Cancelar</button><button className="secondary-button" type="button" onClick={async () => { await deleteAssessment(disciplineId, item.id); await refreshRecords("Avaliação excluída."); }}>Excluir</button></div></div>)}
            </section>
            </section>
            <section className="panel stack"><div className="section-heading"><div><h2>Avaliações realizadas</h2><p>Somente estas, com nota, entram na média atual.</p></div><button type="button" onClick={() => { setSelectedAssessment(null); setAssessmentAction("completed"); }}>Registrar realizada</button></div>{completedAssessments.length === 0 && <p className="message muted">Nenhuma avaliação realizada com nota.</p>}{completedAssessments.map((item) => <div className="status-box" key={item.id}><span>{item.date ?? "sem data"}</span><strong>{item.name} · Nota: {numberText(item.grade)} · Peso global: {numberText(effectiveWeight(item), "%")}</strong><p>{topicsToText(item.topics) || "Conteúdo não informado"}</p><div className="button-row"><button className="secondary-button" type="button" onClick={() => { setSelectedAssessment(item); setAssessmentAction("edit"); }}>Editar</button><button className="secondary-button" type="button" onClick={async () => { await deleteAssessment(disciplineId, item.id); await refreshRecords("Avaliação excluída."); }}>Excluir</button></div></div>)}</section>
          </div>
          <div className="stack">
            {assessmentAction && <AssessmentEditor key={`${assessmentAction}-${selectedAssessment?.id ?? "new"}`} action={assessmentAction} assessment={selectedAssessment} loading={saving} contentNodes={contentNodes} initialSelections={selectedAssessment ? contentAssociations[selectedAssessment.id]?.selections ?? [] : []} onCancel={() => { setAssessmentAction(null); setSelectedAssessment(null); }} onSubmit={submitAssessment} />}
            <section className="panel target-panel"><label>Média alvo<input type="number" min="0" max="10" step="0.1" value={targetAverage} onChange={(event) => setTargetAverage(event.target.value)} /></label><button type="button" onClick={() => void loadSimulation()}>Recalcular</button></section>
            <AcademicSimulationPanel simulation={simulation} loading={false} error={null} />
          </div>
        </div>
      )}

      {activeTab === "attendance" && (
        <div className="detail-grid">
          <section className="panel stack"><div className="section-heading"><div><h2>Frequência</h2><p>Unidade adotada: hora-aula.</p></div><button type="button" onClick={() => { setSelectedAbsence(null); setAbsenceAction("create"); }}>Registrar falta</button></div><div className="metrics-grid"><div><span>Carga horária</span><strong>{numberText(attendanceSummary?.workload_class_hours, " h/a")}</strong></div><div><span>Horas perdidas</span><strong>{numberText(attendanceSummary?.missed_class_hours, " h/a")}</strong></div><div><span>Limite 25%</span><strong>{numberText(attendanceSummary?.absence_limit_class_hours, " h/a")}</strong></div><div><span>Saldo restante</span><strong>{numberText(attendanceSummary?.remaining_class_hours, " h/a")}</strong></div><div><span>Frequência</span><strong>{percent(attendanceSummary?.frequency)}</strong></div><div><span>Risco</span><strong>{attendanceSummary?.risk_level}</strong></div></div>{attendanceSummary?.warnings.map((warning) => <p className="message warning" key={warning}>{warning}</p>)}<h3>Ocorrências</h3>{absences.length === 0 && <p className="message muted">Nenhuma falta registrada.</p>}{absences.map((item) => <div className="status-box" key={item.id}><span>{item.date}</span><strong>{item.class_hours} h/a</strong><p>{item.notes || "Sem observação"}</p><div className="button-row"><button className="secondary-button" type="button" onClick={() => { setSelectedAbsence(item); setAbsenceAction("edit"); }}>Editar</button><button className="secondary-button" type="button" onClick={async () => { await deleteAbsence(disciplineId, item.id); await refreshRecords("Falta removida."); }}>Remover</button></div></div>)}</section>
          <div>{absenceAction && <AbsenceEditor key={`${absenceAction}-${selectedAbsence?.id ?? "new"}`} absence={selectedAbsence} loading={saving} onCancel={() => { setAbsenceAction(null); setSelectedAbsence(null); }} onSubmit={submitAbsence} />}</div>
        </div>
      )}

      {activeTab === "coursePlan" && (
        <div className="detail-grid">
          <section className="panel stack"><h2>Plano de ensino</h2><p>O PDF é usado só para extração temporária. A persistência ocorre apenas após confirmação dos dados estruturados.</p><label>Enviar PDF<input type="file" accept="application/pdf" onChange={(event) => void handlePlanPreview(event.target.files?.[0])} /></label>{preview?.warnings.map((warning) => <p className="message warning" key={warning}>{warning}</p>)}{previewData ? <><div className="status-box"><span>Resumo da extração</span><strong>{previewData.evaluation_groups.length} grupo(s) de avaliação · {previewData.assessments.length} componente(s)</strong><p>{previewData.assessments.filter((item) => !item.date).length} componentes ainda sem data · Fonte: {preview?.source === "gemini" ? "Gemini" : "parser local"}</p></div><details className="simulation-details"><summary>Revisar itens extraídos</summary><CoursePlanEditor data={previewData} onChange={setPreviewData} /></details><div className="form-actions"><button className="secondary-button" type="button" onClick={() => { setPreview(null); setPreviewData(null); }}>Descartar prévia</button><button type="button" disabled={saving || previewData.assessments.some((item) => item.status === "requires_review")} onClick={handlePlanConfirm}>Confirmar dados estruturados</button></div></> : coursePlan ? <div className="stack"><div className="status-box"><span>Estado</span><strong>Plano confirmado</strong></div><h3>Conteúdos</h3><ul>{coursePlan.contents.map((item) => <li key={item}>{item}</li>)}</ul><h3>Cronograma</h3><ul>{coursePlan.schedule.map((item) => <li key={item}>{item}</li>)}</ul><h3>Avaliações extraídas</h3><div className="status-box"><span>Resumo</span><strong>{coursePlan.evaluation_groups.length} grupo(s) · {coursePlan.assessments.length} componente(s)</strong><p>{coursePlan.assessments.filter((item) => !item.date).length} componentes ainda sem data</p></div><details className="simulation-details"><summary>Revisar itens</summary><ul>{coursePlan.assessments.map((item) => <li key={item.name}>{item.name} · {item.date ?? "Data não informada"} · {numberText(item.weight, "%")}</li>)}</ul></details><button className="secondary-button" type="button" onClick={async () => { await deleteCoursePlan(disciplineId); await refreshRecords("Plano removido."); }}>Remover dados estruturados</button></div> : <p className="message muted">Nenhum plano confirmado. Envie um PDF para pré-visualizar.</p>}</section>
          <SigaaComponentPanel discipline={discipline} result={sigaaResult} loading={loadingSigaa} attaching={attachingSigaa} error={sigaaError} onSearch={handleSigaaSearch} onAttach={handleSigaaAttach} />
        </div>
      )}

      {activeTab === "recommendations" && (
        <div className="recommendations-layout">
          <section className="panel"><label>Objetivo do estudante<input value={userGoal} maxLength={500} onChange={(event) => setUserGoal(event.target.value)} placeholder="Ex.: preparar a prova sem comprometer as outras disciplinas" /></label></section>
          <DisciplineAssistantChat disciplineId={disciplineId} userGoal={userGoal} />
        </div>
      )}
    </div>
  );
}
