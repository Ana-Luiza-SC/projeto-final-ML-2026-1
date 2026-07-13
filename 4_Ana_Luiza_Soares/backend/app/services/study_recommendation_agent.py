from __future__ import annotations

import json
import logging
import os
import re
import time
import urllib.error
import urllib.request
from typing import Any

from pydantic import ValidationError

from app.schemas import DisciplineAssistantResponse, StudyAction, StudyRecommendationResponse, StudyStrategyReference, StudyTopicInput
from app.services.study_strategy_catalog import build_study_actions, strategy_references, validate_study_actions

logger = logging.getLogger("estudaunb.agent")

APPROVAL_MENTIONS = {"SS", "MS", "MM"}
FAILURE_MENTIONS = {"MI", "II", "SR"}


def _now_ms() -> float:
    return time.perf_counter() * 1000


def _duration_ms(start_ms: float) -> float:
    return round(_now_ms() - start_ms, 2)


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_timeout() -> float:
    try:
        return max(1.0, float(os.getenv("LLM_TIMEOUT_SECONDS", "8")))
    except ValueError:
        return 8.0


def _safe_text(value: Any, limit: int = 240) -> str:
    if value is None:
        return ""
    text = str(value).replace("\n", " ").strip()
    return text[:limit]


def _log_event(event: str, **fields: Any) -> None:
    safe_fields = {
        key: value
        for key, value in fields.items()
        if key not in {"prompt", "api_key", "GOOGLE_API_KEY"}
    }
    logger.info(json.dumps({"event": event, **safe_fields}, ensure_ascii=False))


def _assessment_weight_context(item: dict[str, Any]) -> dict[str, float | None]:
    group_final = item.get("group_final_weight")
    group_internal = item.get("group_weight")
    simple = item.get("weight")
    def normalized(value):
        if value is None:
            return None
        value = float(value)
        return value / 100 if value > 1 else value
    final_value = normalized(group_final)
    internal_value = normalized(group_internal)
    effective = final_value * internal_value if final_value is not None and internal_value is not None else normalized(simple)
    return {"weight": simple, "group_final_weight": group_final, "group_weight": group_internal, "effective_weight": effective}

def build_safe_prompt_context(
    discipline: dict[str, Any],
    simulation: dict[str, Any],
    pending_topics: list[StudyTopicInput],
    user_goal: str | None,
) -> dict[str, Any]:
    return {
        "discipline": {
            "id": _safe_text(discipline.get("id"), 80),
            "code": _safe_text(discipline.get("code"), 40),
            "name": _safe_text(discipline.get("name"), 120),
            "workload_class_hours": discipline.get("workload_hours") or discipline.get("total_class_hours"),
            "class_code": _safe_text(discipline.get("class_code"), 40),
            "schedule_code": _safe_text(discipline.get("schedule_code"), 80),
            "local": _safe_text(discipline.get("local"), 80),
        },
        "course_plan": {
            "source": "dado oficial do plano de ensino confirmado pelo usuário" if discipline.get("course_plan") else "não informado",
            "contents": [_safe_text(item, 160) for item in (discipline.get("course_plan") or {}).get("contents", [])[:20]],
            "schedule": [_safe_text(item, 160) for item in (discipline.get("course_plan") or {}).get("schedule", [])[:20]],
        },
        "assessments": {
            "planned_confirmed": [
                {
                    "name": _safe_text(item.get("name"), 120),
                    "date": _safe_text(item.get("date"), 20),
                    **_assessment_weight_context(item),
                    "topics": [_safe_text(topic, 120) for topic in (item.get("topics") or [])[:10]],
                    "source": item.get("source"),
                }
                for item in discipline.get("assessments", [])
                if item.get("status") == "planned" and item.get("date")
            ][:20],
            "planned_without_date": [
                {
                    "name": _safe_text(item.get("name"), 120),
                    "date": None,
                    **_assessment_weight_context(item),
                    "topics": [_safe_text(topic, 120) for topic in (item.get("topics") or [])[:10]],
                    "source": item.get("source"),
                    "warning": "Data não informada; não usar para prioridade por proximidade.",
                }
                for item in discipline.get("assessments", [])
                if item.get("status") == "planned" and not item.get("date")
            ][:20],
            "completed_with_grades": [
                {
                    "name": _safe_text(item.get("name"), 120),
                    "date": _safe_text(item.get("date"), 20),
                    **_assessment_weight_context(item),
                    "grade": item.get("grade"),
                    "topics": [_safe_text(topic, 120) for topic in (item.get("topics") or [])[:10]],
                    "source": item.get("source"),
                }
                for item in discipline.get("assessments", [])
                if item.get("status") == "completed" and item.get("grade") is not None
            ][:20],
        },
        "simulation": {
            "current_contribution": simulation.get("current_contribution"),
            "partial_average": simulation.get("partial_average"),
            "completed_weight": simulation.get("completed_weight"),
            "remaining_weight": simulation.get("remaining_weight"),
            "target_average": simulation.get("target_average"),
            "required_average_on_remaining": simulation.get("required_average_on_remaining"),
            "current_mention": simulation.get("current_mention"),
            "projected_mention": simulation.get("projected_mention"),
            "grade_risk_level": simulation.get("grade_risk_level"),
            "attendance": simulation.get("attendance", {}),
            "academic_status": simulation.get("academic_status", {}),
            "warnings": simulation.get("warnings", []),
        },
        "content_hierarchy": discipline.get("content_hierarchy", []),
        "assessment_content_context": discipline.get("assessment_content_context", []),
        "pending_topics": [
            {
                "title": _safe_text(topic.title, 120),
                "difficulty": topic.difficulty,
                "status": topic.status,
            }
            for topic in pending_topics[:30]
        ],
        "user_goal": _safe_text(user_goal, 500),
        "rules": {
            "approval_mentions": ["SS", "MS", "MM"],
            "failure_mentions": ["MI", "II", "SR"],
            "minimum_frequency": 0.75,
            "instruction": "Use nota, menção e frequência apenas como dados já calculados; responda somente JSON válido.",
        },
    }


