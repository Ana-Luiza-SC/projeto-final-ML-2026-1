import type {
  AcademicSimulation,
  AssistantMessage,
  DisciplineAssistantResponse,
  ApiHealth,
  Absence,
  AbsencePayload,
  Assessment,
  AssessmentPayload,
  AttendancePayload,
  AttendanceSummary,
  CoursePlanData,
  CoursePlanPreviewResponse,
  Discipline,
  DisciplineCreatePayload,
  SigaaComponent,
  SigaaComponentSearchResponse,
  StudyRecommendationRequest,
  StudyRecommendationResponse,
  StudyPlanRequest,
  StudyPlanResponse,
  MatriculaPdfPreviewResponse,
  MatriculaImportConfirmRequest,
  MatriculaImportConfirmResponse,
} from "../types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export function getApiBaseUrl() {
  return API_BASE_URL;
}

function friendlyError(status: number, detail: unknown): string {
  if (status === 404) return typeof detail === "string" ? detail : "Recurso não encontrado.";
  if (status === 409) return typeof detail === "string" ? detail : "A operação conflita com a hierarquia atual.";
  if (status === 400 || status === 422) {
    const detailText = typeof detail === "string" ? detail : "Verifique os dados informados.";
    if (detailText.toLowerCase().includes("nota")) return "Nota deve estar entre 0 e 10.";
    if (detailText.toLowerCase().includes("peso")) return "Peso inválido. Use decimal ou porcentagem válida.";
    if (detailText.toLowerCase().includes("faltas")) return "Faltas não podem ser maiores que o total informado.";
    return detailText;
  }
  return "Não foi possível completar a operação. Tente novamente.";
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      headers: { "Content-Type": "application/json", ...options.headers },
      ...options,
    });

    let body: unknown = null;
    const contentType = response.headers.get("content-type") ?? "";
    if (contentType.includes("application/json")) {
      body = await response.json();
    }

    if (!response.ok) {
      const detail = body && typeof body === "object" && "detail" in body ? (body as { detail: unknown }).detail : null;
      throw new Error(friendlyError(response.status, detail));
    }

    return body as T;
  } catch (error) {
    if (error instanceof TypeError) {
      throw new Error("Não foi possível conectar à API. Verifique se o backend está rodando.");
    }
    if (error instanceof Error) throw error;
    throw new Error("Erro inesperado ao comunicar com a API.");
  }
}


async function requestForm<T>(path: string, formData: FormData): Promise<T> {
  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      method: "POST",
      body: formData,
    });

    let body: unknown = null;
    const contentType = response.headers.get("content-type") ?? "";
    if (contentType.includes("application/json")) {
      body = await response.json();
    }

    if (!response.ok) {
      const detail = body && typeof body === "object" && "detail" in body ? (body as { detail: unknown }).detail : null;
      throw new Error(friendlyError(response.status, detail));
    }

    return body as T;
  } catch (error) {
    if (error instanceof TypeError) {
      throw new Error("Não foi possível conectar à API. Verifique se o backend está rodando.");
    }
    if (error instanceof Error) throw error;
    throw new Error("Erro inesperado ao comunicar com a API.");
  }
}

export function getHealth() {
  return request<ApiHealth>("/api/health");
}

export function listDisciplines() {
  return request<Discipline[]>("/api/disciplines");
}

export function getDiscipline(id: string) {
  return request<Discipline>(`/api/disciplines/${id}`);
}

