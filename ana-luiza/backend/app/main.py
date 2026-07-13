from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
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
from app.auth import bootstrap_test_user, decode_token, ensure_user, get_user
from app.database import current_user_id, init_database


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
    ],
)


@app.middleware("http")
async def authenticated_student_context(request: Request, call_next):
    public = request.url.path in {
        "/api/health",
        "/api/auth/login",
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


# CORS is intentionally restricted to local Vite dev origins for the MVP frontend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
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
app.include_router(disciplines_router)
app.include_router(agent_router)
app.include_router(sigaa_router)
app.include_router(study_plans_router)
app.include_router(matricula_import_router)
app.include_router(course_plan_router)
app.include_router(academic_records_router)
app.include_router(discipline_assistant_router)
app.include_router(contents_router)
