from fastapi import APIRouter, HTTPException
from app import storage
from app.routers.agent import _attendance_from_absences
from app.schemas import DisciplineAssistantRequest, DisciplineAssistantResponse
from app.services.academic_calculator import calculate_grade_simulation, classify_academic_status
from app.services.study_recommendation_agent import generate_discipline_assistant_message
from app.services.content_map import agent_content_context

router = APIRouter(prefix="/api/disciplines/{discipline_id}/assistant", tags=["agent"])

@router.post("/messages", response_model=DisciplineAssistantResponse)
def create_message(discipline_id: str, payload: DisciplineAssistantRequest):
    discipline = storage.get_discipline(discipline_id)
    if discipline is None:
        raise HTTPException(status_code=404, detail="Disciplina não encontrada.")
    assessments = storage.list_assessments(discipline_id)
    grade = calculate_grade_simulation(assessments, 5.0)
    attendance = _attendance_from_absences(discipline_id, discipline)
    status = classify_academic_status(grade, attendance)
    simulation = {**grade, "attendance": attendance, "academic_status": status, "warnings": grade["warnings"] + attendance["warnings"]}
    content_context = agent_content_context(discipline_id, assessments)
    enriched = {**discipline, "assessments": assessments, "course_plan": storage.COURSE_PLANS.get(discipline_id), "absence_occurrences": storage.list_absences(discipline_id), "content_hierarchy": content_context["tree"], "assessment_content_context": content_context["assessment_contents"], "content_evidence_by_title": content_context["evidence_by_title"]}
    return generate_discipline_assistant_message(enriched, simulation, payload.message, [item.model_dump() for item in payload.recent_messages], payload.user_goal)
