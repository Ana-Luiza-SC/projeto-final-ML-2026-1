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
  local?: string | null;
  total_classes?: number | null;
  missed_classes?: number | null;
  total_class_hours?: number | null;
  missed_class_hours?: number | null;
  created_at?: string;
  updated_at?: string;
};

export type DisciplineCreatePayload = {
  code: string;
  name: string;
  professor?: string | null;
  class_code?: string | null;
  schedule_code?: string | null;
  local?: string | null;
};

export type AttendancePayload = {
  total_classes?: number | null;
  missed_classes?: number | null;
  total_class_hours?: number | null;
  missed_class_hours?: number | null;
};

export type AssessmentPayload = {
  name: string;
  weight: number;
  grade?: number | null;
  date?: string | null;
  topics?: string[];
};

export type Assessment = AssessmentPayload & {
  id: string;
  discipline_id: string;
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
};
