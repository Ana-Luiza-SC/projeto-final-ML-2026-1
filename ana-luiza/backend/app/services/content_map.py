from __future__ import annotations
from datetime import date, datetime, timezone
from typing import Any
from uuid import uuid4
from app import storage

MAX_DEPTH = 5
MAX_NODES = 100

class ContentMapError(ValueError): pass
class ContentMapConflict(ContentMapError): pass
class ContentMapNotFound(ContentMapError): pass

def _nodes(discipline_id: str) -> dict[str, dict]:
    return storage.CONTENT_NODES.setdefault(discipline_id, {})

def get_node(discipline_id: str, node_id: str) -> dict:
    node = _nodes(discipline_id).get(node_id)
    if not node: raise ContentMapNotFound("Conteúdo não encontrado nesta disciplina.")
    return node

def _depth(discipline_id: str, parent_id: str | None) -> int:
    depth, current, seen = 1, parent_id, set()
    while current:
        if current in seen: raise ContentMapConflict("Ciclo detectado na hierarquia.")
        seen.add(current); node = get_node(discipline_id, current); current = node.get("parent_id"); depth += 1
    return depth

def descendants(discipline_id: str, node_id: str) -> list[dict]:
    nodes, result, queue = _nodes(discipline_id), [], [node_id]
    while queue:
        parent = queue.pop(0)
        children = sorted((node for node in nodes.values() if node.get("parent_id") == parent), key=lambda n: (n["created_at"], n["title"]))
        result.extend(children); queue.extend(child["id"] for child in children)
    return result

def create_node(discipline_id: str, payload: dict[str, Any]) -> dict:
    nodes = _nodes(discipline_id)
    if len(nodes) >= MAX_NODES: raise ContentMapConflict("Limite de conteúdos da disciplina atingido.")
    parent_id = payload.get("parent_id")
    if parent_id: get_node(discipline_id, parent_id)
    if _depth(discipline_id, parent_id) > MAX_DEPTH: raise ContentMapConflict(f"Profundidade máxima de {MAX_DEPTH} níveis excedida.")
    now = datetime.now(timezone.utc)
    node = {"id": str(uuid4()), "discipline_id": discipline_id, **payload, "created_at": now}
    nodes[node["id"]] = node
    return node

def update_node(discipline_id: str, node_id: str, payload: dict[str, Any]) -> dict:
    node = get_node(discipline_id, node_id)
    parent_id = payload.get("parent_id", node.get("parent_id"))
    if parent_id == node_id: raise ContentMapConflict("Um conteúdo não pode ser seu próprio pai.")
    if parent_id:
        get_node(discipline_id, parent_id)
        if parent_id in {item["id"] for item in descendants(discipline_id, node_id)}:
            raise ContentMapConflict("A movimentação criaria um ciclo.")
    if _depth(discipline_id, parent_id) > MAX_DEPTH: raise ContentMapConflict(f"Profundidade máxima de {MAX_DEPTH} níveis excedida.")
    old = dict(node)
    node.update(payload)
    try:
        for child in descendants(discipline_id, node_id):
            if _depth(discipline_id, child.get("parent_id")) > MAX_DEPTH: raise ContentMapConflict(f"Profundidade máxima de {MAX_DEPTH} níveis excedida.")
    except ContentMapError:
        node.clear(); node.update(old); raise
    return node

def delete_node(discipline_id: str, node_id: str) -> None:
    get_node(discipline_id, node_id)
    if descendants(discipline_id, node_id): raise ContentMapConflict("Exclusão bloqueada: remova primeiro os conteúdos descendentes.")
    if any(any(selection["content_node_id"] == node_id for selection in selections) for selections in storage.ASSESSMENT_CONTENT_LINKS.values()):
        raise ContentMapConflict("Exclusão bloqueada: remova primeiro a associação com avaliações.")
    del _nodes(discipline_id)[node_id]

def tree(discipline_id: str) -> list[dict]:
    nodes = _nodes(discipline_id)
    def build(parent_id):
        return [{**node, "children": build(node["id"])} for node in sorted((n for n in nodes.values() if n.get("parent_id") == parent_id), key=lambda n: (n["created_at"], n["title"]))]
    return build(None)

def node_with_descendants(discipline_id: str, node_id: str) -> dict:
    node = get_node(discipline_id, node_id)
    def nested(current): return {**current, "children": [nested(child) for child in _nodes(discipline_id).values() if child.get("parent_id") == current["id"]]}
    return nested(node)

