from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

CATALOG_PATH = (
    Path(__file__).resolve().parents[1]
    / "knowledge"
    / "study_methods"
    / "study_methods.json"
)


class StudyMethodCatalogError(ValueError):
    pass


@lru_cache(maxsize=1)
def load_study_method_catalog() -> dict[str, Any]:
    payload = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    policy = payload.get("ingestion_policy") or {}
    if (
        payload.get("canonical_ingestion_source") != "study_methods.json"
        or policy.get("embed_json") is not True
        or policy.get("embed_pdf") is not False
        or not isinstance(payload.get("methods"), list)
    ):
        raise StudyMethodCatalogError("Catálogo de métodos de estudo inválido.")
    return payload


def _task_tags(task_type: str) -> set[str]:
    return {
        "programming": {
            "programming",
            "algorithms",
            "procedural",
            "code_comprehension",
        },
        "exam_preparation": {"exam_preparation", "factual", "conceptual"},
        "conceptual": {"conceptual", "conceptual_learning", "concepts"},
        "project": {"programming", "procedural", "conceptual_learning"},
        "general": {"conceptual", "factual", "procedural"},
    }.get(task_type, {"conceptual", "factual", "procedural"})


def recommend_study_methods(
    task_type: str = "general",
    available_minutes: int | None = None,
) -> dict[str, Any]:
    catalog = load_study_method_catalog()
    tags = _task_tags(task_type)
    scored = []
    for method in catalog["methods"]:
        recommended = set(method.get("recommended_for") or [])
        score = len(tags & recommended)
        if method.get("category") == "learning_strategy":
            score += 2
        scored.append((score, method["id"], method))
    selected = [
        item[2]
        for item in sorted(scored, key=lambda item: (-item[0], item[1]))[:3]
    ]
    return {
        "catalog_version": catalog["schema_version"],
        "document_id": catalog["document_id"],
        "available_minutes": available_minutes,
        "methods": [
            {
                "id": method["id"],
                "name": method["name"],
                "category": method["category"],
                "evidence_level": method["evidence_level"],
                "purpose": method["purpose"],
                "limitations": method.get("limitations", []),
                "requires_cognitive_strategy_pairing": (
                    method.get("category") == "time_management_format"
                ),
            }
            for method in selected
        ],
    }
