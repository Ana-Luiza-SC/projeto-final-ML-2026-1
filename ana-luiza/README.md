# EstudaUnB

Plataforma MVP para estudantes da UnB organizarem disciplinas, avaliações, faltas e simulações acadêmicas por menção/frequência.

## Rodar backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

API local: http://localhost:8000

Swagger: http://localhost:8000/docs
ReDoc: http://localhost:8000/redoc
OpenAPI JSON: http://localhost:8000/openapi.json

## Rodar frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend local: http://localhost:5173

Para apontar para outra API, crie `frontend/.env` com:

```bash
VITE_API_BASE_URL=http://localhost:8000
```

## Agente de recomendação

O agente usa Google/Gemini quando configurado com `GOOGLE_API_KEY`. Se a chave não existir, se o LLM falhar, se houver timeout ou se a resposta vier inválida, o backend usa fallback determinístico por regras.

Crie apenas `.env.example` no repositório. Não commite `.env` real.

Endpoint no Swagger:

- `POST /api/agent/study-recommendation`

## Validação

```bash
cd backend && pytest
cd frontend && npm run build
```

## Escopo atual

- Backend FastAPI em memória.
- Frontend React mínimo para cadastro de disciplinas, avaliações, faltas e simulação.
- Sem login, LLM, scraping SIGAA, upload/parsing de PDF, calendário ou SQLite nesta fatia.
