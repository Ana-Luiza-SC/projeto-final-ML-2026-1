from __future__ import annotations

import os
from contextlib import asynccontextmanager
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.routers.agent import router as agent_router
from app.routers.disciplines import router as disciplines_router
from app.routers.sigaa import router as sigaa_router
from app.routers.study_plans import router as study_plans_router
from app.routers.matricula_import import router as matricula_import_router
from app.routers.course_plan import router as course_plan_router
from app.routers.academic_records import router as academic_records_router
from app.routers.discipline_assistant import router as discipline_assistant_router
from app.routers.contents import router as contents_router
from app.routers.auth import router as auth_router
from app.routers.catalog import router as catalog_router
from app.routers.calendar import router as calendar_router
from app.routers.contextual_assistant import router as contextual_assistant_router
from app.auth import bootstrap_test_user, decode_token, ensure_user, get_user
from app.database import current_user_id, init_database

REGISTRATION_MAX_BODY_BYTES = 16 * 1024


class RegistrationRequestGuard:
    def __init__(self, app):
        self.app = app

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Callable[[], Awaitable[dict[str, Any]]],
        send: Callable[[dict[str, Any]], Awaitable[None]],
    ):
        if (
            scope["type"] != "http"
            or scope.get("path") != "/api/auth/register"
            or scope.get("method") != "POST"
        ):
            await self.app(scope, receive, send)
            return
        headers = {
            key.decode("latin-1").casefold(): value.decode("latin-1")
            for key, value in scope.get("headers", [])
        }
        if headers.get("content-type", "").split(";", 1)[0].strip().casefold() != (
            "application/json"
        ):
            await JSONResponse(
                status_code=415,
                content={"detail": "Envie os dados como application/json."},
            )(scope, receive, send)
            return
        content_length = headers.get("content-length")
        if content_length and content_length.isdigit():
            if int(content_length) > REGISTRATION_MAX_BODY_BYTES:
                await JSONResponse(
                    status_code=413,
                    content={"detail": "Os dados de cadastro excedem o limite permitido."},
                )(scope, receive, send)
                return
        messages = []
        total = 0
        while True:
            message = await receive()
            messages.append(message)
            if message.get("type") == "http.request":
                total += len(message.get("body", b""))
                if total > REGISTRATION_MAX_BODY_BYTES:
                    await JSONResponse(
                        status_code=413,
                        content={
                            "detail": "Os dados de cadastro excedem o limite permitido."
                        },
                    )(scope, receive, send)
                    return
                if not message.get("more_body", False):
                    break
            elif message.get("type") == "http.disconnect":
                return
        position = 0

        async def replay():
            nonlocal position
            if position < len(messages):
                message = messages[position]
                position += 1
                return message
            return {"type": "http.request", "body": b"", "more_body": False}

        await self.app(scope, replay, send)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_database()
    bootstrap_test_user()
    yield


app = FastAPI(
    title="EstudaUnB API",
    version="0.1.0",
    description=(
        "API para organização acadêmica de estudantes da UnB, com cadastro de "
        "disciplinas, avaliações, faltas e simulação por menção/frequência."
    ),
    lifespan=lifespan,
    openapi_tags=[
        {"name": "health", "description": "Verificação de disponibilidade da API."},
        {"name": "disciplines", "description": "Cadastro e consulta de disciplinas."},
        {
            "name": "assessments",
            "description": "Cadastro de avaliações, pesos e notas.",
        },
        {"name": "attendance", "description": "Atualização de faltas e frequência."},
        {
            "name": "agent",
            "description": "Recomendação de estudos com fallback por regras.",
        },
        {
            "name": "sigaa",
            "description": "Consulta pública de componentes curriculares do SIGAA/UnB.",
        },
        {
            "name": "study-plans",
            "description": "Geração determinística de planos semanais de estudo.",
        },
        {
            "name": "matricula-import",
            "description": "Importação revisada de disciplinas por comprovante de matrícula.",
        },
        {
            "name": "academic-simulation",
            "description": "Simulação determinística de nota, menção, frequência e riscos.",
        },
        {
            "name": "calendar",
            "description": "Calendário acadêmico, eventos extraídos do plano e agenda semanal.",
        },
    ],
)


@app.exception_handler(RequestValidationError)
async def safe_request_validation_error(
    _request: Request,
    exc: RequestValidationError,
):
    details = []
    for error in exc.errors():
        safe_error = {
            key: value
            for key, value in error.items()
            if key not in {"input", "ctx"}
        }
        details.append(safe_error)
    return JSONResponse(status_code=422, content={"detail": details})


@app.middleware("http")
async def authenticated_student_context(request: Request, call_next):
    public = request.url.path in {
        "/api/health",
        "/api/auth/login",
        "/api/auth/register",
        "/api/auth/registration-status",
        "/docs",
        "/redoc",
        "/openapi.json",
    }
    token = None
    if not public:
        authorization = request.headers.get("authorization", "")
        if authorization.lower().startswith("bearer "):
            token = authorization.split(" ", 1)[1]
        elif (
            os.getenv("PYTEST_CURRENT_TEST")
            and os.getenv("AUTH_REQUIRED_IN_TESTS") != "true"
        ):
            user = ensure_user(
                "pytest@local.invalid",
                "pytest-only-password",
                user_id="local-test-user",
            )
            payload = {"sub": user.id, "email": user.email}
        else:
            return JSONResponse(
                status_code=401,
                content={"detail": "Faça login para acessar seus dados acadêmicos."},
            )
        if token:
            try:
                payload = decode_token(token)
            except Exception as exc:
                if hasattr(exc, "status_code"):
                    return JSONResponse(
                        status_code=exc.status_code, content={"detail": exc.detail}
                    )
                raise
            user = get_user(payload["sub"])
            if user is None or not user.is_active:
                return JSONResponse(
                    status_code=401, content={"detail": "Sessão inválida ou expirada."}
                )
        request.state.user_id, request.state.user_email = (
            payload["sub"],
            payload["email"],
        )
        context_token = current_user_id.set(payload["sub"])
    else:
        request.state.user_id = request.state.user_email = None
        context_token = None
    try:
        return await call_next(request)
    finally:
        if context_token is not None:
            current_user_id.reset(context_token)


def _cors_origins() -> list[str]:
    raw = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    return [item.strip() for item in raw.split(",") if item.strip()]


app.add_middleware(RegistrationRequestGuard)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get(
    "/api/health",
    tags=["health"],
    summary="Verifica status da API",
    description="Retorna status simples para o frontend confirmar que a API está disponível.",
)
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(auth_router)
app.include_router(catalog_router)
app.include_router(calendar_router)
app.include_router(disciplines_router)
app.include_router(agent_router)
app.include_router(sigaa_router)
app.include_router(study_plans_router)
app.include_router(matricula_import_router)
app.include_router(course_plan_router)
app.include_router(academic_records_router)
app.include_router(discipline_assistant_router)
app.include_router(contextual_assistant_router)
app.include_router(contents_router)
