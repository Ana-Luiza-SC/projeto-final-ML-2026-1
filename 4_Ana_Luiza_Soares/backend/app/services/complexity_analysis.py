from __future__ import annotations

import logging
import re
import time
from typing import Any

from app import storage

VERSION = "study-demand-v2"
logger = logging.getLogger("estudaunb.study_demand")

FACTOR_LEVELS = {"unknown": 0, "low": 1, "moderate": 2, "high": 3}


def _sentences(text: str) -> list[str]:
    return [
        sentence.strip()
        for sentence in re.split(r"[.;\n]+", text)
        if sentence.strip()
    ]


def _keyword_count(text: str, keywords: tuple[str, ...]) -> int:
    normalized = text.casefold()
    return sum(normalized.count(keyword) for keyword in keywords)


def _factor_level(score: int) -> str:
    if score >= 5:
        return "high"
    if score >= 2:
        return "moderate"
    return "low"


def _unfinished_content(discipline_id: str) -> list[dict[str, Any]]:
    nodes = storage.CONTENT_NODES.get(discipline_id, {})
    values = list(nodes.values()) if isinstance(nodes, dict) else list(nodes or [])
    return [
        node
        for node in values
        if node.get("status", "not_started") not in {"studied", "reviewed"}
    ]


def _learner_difficulty(
    assessments: list[dict[str, Any]], contents: list[dict[str, Any]]
) -> dict[str, Any]:
    evidence: list[dict[str, str]] = []
    missing: list[str] = []
    completed_grades = [
        float(item["grade"])
        for item in assessments
        if item.get("status") == "completed" and item.get("grade") is not None
    ]
    reported_difficult = [
        item for item in contents if item.get("difficulty") == "high"
    ]

    if completed_grades:
        average = sum(completed_grades) / len(completed_grades)
        evidence.append(
            {
                "type": "learner_history",
                "summary": f"Media de {len(completed_grades)} avaliacao(oes) concluida(s): {average:.1f}.",
            }
        )
    else:
        average = None
        missing.append("desempenho anterior")

    if reported_difficult:
        evidence.append(
            {
                "type": "content_hierarchy",
                "summary": f"{len(reported_difficult)} conteudo(s) marcado(s) como dificil(is).",
            }
        )
    elif contents:
        missing.append("dificuldade percebida dos conteudos")
    else:
        missing.append("historico de conteudos")

    if average is None and not reported_difficult:
        level = "insufficient_evidence"
    elif (average is not None and average < 5) or len(reported_difficult) >= 2:
        level = "high"
    elif (average is not None and average < 7) or reported_difficult:
        level = "moderate"
    else:
        level = "low"

    confidence = min(
        1.0,
        (0.65 if completed_grades else 0)
        + (0.35 if contents else 0),
    )
    return {
        "level": level,
        "confidence": round(confidence, 2),
        "evidence_used": evidence,
        "missing_evidence": missing,
    }


