from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator
from app.auth import authenticate, create_token

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=200)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        value = value.strip().casefold()
        if "@" not in value:
            raise ValueError("E-mail inválido.")
        return value


@router.post("/login")
def login(payload: LoginRequest) -> dict:
    user = authenticate(payload.email, payload.password)
    if user is None:
        raise HTTPException(401, "E-mail ou senha inválidos.")
    return {
        "access_token": create_token(user),
        "token_type": "bearer",
        "user": {"id": user.id, "email": user.email},
    }


@router.get("/me")
def me(request: Request) -> dict:
    return {"id": request.state.user_id, "email": request.state.user_email}


@router.post("/logout", status_code=204)
def logout() -> Response:
    return Response(status_code=204)
