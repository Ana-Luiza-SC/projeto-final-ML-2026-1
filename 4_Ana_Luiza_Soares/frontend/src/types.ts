export type ApiHealth = {
  status: string;
};

export type Discipline = {
  id: string;
  code: string;
  name: string;
  professor?: string | null;
  class_code?: string | null;
  schedule_code?: string | null;
  schedule_slots?: { day: string; start_time: string; end_time: string; source: string }[];
  schedule_display?: string | null;
  schedule_source?: "receipt_table" | "sigaa_tooltip" | "decoded_code" | "unresolved";
  local?: string | null;
  total_classes?: number | null;
  missed_classes?: number | null;
  total_class_hours?: number | null;
  missed_class_hours?: number | null;
  created_at?: string;
  updated_at?: string;
  sigaa_code?: string | null;
  sigaa_source_url?: string | null;
  syllabus?: string | null;
  current_program?: string | null;
  workload_hours?: number | null;
  sigaa_cached_at?: string | null;
};

export type DisciplineCreatePayload = {
  code: string;
  name: string;
  professor?: string | null;
  class_code?: string | null;
  schedule_code?: string | null;
  schedule_slots?: { day: string; start_time: string; end_time: string; source: string }[];
  schedule_display?: string | null;
  schedule_source?: "receipt_table" | "sigaa_tooltip" | "decoded_code" | "unresolved";
  local?: string | null;
  sigaa_code?: string | null;
  sigaa_source_url?: string | null;
  syllabus?: string | null;
  current_program?: string | null;
  workload_hours?: number | null;
  sigaa_cached_at?: string | null;
};

export type AttendancePayload = {
  total_classes?: number | null;
  missed_classes?: number | null;
  total_class_hours?: number | null;
  missed_class_hours?: number | null;
};

export type AssessmentStatus = "planned" | "completed" | "cancelled";
export type AssessmentSource = "manual" | "course_plan";

export type AssessmentPayload = {
  name: string;
  weight?: number | null;
  grade?: number | null;
  date?: string | null;
  topics?: string[];
  notes?: string | null;
  source?: AssessmentSource;
  status?: AssessmentStatus;
  code?: string | null;
  evaluation_group_code?: string | null;
  evaluation_group_name?: string | null;
  group_final_weight?: number | null;
  group_weight?: number | null;
  requires_date?: boolean;
  description?: string | null;
  source_page?: number | null;
};

export type Assessment = AssessmentPayload & {
  id: string;
  discipline_id: string;
  source: AssessmentSource;
  status: AssessmentStatus;
};

export type AbsencePayload = {
  date: string;
  class_hours: number;
  notes?: string | null;
};

export type Absence = AbsencePayload & {
  id: string;
  discipline_id: string;
};

export type AttendanceSummary = {
  workload_class_hours?: number | null;
  missed_class_hours: number;
  absence_limit_class_hours?: number | null;
  remaining_class_hours?: number | null;
  frequency?: number | null;
  absence_percentage?: number | null;
  risk_level: "low" | "medium" | "high" | "unknown";
  warnings: string[];
};

export type AttendanceResult = {
  status?: string;
  source?: string | null;
  frequency?: number | null;
  absence_percentage?: number | null;
  risk_level?: string;
  warnings?: string[];
};

export type AcademicStatus = {
  status?: string;
  message?: string;
  warnings?: string[];
};

export type AcademicSimulation = {
  current_contribution?: number | null;
  partial_average?: number | null;
  completed_weight?: number | null;
  remaining_weight?: number | null;
  target_average?: number | null;
  required_average_on_remaining?: number | null;
  current_mention?: string | null;
  projected_mention?: string | null;
  grade_risk_level?: string | null;
  attendance?: AttendanceResult | null;
  academic_status?: AcademicStatus | null;
  reasons?: string[];
  warnings?: string[];
  group_results?: { code: string; name: string; average?: number | null; status: "calculated" | "insufficient_data"; meets_minimum_5?: boolean | null }[];
};


