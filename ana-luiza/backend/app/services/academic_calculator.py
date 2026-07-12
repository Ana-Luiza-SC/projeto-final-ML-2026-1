from __future__ import annotations

from typing import Any

APPROVAL_MENTIONS = {"SS", "MS", "MM"}
FAILURE_MENTIONS = {"MI", "II", "SR"}


def _read_field(item: Any, field: str) -> Any:
    if isinstance(item, dict):
        return item.get(field)
    return getattr(item, field, None)


def normalize_weight(weight: float) -> float:
    if weight is None:
        raise ValueError("Peso é obrigatório.")
    weight = float(weight)
    if weight <= 0:
        raise ValueError("Peso deve ser positivo.")
    if weight > 100:
        raise ValueError("Peso não pode ser maior que 100%.")
    if weight > 1:
        return weight / 100
    return weight


def validate_grade(grade: float) -> float:
    grade = float(grade)
    if grade < 0 or grade > 10:
        raise ValueError("Nota deve estar entre 0 e 10.")
    return grade


def normalize_assessments_weights(assessments: list[Any]) -> list[dict[str, Any]]:
    normalized = []
    for assessment in assessments:
        if _read_field(assessment, "status") == "cancelled":
            continue
        grade = _read_field(assessment, "grade")
        normalized.append(
            {
                "name": _read_field(assessment, "name"),
                "weight": (normalize_weight(_read_field(assessment, "group_final_weight")) * normalize_weight(_read_field(assessment, "group_weight"))) if _read_field(assessment, "group_final_weight") is not None and _read_field(assessment, "group_weight") is not None else (normalize_weight(_read_field(assessment, "weight")) if _read_field(assessment, "weight") is not None else None),
                "grade": validate_grade(grade) if grade is not None else None,
                "date": _read_field(assessment, "date"),
                "topics": _read_field(assessment, "topics") or [],
                "group_code": _read_field(assessment, "evaluation_group_code") or _read_field(assessment, "group_code"),
                "group_name": _read_field(assessment, "evaluation_group_name") or _read_field(assessment, "group_name"),
                "group_final_weight": normalize_weight(_read_field(assessment, "group_final_weight")) if _read_field(assessment, "group_final_weight") is not None else None,
                "group_weight": normalize_weight(_read_field(assessment, "group_weight")) if _read_field(assessment, "group_weight") is not None else None,
            }
        )
    return normalized


def grade_to_mention(grade: float) -> str:
    grade = validate_grade(grade)
    if grade >= 9.0:
        return "SS"
    if grade >= 7.0:
        return "MS"
    if grade >= 5.0:
        return "MM"
    if grade >= 3.0:
        return "MI"
    if grade > 0.0:
        return "II"
    return "SR"


def classify_grade_risk(required_average_on_remaining: float | None) -> str:
    if required_average_on_remaining is None:
        return "unknown"
    if required_average_on_remaining <= 6.0:
        return "low"
    if required_average_on_remaining <= 8.0:
        return "medium"
    return "high"


def calculate_grade_simulation(
    assessments: list[Any], target_average: float = 5.0
) -> dict[str, Any]:
    target_average = validate_grade(target_average)
    normalized = normalize_assessments_weights(assessments)
    completed = [item for item in normalized if item["grade"] is not None and item["weight"] is not None]

    current_contribution = sum(item["grade"] * item["weight"] for item in completed)
    completed_weight = sum(item["weight"] for item in completed)
    remaining_weight = max(0.0, 1.0 - completed_weight)
    partial_average = current_contribution / completed_weight if completed_weight else None

    warnings: list[str] = []
    if any(item["weight"] is None for item in normalized):
        warnings.append("Há avaliações sem peso conhecido; a simulação está incompleta.")
    total_weight = sum(item["weight"] for item in normalized if item["weight"] is not None)
    if normalized and abs(total_weight - 1.0) > 0.001:
        warnings.append("A soma dos pesos cadastrados é diferente de 100%.")

    required_average_on_remaining = None
    if remaining_weight > 0:
        required_average_on_remaining = max(
            0.0, (target_average - current_contribution) / remaining_weight
        )
        if required_average_on_remaining > 10:
            warnings.append(
                "Meta inalcançável apenas com as avaliações restantes."
            )

    group_results = []
    group_codes = list(dict.fromkeys(item["group_code"] for item in normalized if item.get("group_code")))
    for group_code in group_codes:
        items = [item for item in normalized if item.get("group_code") == group_code]
        graded = [item for item in items if item["grade"] is not None and item.get("group_weight") is not None]
        complete = len(graded) == len(items) and bool(items)
        internal_weight = sum(item.get("group_weight") or 0 for item in graded)
        group_average = sum(item["grade"] * item["group_weight"] for item in graded) / internal_weight if complete and internal_weight else None
        group_results.append({"code": group_code, "name": items[0].get("group_name") or group_code, "average": group_average, "status": "calculated" if group_average is not None else "insufficient_data", "meets_minimum_5": group_average >= 5 if group_average is not None else None})

    current_mention = grade_to_mention(partial_average) if partial_average is not None else None
    if remaining_weight == 0:
        projected_average = min(10.0, max(0.0, current_contribution))
    elif required_average_on_remaining is not None and required_average_on_remaining <= 10:
        projected_average = target_average
    else:
        projected_average = partial_average
    projected_mention = (
        grade_to_mention(projected_average) if projected_average is not None else None
    )

    return {
        "current_contribution": current_contribution,
        "partial_average": partial_average,
        "completed_weight": completed_weight,
        "remaining_weight": remaining_weight,
        "target_average": target_average,
        "required_average_on_remaining": required_average_on_remaining,
        "current_mention": current_mention,
        "projected_mention": projected_mention,
        "grade_risk_level": classify_grade_risk(required_average_on_remaining),
        "warnings": warnings,
        "group_results": group_results,
    }