export function createDiscipline(payload: DisciplineCreatePayload) {
  return request<Discipline>("/api/disciplines", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateAttendance(id: string, payload: AttendancePayload) {
  return request<Discipline>(`/api/disciplines/${id}/attendance`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function createAssessment(id: string, payload: AssessmentPayload) {
  return request<Assessment>(`/api/disciplines/${id}/assessments`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function listAssessments(id: string) {
  return request<Assessment[]>(`/api/disciplines/${id}/assessments`);
}

export function updateAssessment(id: string, assessmentId: string, payload: Partial<AssessmentPayload>) {
  return request<Assessment>(`/api/disciplines/${id}/assessments/${assessmentId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function completeAssessment(id: string, assessmentId: string, payload: { grade: number; date?: string | null; topics?: string[]; notes?: string | null }) {
  return request<Assessment>(`/api/disciplines/${id}/assessments/${assessmentId}/complete`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function deleteAssessment(id: string, assessmentId: string) {
  return request<unknown>(`/api/disciplines/${id}/assessments/${assessmentId}`, { method: "DELETE" });
}

export function listAbsences(id: string) {
  return request<Absence[]>(`/api/disciplines/${id}/absences`);
}

export function createAbsence(id: string, payload: AbsencePayload) {
  return request<Absence>(`/api/disciplines/${id}/absences`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateAbsence(id: string, absenceId: string, payload: AbsencePayload) {
  return request<Absence>(`/api/disciplines/${id}/absences/${absenceId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function deleteAbsence(id: string, absenceId: string) {
  return request<unknown>(`/api/disciplines/${id}/absences/${absenceId}`, { method: "DELETE" });
}

export function getAttendanceSummary(id: string) {
  return request<AttendanceSummary>(`/api/disciplines/${id}/attendance-summary`);
}

export function getCoursePlan(id: string) {
  return request<CoursePlanData | null>(`/api/disciplines/${id}/course-plan`);
}

export function previewCoursePlan(id: string, file: File) {
  const formData = new FormData();
  formData.append("file", file);
  return requestForm<CoursePlanPreviewResponse>(`/api/disciplines/${id}/course-plan/preview`, formData);
}

export function confirmCoursePlan(id: string, previewId: string, data: CoursePlanData) {
  return request<CoursePlanData>(`/api/disciplines/${id}/course-plan/confirm`, {
    method: "POST",
    body: JSON.stringify({ preview_id: previewId, data }),
  });
}

export function deleteCoursePlan(id: string) {
  return request<unknown>(`/api/disciplines/${id}/course-plan`, { method: "DELETE" });
}

export function getAcademicSimulation(id: string, targetAverage: number) {
  const params = new URLSearchParams({ target_average: String(targetAverage) });
  return request<AcademicSimulation>(`/api/disciplines/${id}/academic-simulation?${params.toString()}`);
}


export function createStudyRecommendation(payload: StudyRecommendationRequest) {
  return request<StudyRecommendationResponse>("/api/agent/study-recommendation", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}


export function createStudyPlan(payload: StudyPlanRequest) {
  return request<StudyPlanResponse>("/api/study-plans/generate", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}


export function searchSigaaComponent(query: string) {
  const params = new URLSearchParams({ query });
  return request<SigaaComponentSearchResponse>(`/api/sigaa/components/search?${params.toString()}`);
}

export function attachSigaaComponent(id: string, component: SigaaComponent) {
  return request<Discipline>(`/api/disciplines/${id}/sigaa-component`, {
    method: "PATCH",
    body: JSON.stringify({ component }),
  });
}


export function previewMatriculaPdf(file: File) {
  const formData = new FormData();
  formData.append("file", file);
  return requestForm<MatriculaPdfPreviewResponse>("/api/import/matricula-pdf/preview", formData);
}

export function confirmMatriculaImport(payload: MatriculaImportConfirmRequest) {
  return request<MatriculaImportConfirmResponse>("/api/import/matricula-pdf/confirm", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function sendDisciplineAssistantMessage(id: string, message: string, recentMessages: AssistantMessage[], userGoal?: string | null) {
  return request<DisciplineAssistantResponse>(`/api/disciplines/${id}/assistant/messages`, {
    method: "POST",
    body: JSON.stringify({ message, recent_messages: recentMessages.slice(-8).map(({ role, content }) => ({ role, content })), user_goal: userGoal || null }),
  });
}

export function listContentNodes(disciplineId: string) { return request<import("../types").ContentNode[]>(`/api/disciplines/${disciplineId}/contents`); }
export function createContentNode(disciplineId: string, payload: import("../types").ContentNodePayload, parentId?: string | null) { const path = parentId ? `/api/disciplines/${disciplineId}/contents/${parentId}/children` : `/api/disciplines/${disciplineId}/contents`; return request<import("../types").ContentNode>(path, { method: "POST", body: JSON.stringify(payload) }); }
export function updateContentNode(disciplineId: string, nodeId: string, payload: Partial<import("../types").ContentNodePayload>) { return request<import("../types").ContentNode>(`/api/disciplines/${disciplineId}/contents/${nodeId}`, { method: "PATCH", body: JSON.stringify(payload) }); }
export function moveContentNode(disciplineId: string, nodeId: string, parentId?: string | null) { return request<import("../types").ContentNode>(`/api/disciplines/${disciplineId}/contents/${nodeId}/move`, { method: "POST", body: JSON.stringify({ parent_id: parentId ?? null }) }); }
export function deleteContentNode(disciplineId: string, nodeId: string) { return request<unknown>(`/api/disciplines/${disciplineId}/contents/${nodeId}`, { method: "DELETE" }); }
export function getAssessmentContentAssociation(disciplineId: string, assessmentId: string) { return request<import("../types").AssessmentContentAssociation>(`/api/disciplines/${disciplineId}/assessments/${assessmentId}/content-associations`); }
export function setAssessmentContentAssociation(disciplineId: string, assessmentId: string, selections: import("../types").AssessmentContentSelection[]) { return request<import("../types").AssessmentContentAssociation>(`/api/disciplines/${disciplineId}/assessments/${assessmentId}/content-associations`, { method: "PUT", body: JSON.stringify({ selections }) }); }
export function previewContentExtraction(disciplineId: string) { return request<import("../types").ContentExtractionPreview>(`/api/disciplines/${disciplineId}/contents/extract-preview`, { method: "POST" }); }
export function confirmContentExtraction(disciplineId: string, previewId: string, draftNodes: import("../types").ContentDraftNode[]) { return request<import("../types").ContentExtractionConfirmation>(`/api/disciplines/${disciplineId}/contents/confirm-preview`, { method: "POST", body: JSON.stringify({ preview_id: previewId, draft_nodes: draftNodes }) }); }