export type TopicDifficulty = "low" | "medium" | "high";
export type TopicStatus = "not_started" | "in_progress" | "reviewed";
export type DedicationLevel = "low" | "medium" | "high";

export type StudyTopicInput = {
  title: string;
  difficulty: TopicDifficulty;
  status: TopicStatus;
};

export type StudyRecommendationRequest = {
  discipline_id: string;
  target_average: number;
  pending_topics: StudyTopicInput[];
  user_goal?: string | null;
};

export type AgentExecutionMode = "llm" | "deterministic_fallback";
export type AssistantMessage = { role: "user" | "assistant"; content: string; evidence?: string[]; suggested_actions?: string[]; warnings?: string[]; source?: "gemini" | "fallback"; execution_mode?: AgentExecutionMode; fallback_reason?: string | null; model?: string | null };
export type DisciplineAssistantResponse = { status: "success"; source: "gemini" | "fallback"; execution_mode: AgentExecutionMode; fallback_reason?: string | null; model?: string | null; answer: string; evidence: string[]; suggested_actions: string[]; warnings: string[] };

export type StudyAction = { strategy_id: "retrieval_practice" | "spaced_practice" | "interleaving" | "concrete_examples" | "self_explanation"; action: string; topic?: string | null; estimated_minutes?: number | null; reason: string; evidence: string; reference_ids: string[] };
export type StudyStrategyReference = { id: string; short_citation: string; title: string; url: string };

export type StudyRecommendationResponse = {
  dedication_level: DedicationLevel;
  confidence: number;
  academic_situation_summary: string;
  grade_status: string;
  attendance_status: string;
  recommended_actions: string[];
  reasons: string[];
  missing_information: string[];
  used_fallback: boolean;
  provider: "google" | "rules";
  execution_mode: AgentExecutionMode;
  fallback_reason?: string | null;
  model?: string | null;
  latency_ms: number;
  warnings?: string[];
  used_evidence?: string[];
  influencing_assessments?: string[];
  study_actions?: StudyAction[];
  strategy_references?: StudyStrategyReference[];
};


export type SigaaComponent = {
  code: string;
  name: string;
  type?: string | null;
  unit?: string | null;
  workload_hours?: number | null;
  syllabus?: string | null;
  current_program?: string | null;
  prerequisites?: string | null;
  theoretical_workload_hours?: number | null;
  practical_workload_hours?: number | null;
  details_processed?: boolean;
  source_url: string;
};

export type SigaaComponentSearchResponse = {
  status: "found" | "not_found" | "error";
  source: "sigaa_public_components";
  query: string;
  component: SigaaComponent | null;
  cached: boolean;
  warnings: string[];
};


export type StudyPlanDay = "monday" | "tuesday" | "wednesday" | "thursday" | "friday" | "saturday" | "sunday";

export type StudyPlanTimeWindow = {
  day: StudyPlanDay;
  start_time: string;
  end_time: string;
};

export type StudyPlanRequest = {
  discipline_ids: string[];
  availability: {
    available_hours_per_week: number;
    days_available: StudyPlanDay[];
    time_windows?: StudyPlanTimeWindow[];
  };
  max_session_minutes: number;
  priorities: { discipline_id: string; priority: number }[];
  objective_text?: string | null;
};

export type StudyPlanSession = {
  day: StudyPlanDay;
  sequence: number;
  discipline_id: string;
  discipline_code: string;
  discipline_name: string;
  duration_minutes: number;
  activity: string;
  start_time?: string | null;
  end_time?: string | null;
  scheduled_date?: string | null;
  content_node_id?: string | null;
  assessment_id?: string | null;
  assessment_name?: string | null;
  assessment_date?: string | null;
  association_origin?: "direct" | "inherited" | null;
  evidence?: string | null;
};