def _build_prompt(context: dict[str, Any]) -> str:
    schema = {
        "dedication_level": "low | medium | high",
        "confidence": 0.0,
        "academic_situation_summary": "",
        "grade_status": "",
        "attendance_status": "",
        "recommended_actions": [],
        "reasons": [],
        "missing_information": [],
        "study_actions": [],
    }
    return (
        "Você é o agente de recomendação de estudos do EstudaUnB. "
        "Não recalcule nota, menção ou frequência; use apenas a simulação fornecida. "
        "Não avalie professor, não invente dados do SIGAA, e não afirme aprovação final se houver dados pendentes. "
        "Não prometa nota, aprovação ou domínio e use somente estratégias e referências fornecidas pelo backend. "
        "Responda apenas JSON válido seguindo este schema: "
        + json.dumps(schema, ensure_ascii=False)
        + "\nContexto seguro: "
        + json.dumps(context, ensure_ascii=False)
    )


def validate_llm_response(data: Any, latency_ms: float) -> StudyRecommendationResponse:
    if not isinstance(data, dict):
        raise ValueError("Resposta do LLM não é um objeto JSON.")
    validate_study_actions(data.get("study_actions"))
    payload = {
        **data,
        "used_fallback": False,
        "provider": "google",
        "execution_mode": "llm",
        "fallback_reason": None,
        "model": os.getenv("LLM_MODEL", "gemini-2.5-flash"),
        "latency_ms": latency_ms,
    }
    try:
        response = StudyRecommendationResponse.model_validate(payload)
    except ValidationError as exc:
        raise ValueError("Resposta do LLM não segue o schema esperado.") from exc

    forbidden = "aprovado final"
    joined = " ".join(
        [
            response.academic_situation_summary,
            response.grade_status,
            response.attendance_status,
            *response.recommended_actions,
            *response.reasons,
        ]
    ).lower()
    if "garant" in joined and any(term in joined for term in ("aprova", "nota", "domínio", "dominio")):
        raise ValueError("Resposta do LLM promete resultado acadêmico.")
    if forbidden in joined:
        raise ValueError("Resposta do LLM afirma aprovação final indevidamente.")
    return response




def _extract_json_text(value: str) -> str:
    text = value.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        return fenced.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return text[start:end + 1]
    return text

def generate_google_recommendation(
    context: dict[str, Any],
    timeout_seconds: float,
) -> dict[str, Any]:
    return generate_google_json(_build_prompt(context), timeout_seconds)


