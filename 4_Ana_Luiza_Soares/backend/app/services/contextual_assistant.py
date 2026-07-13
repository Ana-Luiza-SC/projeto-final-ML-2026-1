from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from app import storage
from app.schemas import ContextualAssistantRequest
from app.services.study_method_catalog import recommend_study_methods


class ContextualAssistantError(ValueError):
    pass


MUTATING_ACTIONS = {"create_study_block", "modify_unconfirmed_plan"}
ACTION_TTL_MINUTES = 15


def _infer_intent(payload: ContextualAssistantRequest) -> str:
    if payload.intent != "general":
        return payload.intent
    text = payload.message.casefold()
    if any(
        term in text
        for term in ["método", "metodo", "técnica", "tecnica", "como estudar"]
    ):
        return "recommend_methods"
    if any(
        term in text
        for term in [
            "capacidade",
            "não coube",
            "nao coube",
            "sem horário",
            "sem horario",
        ]
    ):
        return "explain_capacity_shortage"
    if any(
        term in text
        for term in ["bloco", "calendário", "calendario", "agendar", "reservar"]
    ):
        return "propose_study_block"
    return "explain_priority"


def _selected_priority(
    preview: dict | None,
    payload: ContextualAssistantRequest,
) -> dict | None:
    if not preview:
        return None
    priorities = preview.get("ranked_priorities") or []
    if payload.selected_priority_id:
        selected = next(
            (
                item
                for item in priorities
                if item.get("priority_item_id") == payload.selected_priority_id
            ),
            None,
        )
        if selected:
            return selected
    if payload.selected_discipline_id:
        selected = next(
            (
                item
                for item in priorities
                if str(item.get("discipline_id"))
                == str(payload.selected_discipline_id)
            ),
            None,
        )
        if selected:
            return selected
    return priorities[0] if priorities else None


def _discipline(payload: ContextualAssistantRequest) -> dict | None:
    if not payload.selected_discipline_id:
        return None
    discipline = storage.get_discipline(str(payload.selected_discipline_id))
    if discipline is None:
        raise ContextualAssistantError("Disciplina não encontrada.")
    return discipline