export type StudyPlanResponse = {
  status: "success";
  source: "llm_assisted" | "deterministic_fallback";
  plan: StudyPlanSession[];
  summary: string;
  warnings: string[];
  metrics: {
    requested_minutes: number;
    allocated_minutes: number;
    unallocated_minutes: number;
    session_count: number;
    discipline_count: number;
  };
  priority_influences?: {
    discipline_id: string;
    assessment_id?: string | null;
    assessment_name: string;
    assessment_date: string;
    weight?: number | null;
    bonus: number;
    reason: string;
  }[];
  fallback_reason?: string | null;
  request_id: string;
};

export type CoursePlanAssessment = {
  name: string;
  date?: string | null;
  weight?: number | null;
  topics: string[];
  status: "recognized" | "requires_review";
  code?: string | null;
  group_code?: string | null;
  group_name?: string | null;
  group_final_weight?: number | null;
  group_weight?: number | null;
  requires_date?: boolean;
  description?: string | null;
  source_page?: number | null;
};

export type CoursePlanData = {
  code?: string | null;
  name?: string | null;
  semester?: string | null;
  workload_hours?: number | null;
  term_weeks?: number | null;
  objectives: string[];
  contents: string[];
  schedule: string[];
  assessments: CoursePlanAssessment[];
  evaluation_groups: { code: string; name: string; final_weight: number; items: { code?: string | null; name: string; group_weight?: number | null; date?: string | null; requires_date: boolean; description?: string | null; topics: string[]; source_page?: number | null; status: "recognized" | "requires_review" }[] }[];
  bibliography: string[];
};

export type CoursePlanPreviewResponse = {
  preview_id: string;
  expires_at: string;
  data: CoursePlanData;
  warnings: string[];
  source: "gemini" | "local_parser";
  model?: string | null;
  evaluation_group_count: number;
  evaluation_component_count: number;
};


export type ImportPreviewStatus = "recognized" | "ambiguous" | "not_found" | "duplicate" | "activity" | "rejected";
export type ImportItemType = "discipline" | "activity";
export type SigaaLookupStatus = "not_queried" | "found" | "not_found" | "error";

export type ImportPreviewItem = {
  preview_item_id: string;
  item_type: ImportItemType;
  status: ImportPreviewStatus;
  selected: boolean;
  code?: string | null;
  name?: string | null;
  class_code?: string | null;
  schedule_code?: string | null;
  schedule_slots?: { day: string; start_time: string; end_time: string; source: string }[];
  schedule_display?: string | null;
  schedule_source?: "receipt_table" | "sigaa_tooltip" | "decoded_code" | "unresolved";
  local?: string | null;
  source: "pdf_local" | "pdf_local_sigaa_enriched";
  sigaa_lookup: SigaaLookupStatus;
  confidence: "low" | "medium" | "high";
  warnings: string[];
};

export type MatriculaPdfPreviewResponse = {
  status: "success" | "no_items" | "extraction_failed";
  preview_id: string;
  expires_at: string;
  items: ImportPreviewItem[];
  summary: {
    recognized_count: number;
    ambiguous_count: number;
    not_found_count: number;
    duplicate_count: number;
    activity_count: number;
    rejected_count: number;
  };
  warnings: string[];
  request_id: string;
};

export type ImportConfirmationItem = {
  preview_item_id: string;
  selected: boolean;
  code?: string | null;
  name?: string | null;
  class_code?: string | null;
  schedule_code?: string | null;
  schedule_slots?: { day: string; start_time: string; end_time: string; source: string }[];
  schedule_display?: string | null;
  schedule_source?: "receipt_table" | "sigaa_tooltip" | "decoded_code" | "unresolved";
  local?: string | null;
};

export type MatriculaImportConfirmRequest = {
  preview_id: string;
  items: ImportConfirmationItem[];
};

export type MatriculaImportConfirmResponse = {
  status: "success" | "partial_success" | "no_items" | "error";
  preview_id: string;
  created: { preview_item_id: string; discipline_id: string; code: string; name: string }[];
  duplicates: { preview_item_id: string; code?: string | null; name?: string | null; reason: string }[];
  rejected: { preview_item_id: string; code?: string | null; name?: string | null; reason: string }[];
  skipped: { preview_item_id: string; code?: string | null; name?: string | null; reason: string }[];
  warnings: string[];
  summary: {
    created_count: number;
    duplicate_count: number;
    rejected_count: number;
    skipped_count: number;
  };
  request_id: string;
};

