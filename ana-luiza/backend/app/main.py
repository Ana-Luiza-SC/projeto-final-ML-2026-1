from __future__ import annotations

from fastapi import FastAPI
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

app = FastAPI(
    title="EstudaUnB API",
    version="0.1.0",
    description=(
        "API para organização acadêmica de estudantes da UnB, com cadastro de "
        "disciplinas, avaliações, faltas e simulação por menção/frequência."
    ),
    openapi_tags=[
        {"name": "health", "description": "Verificação de disponibilidade da API."},
        {"name": "disciplines", "description": "Cadastro e consulta de disciplinas."},
        {"name": "assessments", "description": "Cadastro de avaliações, pesos e notas."},
        {"name": "attendance", "description": "Atualização de faltas e frequência."},
        {"name": "agent", "description": "Recomendação de estudos com fallback por regras."},
        {"name": "sigaa", "description": "Consulta pública de componentes curriculares do SIGAA/UnB."},
        {"name": "study-plans", "description": "Geração determinística de planos semanais de estudo."},
        {"name": "matricula-import", "description": "Importação revisada de disciplinas por comprovante de matrícula."},
        {
            "name": "academic-simulation",
            "description": "Simulação determinística de nota, menção, frequência e riscos.",
        },
    ],
)

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


app.include_router(disciplines_router)
app.include_router(agent_router)
app.include_router(sigaa_router)
app.include_router(study_plans_router)
app.include_router(matricula_import_router)
app.include_router(course_plan_router)
app.include_router(academic_records_router)
app.include_router(discipline_assistant_router)
app.include_router(contents_router)