def classify_attendance_risk(absence_percentage: float | None) -> str:
    if absence_percentage is None:
        return "unknown"
    if absence_percentage <= 0.15:
        return "low"
    if absence_percentage <= 0.25:
        return "medium"
    return "high"


def _calculate_absence(total: int | float | None, missed: int | float | None) -> tuple[float, float] | None:
    if total is None or missed is None:
        return None
    total = float(total)
    missed = float(missed)
    if total <= 0:
        raise ValueError("Total de aulas ou horas deve ser positivo.")
    if missed < 0:
        raise ValueError("Faltas não podem ser negativas.")
    if missed > total:
        raise ValueError("Faltas não podem ser maiores que o total.")
    absence_percentage = missed / total
    return 1 - absence_percentage, absence_percentage


def calculate_attendance(
    total_classes: int | None = None,
    missed_classes: int | None = None,
    total_class_hours: int | None = None,
    missed_class_hours: int | None = None,
) -> dict[str, Any]:
    source = None
    result = _calculate_absence(total_class_hours, missed_class_hours)
    if result is not None:
        source = "class_hours"
    else:
        result = _calculate_absence(total_classes, missed_classes)
        if result is not None:
            source = "classes"

    if result is None:
        return {
            "status": "unknown",
            "source": None,
            "frequency": None,
            "absence_percentage": None,
            "risk_level": "unknown",
            "warnings": ["Frequência desconhecida; não é possível afirmar aprovação final."],
        }

    frequency, absence_percentage = result
    risk_level = classify_attendance_risk(absence_percentage)
    warnings = []
    status = "ok"
    if frequency < 0.75:
        status = "risk_of_failure_by_attendance"
        warnings.append("Frequência abaixo de 75%; há risco de reprovação por falta.")
    elif risk_level == "medium":
        status = "attention"
        warnings.append("Faltas próximas do limite de 25%.")

    return {
        "status": status,
        "source": source,
        "frequency": frequency,
        "absence_percentage": absence_percentage,
        "risk_level": risk_level,
        "warnings": warnings,
    }


def classify_academic_status(
    grade_result: dict[str, Any], attendance_result: dict[str, Any]
) -> dict[str, Any]:
    warnings = list(grade_result.get("warnings", [])) + list(
        attendance_result.get("warnings", [])
    )
    attendance_status = attendance_result.get("status")
    projected_mention = grade_result.get("projected_mention")
    remaining_weight = grade_result.get("remaining_weight")

    if attendance_status == "unknown":
        return {
            "status": "insufficient_attendance_data",
            "message": "Frequência desconhecida; não é possível afirmar aprovação final.",
            "warnings": warnings,
        }

    if attendance_status == "risk_of_failure_by_attendance":
        return {
            "status": "risk_of_failure_by_attendance",
            "message": "Há risco de reprovação por falta mesmo que a nota esteja suficiente.",
            "warnings": warnings,
        }

    if projected_mention in FAILURE_MENTIONS:
        return {
            "status": "risk_of_failure_by_grade",
            "message": "A menção simulada não é suficiente para aprovação.",
            "warnings": warnings,
        }

    if projected_mention in APPROVAL_MENTIONS:
        if remaining_weight and remaining_weight > 0:
            return {
                "status": "passing_simulation",
                "message": "A simulação indica menção de aprovação, mas ainda há avaliações pendentes.",
                "warnings": warnings,
            }
        return {
            "status": "passing_by_current_records",
            "message": "Os registros atuais indicam menção e frequência suficientes.",
            "warnings": warnings,
        }

    return {
        "status": "insufficient_grade_data",
        "message": "Dados de nota insuficientes para simular a situação acadêmica.",
        "warnings": warnings,
    }