def generate_google_json(prompt: str, timeout_seconds: float) -> dict[str, Any]:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("missing_api_key")

    model = os.getenv("LLM_MODEL", "gemini-2.5-flash")
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        + model
        + ":generateContent?key="
        + api_key
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"response_mime_type": "application/json"},
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
    except TimeoutError as exc:
        raise TimeoutError("llm_timeout") from exc
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise RuntimeError("unsupported_model") from exc
        raise RuntimeError("provider_error") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError("provider_error") from exc

    try:
        text = response_payload["candidates"][0]["content"]["parts"][0]["text"]
        data = json.loads(_extract_json_text(text))
        if not isinstance(data, dict):
            raise ValueError("llm_invalid_response")
        return data
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("llm_invalid_response") from exc


def _count_difficult_topics(pending_topics: list[StudyTopicInput]) -> int:
    return sum(
        1
        for topic in pending_topics
        if topic.difficulty == "high" and topic.status != "reviewed"
    )


def _count_active_topics(pending_topics: list[StudyTopicInput]) -> int:
    return sum(1 for topic in pending_topics if topic.status != "reviewed")


def generate_rules_based_recommendation(
    discipline: dict[str, Any],
    simulation: dict[str, Any],
    pending_topics: list[StudyTopicInput],
    latency_ms: float = 0,
    fallback_reason: str | None = None,
) -> StudyRecommendationResponse:
    attendance = simulation.get("attendance") or {}
    academic_status = simulation.get("academic_status") or {}
    projected_mention = simulation.get("projected_mention")
    required = simulation.get("required_average_on_remaining")
    grade_risk = simulation.get("grade_risk_level")
    absence = attendance.get("absence_percentage")
    frequency = attendance.get("frequency")
    attendance_risk = attendance.get("risk_level")
    active_topics = _count_active_topics(pending_topics)
    difficult_topics = _count_difficult_topics(pending_topics)
    study_actions = build_study_actions(discipline, pending_topics)

    reasons: list[str] = []
    actions: list[str] = []
    missing: list[str] = []
    missing.append("disponibilidade de estudo")

    high_conditions = []
    if frequency is not None and frequency < 0.75:
        high_conditions.append("frequency_below_minimum")
        reasons.append("A frequência informada está abaixo do mínimo de 75% exigido pela UnB.")
    if attendance_risk == "high":
        high_conditions.append("high_attendance_risk")
        reasons.append("O risco por falta está alto.")
    if absence is not None and absence > 0.25:
        high_conditions.append("absence_above_limit")
    if projected_mention in FAILURE_MENTIONS:
        high_conditions.append("failing_mention")
        reasons.append(f"A menção projetada é {projected_mention}, que é uma menção de reprovação.")
    if required is not None and required > 8:
        high_conditions.append("high_required_grade")
        reasons.append("A nota necessária restante está acima de 8.")
    if required is not None and required > 10:
        high_conditions.append("unreachable_target")
        reasons.append("A meta informada não é alcançável apenas com as avaliações restantes.")
    if difficult_topics >= 3:
        high_conditions.append("many_difficult_topics")
        reasons.append("Há muitos conteúdos pendentes marcados como difíceis.")

    medium_conditions = []
    if grade_risk == "medium":
        medium_conditions.append("medium_grade_risk")
        reasons.append("O risco por nota está médio.")
    if absence is not None and 0.15 < absence <= 0.25:
        medium_conditions.append("medium_absence")
        reasons.append("As faltas estão entre 15% e 25%, exigindo atenção.")
    if required is not None and 6 < required <= 8:
        medium_conditions.append("medium_required_grade")
        reasons.append("A nota necessária restante está entre 6 e 8.")
    if 1 <= active_topics <= 4:
        medium_conditions.append("some_pending_topics")
        reasons.append("Há conteúdos pendentes que ainda precisam ser organizados.")

    low_conditions = []
    if projected_mention in APPROVAL_MENTIONS:
        low_conditions.append("passing_mention")
        reasons.append(f"A menção projetada é {projected_mention}, uma menção de aprovação na UnB.")
    if frequency is not None and frequency >= 0.85:
        low_conditions.append("comfortable_frequency")
        reasons.append("A frequência informada está confortável em relação ao mínimo de 75%.")
    if grade_risk == "low":
        low_conditions.append("low_grade_risk")
        reasons.append("O risco por nota está baixo na simulação atual.")
    if active_topics == 0:
        low_conditions.append("no_pending_topics")

    if high_conditions:
        dedication = "high"
        confidence = 0.88
    elif medium_conditions:
        dedication = "medium"
        confidence = 0.74
    else:
        dedication = "low" if low_conditions else "medium"
        confidence = 0.62 if low_conditions else 0.55

    if frequency is None:
        missing.append("frequência/faltas")
        reasons.append("A frequência está desconhecida, então não é possível afirmar aprovação final.")
    if simulation.get("partial_average") is None:
        missing.append("avaliações com nota")
    if required is None:
        missing.append("avaliações restantes ou pesos completos")

    if not pending_topics:
        missing.append("conteúdos cadastrados")
        actions.append("Cadastre ao menos um conteúdo com dificuldade e estado para receber uma atividade de estudo específica.")
    if study_actions:
        actions.extend(item["action"] for item in study_actions)
    if attendance_risk in {"medium", "high"} or (frequency is not None and frequency < 0.85):
        actions.append("Evite novas faltas, pois sua frequência está próxima ou abaixo do limite mínimo de 75%.")
    if simulation.get("partial_average") is None or simulation.get("completed_weight", 0) == 0:
        actions.append("Cadastre mais avaliações ou pesos para melhorar a precisão da simulação.")
    if not actions:
        actions.append("Mantenha revisões curtas durante a semana e acompanhe novas avaliações cadastradas.")

    grade_status = "Menção final: ainda não calculável." if simulation.get("remaining_weight", 0) > 0 else "Dados de nota insuficientes para calcular a menção final."
    if projected_mention:
        if simulation.get("remaining_weight", 0) > 0:
            grade_status += f" Projeção para a meta: {projected_mention}; não é resultado final."
        else:
            grade_status = f"Menção final calculada: {projected_mention}."
    if required is not None and required > 10:
        grade_status += " A nota necessária restante é maior que 10, então a meta está inalcançável apenas com as avaliações restantes."

    attendance_status = "Frequência desconhecida; não é possível afirmar aprovação final."
    if frequency is not None:
        attendance_status = (
            f"Frequência informada de {frequency * 100:.1f}% e risco por falta {attendance_risk}."
        )
        if frequency < 0.75:
            attendance_status += " O risco por falta deve ser tratado antes das recomendações de conteúdo."

    summary = academic_status.get("message") or "Situação acadêmica simulada a partir dos dados cadastrados."
    if frequency is None or simulation.get("remaining_weight", 0) > 0:
        summary += " Não há afirmação de aprovação final porque há dados pendentes ou frequência desconhecida."

    if not reasons:
        reasons.append("A recomendação foi gerada com os dados acadêmicos disponíveis no momento.")

    used_evidence = []
    if discipline.get("assessments"):
        used_evidence.append("avaliações planejadas/realizadas informadas pelo usuário ou confirmadas do plano")
    if discipline.get("course_plan"):
        used_evidence.append("dados estruturados confirmados do plano de ensino")
    if frequency is not None:
        used_evidence.append("frequência calculada por faltas em horas-aula")
    used_evidence.append("simulação determinística de nota e menção")
    influencing_assessments = [
        _safe_text(item.get("name"), 120)
        for item in discipline.get("assessments", [])
        if item.get("status") == "planned" and item.get("date")
    ][:10]

    return StudyRecommendationResponse(
        dedication_level=dedication,
        confidence=confidence,
        academic_situation_summary=summary,
        grade_status=grade_status,
        attendance_status=attendance_status,
        recommended_actions=actions,
        reasons=list(dict.fromkeys(reasons)),
        missing_information=list(dict.fromkeys(missing)),
        used_fallback=True,
        provider="rules",
        execution_mode="deterministic_fallback",
        fallback_reason=fallback_reason,
        model=None,
        latency_ms=latency_ms,
        warnings=list(dict.fromkeys(simulation.get("warnings", []))),
        used_evidence=used_evidence,
        influencing_assessments=influencing_assessments,
        study_actions=study_actions,
        strategy_references=strategy_references(study_actions),
    )


