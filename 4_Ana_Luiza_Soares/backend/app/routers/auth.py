import re
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator

from app.auth import (
    DuplicateEmailError,
    authenticate,
    create_token,
    get_user,
    register_user,
    registration_enabled,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def _normalize_email(value: str) -> str:
    normalized = value.strip().casefold()
    if (
        len(normalized) > 320
        or not EMAIL_PATTERN.fullmatch(normalized)
        or normalized.startswith("@")
        or normalized.endswith("@")
    ):
        raise ValueError("E-mail inválido.")
    return normalized


class LoginRequest(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=200)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        return _normalize_email(value)


class RegistrationRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: str
    password: str = Field(min_length=8, max_length=200)
    accepted_terms: Literal[True]

    model_config = {"extra": "forbid"}

    @field_validator("name")
    @classmethod
    def valid_name(cls, value: str) -> str:
        normalized = " ".join(value.strip().split())
        if len(normalized) < 2 or any(
            ord(character) < 32 or character in "<>"
            for character in normalized
        ):
            raise ValueError("Informe um nome válido.")
        return normalized

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        return _normalize_email(value)

    @field_validator("password")
    @classmethod
    def strong_password(cls, value: str) -> str:
        if not (
            re.search(r"[A-Z]", value)
            and re.search(r"[a-z]", value)
            and re.search(r"\d", value)
        ):
            raise ValueError(
                "A senha deve conter letra maiúscula, letra minúscula e número."
            )
        return value


class AuthUserResponse(BaseModel):
    id: str
    email: str
    display_name: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    user: AuthUserResponse


class RegistrationStatusResponse(BaseModel):
    enabled: bool


def _user_response(user) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
    }


@router.get(
    "/registration-status",
    response_model=RegistrationStatusResponse,
)
def registration_status() -> dict:
    return {"enabled": registration_enabled()}


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(payload: RegistrationRequest) -> dict:
    if not registration_enabled():
        raise HTTPException(
            403,
            "O cadastro público não está disponível neste ambiente.",
        )
    try:
        user = register_user(payload.name, payload.email, payload.password)
    except DuplicateEmailError as exc:
        raise HTTPException(409, "Já existe uma conta com este e-mail.") from exc
    return {
        "access_token": create_token(user),
        "token_type": "bearer",
        "user": _user_response(user),
    }


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest) -> dict:
    user = authenticate(payload.email, payload.password)
    if user is None:
        raise HTTPException(401, "E-mail ou senha inválidos.")
    return {
        "access_token": create_token(user),
        "token_type": "bearer",
        "user": _user_response(user),
    }


@router.get("/me", response_model=AuthUserResponse)
def me(request: Request) -> dict:
    user = get_user(request.state.user_id)
    if user is None:
        raise HTTPException(401, "Sessão inválida ou expirada.")
    return _user_response(user)


@router.post("/logout", status_code=204)
def logout() -> Response:
    return Response(status_code=204)
