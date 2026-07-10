import type {
  AcademicSimulation,
  ApiHealth,
  Assessment,
  AssessmentPayload,
  AttendancePayload,
  Discipline,
  DisciplineCreatePayload,
  SigaaComponent,
  SigaaComponentSearchResponse,
  StudyRecommendationRequest,
  StudyRecommendationResponse,
} from "../types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export function getApiBaseUrl() {
  return API_BASE_URL;
}

function friendlyError(status: number, detail: unknown): string {
  if (status === 404) return "Disciplina não encontrada.";
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
