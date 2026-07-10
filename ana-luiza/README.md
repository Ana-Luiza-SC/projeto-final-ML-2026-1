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

## Rodar com Docker

Para subir backend e frontend juntos:

```bash
docker compose up --build
```

URLs locais:

- Frontend: http://localhost:5173
- Backend health: http://localhost:8000/api/health
- Swagger: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- OpenAPI JSON: http://localhost:8000/openapi.json

O frontend em Docker é servido por nginx na porta `5173`. Durante o build, o Compose usa `VITE_API_BASE_URL=http://localhost:8000`, porque as chamadas HTTP são feitas pelo navegador fora da rede interna do Docker.

Para configurar variáveis locais, copie `.env.example` para `.env` e ajuste apenas no seu ambiente. Não commite `.env`, `.env.local` ou arquivos `*.key`.

`GOOGLE_API_KEY` é opcional. Sem essa chave, ou se a chamada ao LLM falhar, o backend continua funcionando com fallback determinístico por regras.

## Componentes curriculares do SIGAA

O backend possui uma consulta best-effort à fonte pública de componentes curriculares do SIGAA/UnB:

- Fonte pública: https://sigaa.unb.br/sigaa/public/componentes/busca_componentes.jsf
- Busca: `GET /api/sigaa/components/search?query=FGA0315`
- Associação à disciplina: `PATCH /api/disciplines/{id}/sigaa-component`

A consulta usa cache local runtime e não depende de login. Se o SIGAA estiver indisponível, se a página JSF mudar ou se o componente não for encontrado, o sistema continua funcionando com o cadastro manual da disciplina. A integração não coleta dados de estudante, não usa páginas autenticadas, não consulta taxa de reprovação e não avalia professor.


## Agente de recomendação

O agente usa Google/Gemini quando configurado com `GOOGLE_API_KEY`. Se a chave não existir, se o LLM falhar, se houver timeout ou se a resposta vier inválida, o backend usa fallback determinístico por regras.

Crie apenas `.env.example` no repositório. Não commite `.env` real.

Endpoint no Swagger:

- `POST /api/agent/study-recommendation`

## Validação

```bash
cd backend && pytest
cd frontend && npm run build
docker compose config --no-env-resolution
```

## Escopo atual

- Backend FastAPI em memória.
- Frontend React mínimo para cadastro de disciplinas, avaliações, faltas e simulação.
- Sem login, upload/parsing de PDF, calendário ou SQLite nesta fatia. Integração SIGAA limitada à fonte pública de componentes curriculares.
