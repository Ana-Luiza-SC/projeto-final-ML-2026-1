from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.schemas import (
    ContextualActionConfirmationResponse,
    ContextualAssistantRequest,
    ContextualAssistantResponse,
)
from app.services.contextual_assistant import (
    ContextualAssistantError,
    build_contextual_response,
    confirm_contextual_action,
)

router = APIRouter(prefix="/api/assistant", tags=["agent"])


@router.post(
    "/contextual/messages",
    response_model=ContextualAssistantResponse,
)
def contextual_message(payload: ContextualAssistantRequest):
    try:
        return build_contextual_response(payload)
    except ContextualAssistantError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post(
    "/actions/{action_id}/confirm",
    response_model=ContextualActionConfirmationResponse,
)
def confirm_action(action_id: UUID):
    try:
        return confirm_contextual_action(str(action_id))
    except ContextualAssistantError as exc:
        raise HTTPException(409, str(exc)) from exc