def set_associations(discipline_id: str, assessment_id: str, selections: list[dict]) -> dict:
    assessment = storage.get_assessment(discipline_id, assessment_id)
    if not assessment: raise ContentMapNotFound("Avaliação não encontrada nesta disciplina.")
    unique = []
    for selection in selections:
        node = get_node(discipline_id, selection["content_node_id"])
        if node["discipline_id"] != discipline_id: raise ContentMapConflict("Conteúdo e avaliação devem pertencer à mesma disciplina.")
        if selection["content_node_id"] not in {item["content_node_id"] for item in unique}: unique.append(selection)
    storage.ASSESSMENT_CONTENT_LINKS[assessment_id] = unique
    return resolve_associations(discipline_id, assessment_id)

def resolve_associations(discipline_id: str, assessment_id: str) -> dict:
    selections = storage.ASSESSMENT_CONTENT_LINKS.get(assessment_id, [])
    resolved, seen = [], set()
    ordered = sorted(selections, key=lambda item: not item.get("include_descendants", False))
    for selection in ordered:
        root = get_node(discipline_id, selection["content_node_id"])
        candidates = [(root, "direct", root["id"])]
        if selection.get("include_descendants"):
            candidates += [(item, "inherited", root["id"]) for item in descendants(discipline_id, root["id"])]
        for node, origin, ancestor_id in candidates:
            if node["id"] in seen: continue
            seen.add(node["id"])
            resolved.append({**node, "association_origin": origin, "selected_ancestor_id": ancestor_id if origin == "inherited" else None})
    return {"assessment_id": assessment_id, "selections": selections, "resolved_nodes": resolved}

def relevant_assessment_contents(discipline_id: str, assessments: list[dict]) -> list[dict]:
    result = []
    status_order = {"not_started": 0, "in_progress": 1, "studied": 2, "reviewed": 3}
    difficulty_order = {"high": 0, "medium": 1, "low": 2, None: 3}
    upcoming = []
    for assessment in assessments:
        if assessment.get("status") != "planned" or not assessment.get("date"):
            continue
        try:
            assessment_date = date.fromisoformat(str(assessment["date"]))
        except ValueError:
            continue
        if assessment_date < date.today():
            continue
        upcoming.append((assessment_date, assessment))
    for _, assessment in sorted(upcoming, key=lambda item: (item[0], item[1]["name"])):
        resolved = resolve_associations(discipline_id, assessment["id"])
        nodes = sorted(resolved["resolved_nodes"], key=lambda n: (status_order[n["status"]], difficulty_order[n.get("difficulty")], n["title"]))
        if nodes: result.append({"assessment_id": assessment["id"], "assessment_name": assessment["name"], "assessment_date": assessment.get("date"), "nodes": nodes})
    return result

def agent_content_context(discipline_id: str, assessments: list[dict]) -> dict:
    relevant = relevant_assessment_contents(discipline_id, assessments)
    prioritized, evidence, associated_ids = [], {}, set()
    for group in relevant:
        for node in group["nodes"]:
            if node["id"] in associated_ids: continue
            associated_ids.add(node["id"]); prioritized.append(node)
            if node["association_origin"] == "direct":
                evidence[node["title"]] = f'{node["title"]} foi associado diretamente à {group["assessment_name"]} e está marcado como {node["status"]}.'
            else:
                ancestor = get_node(discipline_id, node["selected_ancestor_id"])
                evidence[node["title"]] = f'{node["title"]} foi incluído por {ancestor["title"]}, associado com descendentes à {group["assessment_name"]}, e está marcado como {node["status"]}.'
    status_order = {"not_started": 0, "in_progress": 1, "studied": 2, "reviewed": 3}
    difficulty_order = {"high": 0, "medium": 1, "low": 2, None: 3}
    general = sorted((node for node in _nodes(discipline_id).values() if node["id"] not in associated_ids), key=lambda n: (status_order[n["status"]], difficulty_order[n.get("difficulty")], n["title"]))
    for node in general:
        evidence[node["title"]] = f'{node["title"]} está cadastrado sem associação a avaliação e marcado como {node["status"]}.'
    return {"tree": tree(discipline_id), "assessment_contents": relevant, "priority_nodes": prioritized + general, "evidence_by_title": evidence}
