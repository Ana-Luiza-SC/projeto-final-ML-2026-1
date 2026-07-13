from __future__ import annotations
import logging, os, re, time
from app import storage
from app.services.study_recommendation_agent import generate_google_json

VERSION = "complexity-v1"
LEVELS = {"low", "medium", "high"}
logger = logging.getLogger("estudaunb.complexity")


def _evidence(text):
    sentences = [s.strip() for s in re.split(r"[.;\n]+", text) if s.strip()]
    return sentences[:3]


def _fallback(discipline):
    syllabus = (discipline.get("syllabus") or "")[:20000]
    evidence = _evidence(syllabus)
    factors = []
    if len(syllabus) > 800:
        factors.append("ementa extensa")
    technical = sum(
        syllabus.casefold().count(x)
        for x in ("algoritm", "projeto", "laborat", "matem", "prova")
    )
    if technical >= 3:
        factors.append("múltiplos elementos técnicos explícitos")
    level = "high" if len(factors) >= 2 else "medium" if factors or evidence else "low"
    return {
        "estimated_level": level,
        "confidence": 0.55 if evidence else 0.25,
        "factors": factors or ["dados acadêmicos limitados"],
        "syllabus_evidence": evidence,
        "mode": "fallback",
        "model_or_rule_version": VERSION,
        "analyzed_at": storage.utc_now(),
        "warnings": (
            []
            if evidence
            else ["Ementa indisponível; estimativa baseada em dados limitados."]
        ),
    }


def analyze(discipline_id, reanalyze=False, generator=None):
    start = time.perf_counter()
    if not reanalyze:
        cached = storage.COMPLEXITY_ANALYSES.get(discipline_id)
        if cached:
            return cached
    discipline = storage.get_discipline(discipline_id)
    if not discipline:
        raise ValueError("Disciplina não encontrada.")
    result = _fallback(discipline)
    syllabus = (discipline.get("syllabus") or "")[:20000]
    if (
        syllabus
        and os.getenv("GOOGLE_API_KEY")
        and os.getenv("LLM_PROVIDER", "google") == "google"
    ):
        prompt = (
            "Classifique apenas a complexidade estimada desta ementa. Não infira pré-requisitos nem conteúdo de prova. "
            "Retorne JSON com estimated_level low|medium|high, confidence 0..1, factors e syllabus_evidence contendo somente trechos literais fornecidos. Ementa: "
            + syllabus
        )
        try:
            raw = (generator or generate_google_json)(
                prompt, max(1, float(os.getenv("LLM_TIMEOUT_SECONDS", "8")))
            )
            level = raw.get("estimated_level")
            evidence = raw.get("syllabus_evidence", [])
            if (
                level not in LEVELS
                or not isinstance(evidence, list)
                or any(str(e) not in syllabus for e in evidence)
            ):
                raise ValueError
            result = {
                "estimated_level": level,
                "confidence": max(0, min(1, float(raw.get("confidence", 0)))),
                "factors": [str(v)[:200] for v in raw.get("factors", [])[:8]],
                "syllabus_evidence": [str(v)[:300] for v in evidence[:5]],
                "mode": "llm",
                "model_or_rule_version": os.getenv("LLM_MODEL", "gemini-2.5-flash"),
                "analyzed_at": storage.utc_now(),
                "warnings": [],
            }
        except Exception:
            result["warnings"].append(
                "A análise inteligente não pôde ser validada; foi usada a regra local."
            )
    storage.COMPLEXITY_ANALYSES[discipline_id] = result
    persisted = storage.COMPLEXITY_ANALYSES[discipline_id]
    logger.info(
        "complexity_analysis discipline_id=%s mode=%s version=%s latency_ms=%.2f evidence_count=%d",
        discipline_id,
        persisted["mode"],
        persisted["model_or_rule_version"],
        (time.perf_counter() - start) * 1000,
        len(persisted["syllabus_evidence"]),
    )
    return persisted