def _navigation(
    action_type: str,
    label: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    return {
        "action_id": None,
        "type": action_type,
        "label": label,
        "payload": payload,
        "requires_confirmation": False,
    }


def _store_proposal(
    action_type: str,
    label: str,
    action_payload: dict[str, Any],
) -> dict[str, Any]:
    action_id = str(uuid4())
    action = {
        "action_id": action_id,
        "type": action_type,
        "label": label,
        "payload": action_payload,
        "requires_confirmation": True,
        "created_at": storage.utc_now(),
        "expires_at": storage.utc_now()
        + timedelta(minutes=ACTION_TTL_MINUTES),
        "executed_result": None,
    }
    storage.save_assistant_action(action)
    return {
        key: action[key]
        for key in [
            "action_id",
            "type",
            "label",
            "payload",
            "requires_confirmation",
        ]
    }


def _task_type(message: str, discipline: dict | None) -> str:
    text = " ".join(
        [
            message,
            str((discipline or {}).get("name", "")),
            str((discipline or {}).get("syllabus", "")),
        ]
    ).casefold()
    if any(term in text for term in ["program", "código", "codigo", "algorit"]):
        return "programming"
    if any(term in text for term in ["prova", "avalia", "exame"]):
        return "exam_preparation"
    if any(term in text for term in ["projeto", "relatório", "relatorio"]):
        return "project"
    return "conceptual"


def _method_response(
    payload: ContextualAssistantRequest,
    discipline: dict | None,
    preview: dict | None,
) -> tuple[str, list[dict], list[dict], str]:
    block = next(
        (
            item
            for item in (preview or {}).get("planned_blocks", [])
            if not discipline
            or str(item.get("discipline_id")) == str(discipline["id"])
        ),
        None,
    )
    available_minutes = None
    if block:
        available_minutes = int(
            (
                datetime.fromisoformat(block["end_at"])
                - datetime.fromisoformat(block["start_at"])
            ).total_seconds()
            // 60
        )
    methods = recommend_study_methods(
        _task_type(payload.message, discipline),
        available_minutes,
    )
    names = ", ".join(item["name"] for item in methods["methods"])
    evidence = [
        {
            "source_type": "study_method_catalog",
            "source_id": methods["document_id"],
            "summary": (
                f"Catálogo versionado {methods['catalog_version']}; "
                f"{len(methods['methods'])} métodos selecionados."
            ),
        }
    ]
    evidence.extend(
        {
            "source_type": "study_method_catalog",
            "source_id": method["id"],
            "summary": (
                f"{method['name']}: {method['purpose']} "
                f"Evidência: {method['evidence_level']}. "
                f"Limites: {'; '.join(method['limitations'])}"
            ),
        }
        for method in methods["methods"]
    )
    return (
        "Até três opções compatíveis com o contexto: "
        f"{names}. Compare propósito, evidência e limitações antes de escolher.",
        evidence,
        [
            _navigation(
                "navigate_to_planning",
                "Abrir planejamento",
                {"path": "/study-plan"},
            )
        ],
        methods["catalog_version"],
    )


def build_contextual_response(
    payload: ContextualAssistantRequest,
) -> dict[str, Any]:
    discipline = _discipline(payload)
    preview = storage.latest_study_plan_preview()
    priority = _selected_priority(preview, payload)
    intent = _infer_intent(payload)
    evidence: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []
    warnings: list[str] = []
    catalog_version = None

    if intent == "recommend_methods":
        message, evidence, actions, catalog_version = _method_response(
            payload,
            discipline,
            preview,
        )
    elif intent == "explain_capacity_shortage":
        analyses = (preview or {}).get("capacity_analysis") or []
        analysis = next(
            (
                item
                for item in analyses
                if priority
                and item.get("priority_item_id")
                == priority.get("priority_item_id")
            ),
            analyses[0] if analyses else None,
        )
        if analysis:
            message = analysis["reason"]
            evidence.append(
                {
                    "source_type": "capacity",
                    "source_id": analysis["priority_item_id"],
                    "summary": (
                        f"Demanda {analysis.get('requested_minutes')} min; "
                        f"alocados {analysis['allocated_minutes']} min; "
                        f"utilizáveis "
                        f"{analysis['usable_minutes_before_deadline']} min; "
                        f"bloqueados {analysis['blocked_minutes']} min; "
                        f"bloco mínimo "
                        f"{analysis['minimum_useful_block_minutes']} min."
                    ),
                }
            )
        else:
            message = (
                "Gere uma prévia em Planejamento para calcular demanda, "
                "conflitos e capacidade antes do prazo."
            )
            warnings.append(
                "Ainda não há análise de capacidade para esta semana."
            )
        actions.append(
            _navigation(
                "navigate_to_planning",
                "Revisar disponibilidade",
                {"path": "/study-plan"},
            )
        )
    elif intent in {"propose_study_block", "recommend_window"}:
        block = next(
            (
                item
                for item in (preview or {}).get("planned_blocks", [])
                if not discipline
                or str(item.get("discipline_id")) == str(discipline["id"])
            ),
            None,
        )
        if block:
            message = (
                f"Há um intervalo validado para {block['discipline_name']}, "
                f"de {block['start_at']} a {block['end_at']}. Posso "
                "adicioná-lo somente após sua confirmação."
            )
            evidence.append(
                {
                    "source_type": "priority",
                    "source_id": (
                        priority.get("priority_item_id") if priority else None
                    ),
                    "summary": block["reason"],
                }
            )
            actions.append(
                _store_proposal(
                    "create_study_block",
                    "Adicionar bloco ao calendário",
                    {
                        "study_plan_id": (preview or {})["study_plan_id"],
                        "temporary_id": block["temporary_id"],
                    },
                )
            )
            actions.append(
                _navigation(
                    "navigate_to_calendar_date",
                    "Abrir data no calendário",
                    {
                        "path": "/calendar",
                        "date": block["start_at"][:10],
                    },
                )
            )
        else:
            message = (
                "Não há um bloco validado para propor. Configure a "
                "disponibilidade e gere uma prévia primeiro."
            )
            warnings.append(
                "O assistente não cria horários fora de uma prévia "
                "validada pelo backend."
            )
            actions.append(
                _navigation(
                    "navigate_to_planning",
                    "Gerar prévia",
                    {"path": "/study-plan"},
                )
            )
    elif priority:
        deadline = priority.get("deadline_at") or "sem prazo conhecido"
        message = (
            f"{priority['discipline_name']} está em "
            f"{priority['priority_band']} prioridade "
            f"(pontuação {priority['priority_score']}/100), com prazo "
            f"{deadline}. {priority['reason']}"
        )
        evidence.extend(
            {
                "source_type": "priority",
                "source_id": item.get("source_id"),
                "summary": item["summary"],
            }
            for item in priority.get("evidence_used", [])
        )
        if priority.get("missing_evidence"):
            warnings.append(
                "Evidências ausentes: "
                + ", ".join(priority["missing_evidence"])
            )
        actions.append(
            _navigation(
                "explain_capacity_shortage",
                "Explicar capacidade",
                {
                    "intent": "explain_capacity_shortage",
                    "priority_item_id": priority["priority_item_id"],
                },
            )
        )
    elif discipline:
        assessments = [
            item
            for item in storage.list_assessments(str(discipline["id"]))
            if item.get("status") == "planned"
        ]
        message = (
            f"Ainda não existe uma prioridade semanal calculada para "
            f"{discipline['name']}. Há {len(assessments)} avaliação(ões) "
            "planejada(s); gere a prévia para obter uma classificação "
            "auditável."
        )
        evidence.append(
            {
                "source_type": "discipline",
                "source_id": str(discipline["id"]),
                "summary": (
                    f"Disciplina {discipline.get('code')}: "
                    f"{len(assessments)} avaliações planejadas."
                ),
            }
        )
        actions.append(
            _navigation(
                "navigate_to_planning",
                "Calcular prioridades",
                {"path": "/study-plan"},
            )
        )
    else:
        message = (
            "Posso explicar prioridades, capacidade, métodos de estudo e "
            "propostas de bloco usando os dados acadêmicos cadastrados."
        )
        actions.append(
            _navigation(
                "navigate_to_planning",
                "Abrir planejamento",
                {"path": "/study-plan"},
            )
        )

    if discipline:
        actions.append(
            _navigation(
                "navigate_to_discipline",
                "Abrir disciplina",
                {
                    "path": f"/disciplines/{discipline['id']}",
                    "discipline_id": str(discipline["id"]),
                },
            )
        )
    return {
        "message": message,
        "execution_mode": "deterministic_fallback",
        "evidence": evidence,
        "suggested_actions": actions,
        "warnings": warnings,
        "study_method_catalog_version": catalog_version,
    }


def _find_preview_block(action: dict) -> tuple[dict, dict]:
    payload = action["payload"]
    preview = storage.get_study_plan_preview(
        str(payload.get("study_plan_id", ""))
    )
    if not preview:
        raise ContextualAssistantError(
            "A prévia expirou. Gere um novo planejamento."
        )
    block = next(
        (
            item
            for item in preview.get("planned_blocks", [])
            if item.get("temporary_id") == payload.get("temporary_id")
        ),
        None,
    )
    if not block:
        raise ContextualAssistantError(
            "O bloco proposto não pertence à prévia atual."
        )
    if storage.get_discipline(str(block.get("discipline_id"))) is None:
        raise ContextualAssistantError("Disciplina não encontrada.")
    return preview, block


def _conflicting_event(block: dict) -> dict | None:
    start = datetime.fromisoformat(block["start_at"])
    end = datetime.fromisoformat(block["end_at"])
    for event in storage.list_events(
        start_at=start,
        end_at=end,
        status="confirmed",
    ):
        event_start = datetime.fromisoformat(event["start_at"])
        event_end = (
            datetime.fromisoformat(event["end_at"])
            if event.get("end_at")
            else event_start
        )
        if start < event_end and event_start < end:
            return event
    return None


def confirm_contextual_action(action_id: str) -> dict[str, Any]:
    action = storage.get_assistant_action(action_id)
    if not action:
        raise ContextualAssistantError(
            "A ação não existe, expirou ou pertence a outro usuário."
        )
    if action["type"] not in MUTATING_ACTIONS:
        raise ContextualAssistantError(
            "Esta ação não exige confirmação no backend."
        )
    if action.get("executed_result"):
        return {
            "action_id": action_id,
            "action_type": action["type"],
            "status": "already_executed",
            "result": action["executed_result"],
        }
    if action["type"] != "create_study_block":
        raise ContextualAssistantError(
            "Tipo de mutação ainda não implementado."
        )
    preview, block = _find_preview_block(action)
    fingerprint = f"assistant:{action_id}:{block['temporary_id']}"
    existing = storage.find_event_by_fingerprint(fingerprint)
    if existing:
        event = storage.get_event(existing["id"])
    else:
        conflict = _conflicting_event(block)
        if conflict:
            raise ContextualAssistantError(
                "O horário passou a conflitar com um evento confirmado. "
                "Gere uma nova prévia."
            )
        event = storage.create_event(
            {
                "discipline_id": block["discipline_id"],
                "assessment_id": block.get("assessment_id"),
                "title": block["title"],
                "description": block.get("reason"),
                "event_type": "study_block",
                "start_at": block["start_at"],
                "end_at": block["end_at"],
                "all_day": False,
                "timezone": "America/Sao_Paulo",
                "weight": None,
                "status": "confirmed",
                "source": "study_plan",
                "source_evidence": block.get("reason"),
                "extraction_confidence": 1.0,
                "source_fingerprint": fingerprint,
                "study_plan_id": preview["study_plan_id"],
                "content_id": block.get("content_id"),
                "priority_score": block.get("priority_score"),
                "priority_band": block.get("priority_band"),
                "priority_reason": block.get("reason"),
                "algorithm_version": preview.get("algorithm_version"),
                "generated_at": preview.get("generated_at"),
            }
        )
    result = {"event": event}
    action["executed_result"] = result
    storage.save_assistant_action(action)
    return {
        "action_id": action_id,
        "action_type": action["type"],
        "status": "executed",
        "result": result,
    }