def generate_study_recommendation(
    discipline: dict[str, Any],
    simulation: dict[str, Any],
    pending_topics: list[StudyTopicInput],
    user_goal: str | None,
) -> StudyRecommendationResponse:
    start = _now_ms()
    discipline_id = str(discipline.get("id", ""))
    _log_event(
        "agent_recommendation_requested",
        provider=os.getenv("LLM_PROVIDER", "google"),
        used_fallback=False,
        discipline_id=discipline_id,
        pending_topics_count=len(pending_topics),
    )

    context = build_safe_prompt_context(discipline, simulation, pending_topics, user_goal)
    provider = os.getenv("LLM_PROVIDER", "google").strip().lower()
    fallback_enabled = _env_bool("LLM_FALLBACK_ENABLED", True)
    api_key_exists = bool(os.getenv("GOOGLE_API_KEY"))

    def fallback(error_type: str | None = None) -> StudyRecommendationResponse:
        response = generate_rules_based_recommendation(
            discipline,
            simulation,
            pending_topics,
            latency_ms=_duration_ms(start),
            fallback_reason=error_type,
        )
        _log_event(
            "fallback_used",
            provider="rules",
            used_fallback=True,
            latency_ms=response.latency_ms,
            error_type=error_type,
            discipline_id=discipline_id,
            pending_topics_count=len(pending_topics),
            dedication_level=response.dedication_level,
        )
        _log_event(
            "agent_recommendation_generated",
            provider=response.provider,
            used_fallback=response.used_fallback,
            latency_ms=response.latency_ms,
            discipline_id=discipline_id,
            pending_topics_count=len(pending_topics),
            dedication_level=response.dedication_level,
        )
        return response

    if provider != "google":
        return fallback("unsupported_provider")
    if not api_key_exists:
        return fallback("missing_api_key")

    _log_event(
        "llm_called",
        provider="google",
        used_fallback=False,
        discipline_id=discipline_id,
        pending_topics_count=len(pending_topics),
    )
    try:
        raw = generate_google_recommendation(context, timeout_seconds=_env_timeout())
        response = validate_llm_response(raw, latency_ms=_duration_ms(start))
        deterministic_actions = build_study_actions(discipline, pending_topics)
        response.study_actions = [StudyAction.model_validate(item) for item in deterministic_actions]
        response.strategy_references = [StudyStrategyReference.model_validate(item) for item in strategy_references(deterministic_actions)]
        if deterministic_actions:
            response.recommended_actions = [item["action"] for item in deterministic_actions]
        _log_event(
            "agent_recommendation_generated",
            provider=response.provider,
            used_fallback=response.used_fallback,
            latency_ms=response.latency_ms,
            discipline_id=discipline_id,
            pending_topics_count=len(pending_topics),
            dedication_level=response.dedication_level,
        )
        return response
    except TimeoutError:
        _log_event("llm_timeout", provider="google", used_fallback=False, error_type="timeout", discipline_id=discipline_id)
        if fallback_enabled:
            return fallback("timeout")
        raise
    except ValueError as exc:
        _log_event("llm_invalid_response", provider="google", used_fallback=False, error_type=type(exc).__name__, discipline_id=discipline_id)
        if fallback_enabled:
            return fallback("invalid_response")
        raise
    except Exception as exc:
        _log_event("llm_failed", provider="google", used_fallback=False, error_type=type(exc).__name__, discipline_id=discipline_id)
        if fallback_enabled:
            return fallback("provider_unavailable")
        raise

