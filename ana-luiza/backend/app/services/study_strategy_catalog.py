from __future__ import annotations
from datetime import date
from typing import Any

CATALOG_VERSION = "1.0.0"
REFERENCES = {
    "dunlosky2013": {"id": "dunlosky2013", "short_citation": "Dunlosky et al. (2013)", "title": "Improving Students’ Learning With Effective Learning Techniques", "url": "https://doi.org/10.1177/1529100612453266"},
    "roediger_karpicke2006": {"id": "roediger_karpicke2006", "short_citation": "Roediger e Karpicke (2006)", "title": "Test-Enhanced Learning: Taking Memory Tests Improves Long-Term Retention", "url": "https://doi.org/10.1111/j.1467-9280.2006.01693.x"},
}
STRATEGIES = {
    "retrieval_practice": {"id": "retrieval_practice", "name_pt": "Prática de recuperação", "description": "Recuperar o conteúdo sem consulta e conferir depois.", "allowed_actions": ["explicar sem consulta", "responder questões sem consulta", "resolver exercícios e corrigir"], "situations": ["conteúdo já estudado", "avaliação próxima"], "limitations": "Exige correção posterior; recordar erros sem conferir não é suficiente.", "reference_ids": ["dunlosky2013", "roediger_karpicke2006"]},
    "spaced_practice": {"id": "spaced_practice", "name_pt": "Prática distribuída", "description": "Retomar o mesmo conteúdo em dias diferentes quando o prazo permite.", "allowed_actions": ["separar retomadas em dias distintos"], "situations": ["há vários dias confirmados antes da avaliação"], "limitations": "Não cria tempo inexistente e não é indicada como espaçamento ideal para prova iminente.", "reference_ids": ["dunlosky2013"]},
    "interleaving": {"id": "interleaving", "name_pt": "Intercalação", "description": "Alternar problemas de conteúdos relacionados para praticar a escolha do método.", "allowed_actions": ["alternar pequenos conjuntos de exercícios relacionados"], "situations": ["vários conteúdos relacionados e sessão não muito curta"], "limitations": "Alternância excessiva pode fragmentar sessões curtas; requer conteúdos cadastrados.", "reference_ids": ["dunlosky2013"]},
    "concrete_examples": {"id": "concrete_examples", "name_pt": "Exemplos concretos ou resolvidos", "description": "Começar um conteúdo novo ou difícil acompanhando um exemplo e depois reproduzi-lo.", "allowed_actions": ["acompanhar um exemplo resolvido", "criar exemplo concreto", "refazer exemplo sem copiar"], "situations": ["conteúdo novo", "conteúdo difícil"], "limitations": "Observar o exemplo passivamente não demonstra compreensão; deve ser seguido de tentativa própria.", "reference_ids": ["dunlosky2013"]},
    "self_explanation": {"id": "self_explanation", "name_pt": "Autoexplicação", "description": "Explicar com palavras próprias cada passo, hipótese e lacuna.", "allowed_actions": ["explicar passos em voz alta ou por escrito", "comparar explicação com o material"], "situations": ["compreensão inicial", "diagnóstico de lacunas"], "limitations": "A explicação precisa ser conferida; confiança subjetiva não garante domínio.", "reference_ids": ["dunlosky2013"]},
}

def strategy_references(actions: list[dict[str, Any]]) -> list[dict[str, str]]:
    ids = {ref for action in actions for ref in action.get("reference_ids", [])}
    return [REFERENCES[key] for key in REFERENCES if key in ids]


def validate_study_actions(actions: Any) -> list[dict[str, Any]]:
    if actions is None: return []
    if not isinstance(actions, list): raise ValueError("study_actions deve ser lista")
    for action in actions:
        strategy = STRATEGIES.get(action.get("strategy_id")) if isinstance(action, dict) else None
        if not strategy: raise ValueError("Estratégia de estudo inexistente")
        if not action.get("action") or not action.get("reason") or not action.get("evidence"): raise ValueError("Ação de estudo incompleta")
        if not set(action.get("reference_ids", [])).issubset(strategy["reference_ids"]): raise ValueError("Referência não pertence à estratégia")
    return actions


