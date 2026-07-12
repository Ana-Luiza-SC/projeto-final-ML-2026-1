from uuid import UUID
from fastapi import APIRouter, HTTPException
from app import storage
from app.schemas import ContentExtractionConfirmRequest, ContentExtractionConfirmResponse, ContentExtractionPreviewResponse, AssessmentContentAssociationRequest, AssessmentContentAssociationResponse, ContentMoveRequest, ContentNodeCreate, ContentNodeRead, ContentNodeUpdate
from app.services import content_map
from app.services.content_extraction import ContentExtractionError, build_extraction_preview, confirm_extraction_preview

router = APIRouter(prefix="/api/disciplines/{discipline_id}", tags=["contents"])

def ensure_discipline(discipline_id: UUID):
    if not storage.get_discipline(str(discipline_id)): raise HTTPException(404, "Disciplina não encontrada.")

def translate(exc):
    if isinstance(exc, content_map.ContentMapNotFound): raise HTTPException(404, str(exc))
    raise HTTPException(409, str(exc))

@router.get("/contents", response_model=list[ContentNodeRead])
def list_contents(discipline_id: UUID):
    ensure_discipline(discipline_id); return content_map.tree(str(discipline_id))


@router.post("/contents/extract-preview", response_model=ContentExtractionPreviewResponse)
def extract_contents_preview(discipline_id: UUID):
    ensure_discipline(discipline_id)
    try:
        return build_extraction_preview(str(discipline_id))
    except ContentExtractionError as exc:
        raise HTTPException(422, str(exc)) from exc

@router.post("/contents/confirm-preview", response_model=ContentExtractionConfirmResponse)
def confirm_contents_preview(discipline_id: UUID, payload: ContentExtractionConfirmRequest):
    ensure_discipline(discipline_id)
    try:
        created = confirm_extraction_preview(str(discipline_id), str(payload.preview_id), payload.draft_nodes)
        return {"created_nodes": [{**node, "children": []} for node in created], "created_count": len(created)}
    except ContentExtractionError as exc:
        raise HTTPException(422, str(exc)) from exc
@router.post("/contents", response_model=ContentNodeRead, status_code=201)
def create_root(discipline_id: UUID, payload: ContentNodeCreate):
    ensure_discipline(discipline_id)
    try: return content_map.create_node(str(discipline_id), payload.model_dump(mode="json"))
    except content_map.ContentMapError as exc: translate(exc)

@router.post("/contents/{parent_id}/children", response_model=ContentNodeRead, status_code=201)
def create_child(discipline_id: UUID, parent_id: UUID, payload: ContentNodeCreate):
    ensure_discipline(discipline_id)
    data = payload.model_dump(mode="json"); data["parent_id"] = str(parent_id)
    try: return content_map.create_node(str(discipline_id), data)
    except content_map.ContentMapError as exc: translate(exc)

@router.get("/contents/{node_id}", response_model=ContentNodeRead)
def get_content(discipline_id: UUID, node_id: UUID):
    ensure_discipline(discipline_id)
    try: return content_map.node_with_descendants(str(discipline_id), str(node_id))
    except content_map.ContentMapError as exc: translate(exc)

@router.patch("/contents/{node_id}", response_model=ContentNodeRead)
def edit_content(discipline_id: UUID, node_id: UUID, payload: ContentNodeUpdate):
    ensure_discipline(discipline_id)
    data = payload.model_dump(mode="json", exclude_unset=True)
    try:
        node = content_map.update_node(str(discipline_id), str(node_id), data)
        return {**node, "children": []}
    except content_map.ContentMapError as exc: translate(exc)

@router.post("/contents/{node_id}/move", response_model=ContentNodeRead)
def move_content(discipline_id: UUID, node_id: UUID, payload: ContentMoveRequest):
    ensure_discipline(discipline_id)
    try:
        node = content_map.update_node(str(discipline_id), str(node_id), {"parent_id": str(payload.parent_id) if payload.parent_id else None})
        return {**node, "children": []}
    except content_map.ContentMapError as exc: translate(exc)

@router.delete("/contents/{node_id}", status_code=204)
def delete_content(discipline_id: UUID, node_id: UUID):
    ensure_discipline(discipline_id)
    try: content_map.delete_node(str(discipline_id), str(node_id))
    except content_map.ContentMapError as exc: translate(exc)

@router.put("/assessments/{assessment_id}/content-associations", response_model=AssessmentContentAssociationResponse)
def associate_contents(discipline_id: UUID, assessment_id: UUID, payload: AssessmentContentAssociationRequest):
    ensure_discipline(discipline_id)
    selections = [item.model_dump(mode="json") for item in payload.selections]
    try: return content_map.set_associations(str(discipline_id), str(assessment_id), selections)
    except content_map.ContentMapError as exc: translate(exc)

@router.get("/assessments/{assessment_id}/content-associations", response_model=AssessmentContentAssociationResponse)
def get_associations(discipline_id: UUID, assessment_id: UUID):
    ensure_discipline(discipline_id)
    if not storage.get_assessment(str(discipline_id), str(assessment_id)): raise HTTPException(404, "Avaliação não encontrada nesta disciplina.")
    try: return content_map.resolve_associations(str(discipline_id), str(assessment_id))
    except content_map.ContentMapError as exc: translate(exc)