def _build_analysis(discipline_id: str, discipline: dict[str, Any]) -> dict[str, Any]:
    syllabus = (discipline.get("syllabus") or "")[:20000].strip()
    workload = discipline.get("workload_hours")
    prerequisites = (discipline.get("prerequisites") or "").strip()
    contents = _unfinished_content(discipline_id)
    assessments = storage.list_assessments(discipline_id)
    active_assessments = [
        item
        for item in assessments
        if item.get("status", "planned") != "cancelled"
    ]
    completed = [
        item
        for item in assessments
        if item.get("status") == "completed" and item.get("grade") is not None
    ]

    evidence: list[dict[str, str]] = []
    missing: list[str] = []
    coverage = 0.0

    if syllabus:
        coverage += 0.35
        excerpt = _sentences(syllabus)
        evidence.append(
            {
                "type": "syllabus",
                "summary": excerpt[0][:240] if excerpt else "Ementa disponivel.",
            }
        )
    else:
        missing.append("ementa")
    if workload:
        coverage += 0.10
        evidence.append(
            {"type": "workload", "summary": f"Carga horaria: {workload}h."}
        )
    else:
        missing.append("carga horaria")
    if prerequisites:
        coverage += 0.15
        evidence.append(
            {
                "type": "prerequisites",
                "summary": f"Pre-requisitos informados: {prerequisites[:200]}.",
            }
        )
    else:
        missing.append("pre-requisitos")
    if contents:
        coverage += 0.15
        evidence.append(
            {
                "type": "content_hierarchy",
                "summary": f"{len(contents)} conteudo(s) pendente(s) estruturado(s).",
            }
        )
    else:
        missing.append("hierarquia de conteudos")
    if active_assessments:
        coverage += 0.15
        evidence.append(
            {
                "type": "assessment_structure",
                "summary": f"{len(active_assessments)} avaliacao(oes) estruturada(s).",
            }
        )
    else:
        missing.append("estrutura de avaliacoes")
    if completed:
        coverage += 0.10
        evidence.append(
            {
                "type": "learner_history",
                "summary": f"{len(completed)} resultado(s) anterior(es) disponivel(is).",
            }
        )
    else:
        missing.append("historico do estudante")

    factors = {
        "conceptual_breadth": "unknown",
        "prerequisite_depth": "unknown",
        "mathematical_or_algorithmic_density": "unknown",
        "project_workload": "unknown",
        "assessment_concentration": "unknown",
    }

    if syllabus or contents:
        breadth_score = len(_sentences(syllabus)) + min(5, len(contents))
        factors["conceptual_breadth"] = _factor_level(breadth_score)
    if prerequisites:
        prerequisite_count = len(
            [item for item in re.split(r"[,;]+", prerequisites) if item.strip()]
        )
        factors["prerequisite_depth"] = (
            "high" if prerequisite_count >= 3 else "moderate"
        )
    if syllabus:
        algorithm_score = _keyword_count(
            syllabus,
            (
                "algoritm",
                "matem",
                "calculo",
                "estat",
                "complexidade",
                "programa",
                "prova",
            ),
        )
        project_score = _keyword_count(
            syllabus, ("projeto", "laborat", "implement", "relatorio", "software")
        )
        factors["mathematical_or_algorithmic_density"] = _factor_level(
            algorithm_score
        )
        factors["project_workload"] = _factor_level(project_score)
    if active_assessments:
        total_weight = sum(float(item.get("weight") or 0) for item in active_assessments)
        concentration_score = len(active_assessments) + int(total_weight >= 80) * 2
        factors["assessment_concentration"] = _factor_level(concentration_score)

    meaningful_without_syllabus = sum(
        bool(value)
        for value in (prerequisites, contents, active_assessments)
    )
    if not syllabus and meaningful_without_syllabus < 2:
        demand_level = "insufficient_evidence"
    else:
        known_scores = [
            FACTOR_LEVELS[value]
            for value in factors.values()
            if value != "unknown"
        ]
        average_factor = (
            sum(known_scores) / len(known_scores) if known_scores else 0
        )
        if average_factor >= 2.45 or known_scores.count(3) >= 2:
            demand_level = "high"
        elif average_factor >= 1.55:
            demand_level = "moderate"
        else:
            demand_level = "low"

    warnings = (
        [
            "Ainda nao ha evidencia suficiente para classificar a demanda da disciplina."
        ]
        if demand_level == "insufficient_evidence"
        else []
    )
    return {
        "demand_level": demand_level,
        "confidence": round(coverage, 2),
        "evidence_coverage": round(coverage, 2),
        "evidence_used": evidence,
        "missing_evidence": missing,
        "factors": factors,
        "learner_specific_difficulty": _learner_difficulty(
            assessments, contents
        ),
        "mode": "deterministic_fallback",
        "model_or_rule_version": VERSION,
        "analyzed_at": storage.utc_now(),
        "warnings": warnings,
    }


def analyze(
    discipline_id: str, reanalyze: bool = False, generator: Any = None
) -> dict[str, Any]:
    del generator
    start = time.perf_counter()
    if not reanalyze:
        cached = storage.COMPLEXITY_ANALYSES.get(discipline_id)
        if cached and cached.get("model_or_rule_version") == VERSION:
            return cached
    discipline = storage.get_discipline(discipline_id)
    if not discipline:
        raise ValueError("Disciplina nao encontrada.")

    result = _build_analysis(discipline_id, discipline)
    storage.COMPLEXITY_ANALYSES[discipline_id] = result
    persisted = storage.COMPLEXITY_ANALYSES[discipline_id]
    logger.info(
        "study_demand_analyzed discipline_id=%s mode=%s version=%s latency_ms=%.2f "
        "evidence_count=%d missing_count=%d",
        discipline_id,
        persisted["mode"],
        persisted["model_or_rule_version"],
        (time.perf_counter() - start) * 1000,
        len(persisted["evidence_used"]),
        len(persisted["missing_evidence"]),
    )
    return persisted