def build_study_actions(discipline: dict[str, Any], topics: list[Any]) -> list[dict[str, Any]]:
    if not topics: return []
    actions: list[dict[str, Any]] = []
    def add(strategy_id: str, action: str, topic: str, reason: str, evidence: str):
        strategy = STRATEGIES[strategy_id]
        actions.append({"strategy_id": strategy_id, "action": action, "topic": topic, "estimated_minutes": None, "reason": reason, "evidence": evidence, "reference_ids": list(strategy["reference_ids"])})
    for topic in topics[:5]:
        title, difficulty, status = topic.title, topic.difficulty, topic.status
        evidence = discipline.get("content_evidence_by_title", {}).get(title) or f"Conteúdo cadastrado: {title}; dificuldade {difficulty}; estado {status}."
        if difficulty == "high" or status == "not_started":
            add("concrete_examples", f"Acompanhe um exemplo resolvido de {title}; depois refaça o procedimento sem copiar e marque onde precisou consultar.", title, "O conteúdo está novo ou difícil e precisa de compreensão inicial observável.", evidence)
            add("self_explanation", f"Explique {title} com suas palavras, passo a passo; confira o material e registre as lacunas encontradas.", title, "A autoexplicação torna explícitos passos ainda não compreendidos.", evidence)
        else:
            add("retrieval_practice", f"Tente explicar {title} sem consultar o material; depois confira e registre as lacunas.", title, "O conteúdo já foi estudado e pode ser recuperado antes da correção.", evidence)
    dated = []
    for assessment in discipline.get("assessments", []):
        if assessment.get("status") == "planned" and assessment.get("date"):
            try: dated.append((date.fromisoformat(str(assessment["date"])) - date.today()).days)
            except ValueError: pass
    days = min((value for value in dated if value >= 0), default=None)
    first = topics[0].title
    if days is not None and days >= 3:
        add("spaced_practice", f"Em dois dias diferentes em que você confirmar disponibilidade, retome {first} sem concentrar tudo na véspera.", first, "Há vários dias antes da avaliação, então as retomadas podem ser distribuídas.", f"Avaliação confirmada em {days} dias; conteúdo cadastrado: {first}.")
    elif days is not None and days <= 2:
        add("retrieval_practice", f"Faça agora uma tentativa sem consulta sobre {first}, corrija os erros e concentre a próxima tentativa nas lacunas.", first, "A avaliação está próxima; não há base para prometer espaçamento ideal.", f"Avaliação confirmada em {days} dia(s); conteúdo cadastrado: {first}.")
    if len(topics) >= 2:
        names = [topic.title for topic in topics[:3]]
        add("interleaving", f"Se estes conteúdos forem relacionados, alterne um exercício de cada um ({', '.join(names)}), corrigindo um pequeno bloco antes de trocar.", ", ".join(names), "Há vários conteúdos cadastrados; a intercalação fica condicionada à relação entre eles e blocos pequenos evitam alternância excessiva.", f"Conteúdos cadastrados: {', '.join(names)}.")
    return actions

def planner_activity(node: dict[str, Any], duration_minutes: int | None = None) -> str:
    title = node["title"]
    assessment = node.get("assessment_name")
    deadline = node.get("assessment_date")
    origin = "diretamente" if node.get("association_origin") == "direct" else "por um bloco ancestral"
    context = f" para {assessment} em {deadline}" if assessment and deadline else ""
    attempts = max(1, (duration_minutes or 30) // 20)
    if node.get("status") == "not_started":
        if node.get("difficulty") == "high":
            return f"Comece {title}{context} com um exemplo resolvido; explique cada decisão e refaça sem copiar. O conteúdo foi associado {origin}."
        return f"Construa um exemplo concreto de {title}{context}, explique os passos e confira as lacunas ao final. O vínculo foi feito {origin}."
    if node.get("status") == "in_progress":
        return f"Faça {attempts} tentativa(s) de recuperação sobre {title}{context} sem consulta; corrija os erros e retome apenas as lacunas."
    if node.get("status") == "reviewed":
        return f"Teste a retenção de {title}{context} com {attempts} questão(ões) sem consulta e registre somente os pontos que ainda falharem."
    return f"Explique {title}{context} sem consultar, resolva {attempts} exercício(s) e corrija cada erro com evidência do material."