INSUFFICIENT_DATA = "Não há dados suficientes cadastrados para responder com segurança."


def generate_discipline_assistant_message(discipline, simulation, message, recent_messages, user_goal):
    context = build_safe_prompt_context(discipline, simulation, [], user_goal)
    planned = context["assessments"]["planned_confirmed"]
    undated = context["assessments"]["planned_without_date"]
    completed = context["assessments"]["completed_with_grades"]
    attendance = context["simulation"].get("attendance") or {}
    course_plan = context["course_plan"]
    assessment_contents = context.get("assessment_content_context") or []
    hierarchy = context.get("content_hierarchy") or []

    def flatten(nodes):
        return [item for node in nodes for item in [node, *flatten(node.get("children", []))]]

    all_nodes = flatten(hierarchy)

    def fallback(reason: str):
        question = message.casefold()
        evidence, actions, warnings = [], [], []
        if any(term in question for term in ("falta", "frequência", "frequencia")):
            frequency = attendance.get("frequency")
            if frequency is None:
                answer = INSUFFICIENT_DATA
                warnings = ["Cadastre a carga horária para calcular a frequência."]
            else:
                answer = f"Sua frequência calculada é {frequency * 100:.1f}%."
                evidence = [f"Fonte: cálculo acadêmico — frequência de {frequency * 100:.1f}%"]
                actions = ["Evite novas faltas e acompanhe o saldo na aba Frequência."]
        elif any(term in question for term in ("nota", "média", "media", "tirar")):
            required = context["simulation"].get("required_average_on_remaining")
            if not completed or required is None:
                answer = INSUFFICIENT_DATA
                warnings = ["Cadastre avaliações realizadas, pesos e notas."]
            else:
                answer = f"A simulação indica média {required:.2f} no peso restante para atingir a média alvo."
                evidence = [f"Fonte: cálculo acadêmico — nota necessária {required:.2f}"]
                actions = ["Confira os pesos em Ver cálculo completo."]
        elif planned:
            item = planned[0]
            linked = next((group for group in assessment_contents if group.get("assessment_name") == item["name"]), None)
            node_names = [node["title"] for node in (linked or {}).get("nodes", [])][:4]
            answer = f"A prioridade mais próxima é {item['name']}, prevista para {item['date']}."
            if node_names:
                answer += " Conteúdos associados: " + ", ".join(node_names) + "."
            evidence = [f"Fonte: avaliação confirmada — {item['name']} em {item['date']}"]
            for node in (linked or {}).get("nodes", [])[:4]:
                origin = "direta" if node.get("association_origin") == "direct" else "herdada pelo ancestral selecionado"
                evidence.append(f"{node['title']}: associação {origin}; estado {node.get('status')}; dificuldade {node.get('difficulty') or 'não informada'}.")
            actions = [f"Priorize {name} antes de {item['date']}." for name in node_names[:3]] or ["Associe conteúdos à avaliação para obter ações específicas."]
        elif all_nodes or any(term in question for term in ("conteúdo", "conteudo", "revis", "estud", "prior")):
            contents = [node.get("title") for node in all_nodes if node.get("title")]
            contents += course_plan.get("contents") or []
            available = list(dict.fromkeys(contents))[:5]
            if not available:
                answer = INSUFFICIENT_DATA
                warnings = ["Cadastre conteúdos ou confirme um plano de ensino."]
            else:
                answer = "Conteúdos confirmados disponíveis para estudo: " + ", ".join(available) + "."
                evidence = ["Fonte: mapa hierárquico da disciplina" if all_nodes else "Fonte: plano de ensino confirmado"]
                actions = [f"Defina estado e dificuldade de {item} para refinar a prioridade." for item in available[:3]]
        elif undated:
            item = undated[0]
            answer = "Foi identificada uma avaliação no plano de ensino, mas a data ainda não foi informada." if item.get("source") == "course_plan" else "Há uma avaliação cadastrada, mas a data ainda não foi informada."
            evidence = [f"Fonte: avaliação confirmada — {item['name']}; data não informada"]
            actions = ["Defina a data na aba Avaliações para habilitar a prioridade por proximidade."]
        else:
            answer = INSUFFICIENT_DATA
            warnings = ["Cadastre uma avaliação futura ou conteúdos."]
        return DisciplineAssistantResponse(
            source="fallback",
            execution_mode="deterministic_fallback",
            fallback_reason=reason,
            model=None,
            answer=answer,
            evidence=evidence,
            suggested_actions=actions,
            warnings=warnings,
        )

    provider = os.getenv("LLM_PROVIDER", "google").strip().lower()
    if provider != "google":
        return fallback("unsupported_provider")
    if not os.getenv("GOOGLE_API_KEY"):
        return fallback("missing_api_key")
    schema = {"answer": "", "evidence": [], "suggested_actions": [], "warnings": []}
    prompt = "Responda em português e somente JSON. Use apenas o contexto. Não invente dados nem afirme resultado definitivo. Se faltar evidência, responda exatamente: " + INSUFFICIENT_DATA + ". Schema: " + json.dumps(schema, ensure_ascii=False) + "\nContexto: " + json.dumps(context, ensure_ascii=False) + "\nHistórico: " + json.dumps(recent_messages[-8:], ensure_ascii=False) + "\nPergunta: " + _safe_text(message, 1000)
    try:
        response = DisciplineAssistantResponse(source="gemini", execution_mode="llm", fallback_reason=None, model=os.getenv("LLM_MODEL", "gemini-2.5-flash"), **generate_google_json(prompt, _env_timeout()))
        if not response.evidence and response.answer != INSUFFICIENT_DATA:
            raise ValueError("assistant_response_without_evidence")
        return response
    except TimeoutError as exc:
        reason = "timeout"
        _log_event("assistant_fallback_used", discipline_id=str(discipline.get("id", "")), error_type=reason)
        return fallback(reason)
    except ValueError as exc:
        reason = "invalid_response"
        _log_event("assistant_fallback_used", discipline_id=str(discipline.get("id", "")), error_type=reason)
        return fallback(reason)
    except Exception as exc:
        reason = "provider_unavailable"
        _log_event("assistant_fallback_used", discipline_id=str(discipline.get("id", "")), error_type=reason)
        return fallback(reason)