export type ContentStatus = "not_started" | "in_progress" | "studied" | "reviewed";
export type ContentNode = { id: string; discipline_id: string; parent_id?: string | null; title: string; description?: string | null; difficulty?: "low" | "medium" | "high" | null; status: ContentStatus; created_at: string; children: ContentNode[] };
export type ContentNodePayload = { parent_id?: string | null; title: string; description?: string | null; difficulty?: "low" | "medium" | "high" | null; status: ContentStatus };
export type AssessmentContentSelection = { content_node_id: string; include_descendants: boolean };
export type ResolvedContentNode = Omit<ContentNode, "children"> & { association_origin: "direct" | "inherited"; selected_ancestor_id?: string | null };
export type AssessmentContentAssociation = { assessment_id: string; selections: AssessmentContentSelection[]; resolved_nodes: ResolvedContentNode[] };
export type ContentDraftNode = { temporary_id: string; parent_temporary_id?: string | null; title: string; description?: string | null; source_evidence: string; confidence: number; warnings: string[] };
export type ContentExtractionPreview = { preview_id: string; expires_at: string; draft_nodes: ContentDraftNode[]; warnings: string[]; source: "gemini" | "local_fallback"; model?: string | null; used_fallback: boolean; fallback_reason?: "missing_api_key" | "timeout" | "unavailable" | "invalid_response" | "no_explicit_content" | null; latency_ms: number };
export type ContentExtractionConfirmation = { created_nodes: ContentNode[]; created_count: number };

export type CalendarEventType = "exam" | "assignment" | "presentation" | "activity" | "deadline" | "other";
export type CalendarEventStatus = "draft" | "confirmed" | "cancelled" | "completed";
export type CalendarEventSource = "manual" | "assessment" | "course_plan" | "system";

export type AcademicEvent = {
  id: string;
  discipline_id?: string | null;
  assessment_id?: string | null;
  title: string;
  description?: string | null;
  event_type: CalendarEventType;
  start_at: string;
  end_at?: string | null;
  all_day: boolean;
  timezone: "America/Sao_Paulo";
  weight?: number | null;
  status: CalendarEventStatus;
  source: CalendarEventSource;
  source_evidence?: string | null;
  extraction_confidence?: number | null;
  source_fingerprint?: string | null;
  created_at: string;
  updated_at: string;
  discipline_code?: string | null;
  discipline_name?: string | null;
};

export type AcademicEventPayload = {
  discipline_id?: string | null;
  title: string;
  description?: string | null;
  event_type: CalendarEventType;
  start_at: string;
  end_at?: string | null;
  all_day: boolean;
  timezone?: "America/Sao_Paulo";
  weight?: number | null;
  status?: CalendarEventStatus;
  source?: "manual";
};

export type CalendarDraftEvent = {
  temporary_id: string;
  title: string;
  event_type: CalendarEventType;
  start_at?: string | null;
  end_at?: string | null;
  all_day: boolean;
  timezone: "America/Sao_Paulo";
  weight?: number | null;
  description?: string | null;
  source_evidence: string;
  confidence: number;
  warnings: string[];
  ambiguous: boolean;
  source_fingerprint?: string | null;
};

export type CalendarExtractionPreview = {
  preview_id: string;
  expires_at: string;
  draft_events: CalendarDraftEvent[];
  warnings: string[];
  source: "course_plan" | "fallback";
  used_fallback: boolean;
  fallback_reason?: "missing_course_plan" | "missing_llm" | "invalid_response" | "timeout" | "provider_unavailable" | "no_explicit_events" | null;
  latency_ms: number;
};

export type CalendarPreviewConfirmation = {
  created_events: AcademicEvent[];
  skipped_events: { temporary_id: string; reason: string }[];
  created_count: number;
};
