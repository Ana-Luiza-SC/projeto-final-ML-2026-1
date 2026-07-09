# Backend EstudaUnB

Backend inicial do MVP EstudaUnB com FastAPI e armazenamento em memória.

## Instalação

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Rodar a API

```bash
cd backend
uvicorn app.main:app --reload
```

Health check:

```bash
curl http://localhost:8000/api/health
```

## Rodar com Docker

Na raiz do projeto:

```bash
docker compose up --build
```

O serviço `backend` fica disponível em:

- API: http://localhost:8000
- Health: http://localhost:8000/api/health
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

O container lê variáveis LLM do ambiente e também pode receber `.env` local pelo Docker Compose. O arquivo `.env` é opcional e não deve ser commitado. Sem `GOOGLE_API_KEY`, o agente usa fallback por regras.

## Integração com frontend local

A API permite CORS apenas para o frontend local do Vite:

- `http://localhost:5173`
- `http://127.0.0.1:5173`

Essa lista é restrita de propósito para o MVP; não use CORS irrestrito em produção.

## Documentação OpenAPI

Com a API rodando localmente, acesse:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- OpenAPI JSON: http://localhost:8000/openapi.json

## Agente de recomendação de estudos

O backend expõe o endpoint:

- `POST /api/agent/study-recommendation`

A recomendação usa a simulação determinística de nota, menção e frequência como contexto. O agente não recalcula livremente esses valores.

Variáveis LLM previstas em `.env.example`:

```bash
LLM_PROVIDER=google
GOOGLE_API_KEY=
LLM_MODEL=gemini-2.5-flash
LLM_TIMEOUT_SECONDS=8
LLM_FALLBACK_ENABLED=true
VITE_API_BASE_URL=http://localhost:8000
```

O sistema funciona sem `GOOGLE_API_KEY`: quando a chave não existe, quando o provedor falha, quando há timeout ou quando a resposta do LLM é inválida, o backend usa fallback determinístico por regras. Não commite `.env` real.

Exemplo de request:

```bash
curl -X POST http://localhost:8000/api/agent/study-recommendation \
  -H 'Content-Type: application/json' \
  -d '{
    "discipline_id": "uuid-da-disciplina",
    "target_average": 5.0,
    "pending_topics": [
      {"title":"GQM","difficulty":"medium","status":"not_started"}
    ],
    "user_goal": "quero me organizar para a próxima semana"
  }'
```

Consulte também o Swagger: http://localhost:8000/docs

## Rodar testes

```bash
cd backend
pytest
```

## Endpoints disponíveis

- `GET /api/health`
- `POST /api/disciplines`
- `GET /api/disciplines`
- `GET /api/disciplines/{id}`
- `PATCH /api/disciplines/{id}/attendance`
- `POST /api/disciplines/{id}/assessments`
- `GET /api/disciplines/{id}/academic-simulation?target_average=5.0`

## Exemplos

Criar disciplina manualmente:

```bash
curl -X POST http://localhost:8000/api/disciplines \
  -H 'Content-Type: application/json' \
  -d '{
    "code": "FGA0000",
    "name": "Disciplina de Exemplo",
    "professor": "Docente",
    "class_code": "01",
    "schedule_code": "24M12",
    "local": "Sala 1",
    "total_classes": 30,
    "missed_classes": 2
  }'
```

Adicionar avaliação:

```bash
curl -X POST http://localhost:8000/api/disciplines/{id}/assessments \
  -H 'Content-Type: application/json' \
  -d '{"name":"P1","weight":30,"grade":8.0,"topics":["conteúdo 1"]}'
```

Simular situação acadêmica:

```bash
curl 'http://localhost:8000/api/disciplines/{id}/academic-simulation?target_average=5.0'
```

## Menções da UnB

- `SS`: 9.0 a 10.0, aprovação.
- `MS`: 7.0 a menor que 9.0, aprovação.
- `MM`: 5.0 a menor que 7.0, aprovação.
- `MI`: 3.0 a menor que 5.0, reprovação por menção.
- `II`: maior que 0.0 e menor que 3.0, reprovação por menção.
- `SR`: 0.0, reprovação.

A frequência mínima é 75%. Faltas acima de 25% indicam risco grave ou reprovação por falta, mesmo quando a nota estiver boa. Se a frequência for desconhecida, a API não afirma aprovação final.

## Limitações da primeira versão

- Armazenamento apenas em memória.
- Frontend separado em `../frontend`.
- Sem autenticação.
- LLM opcional; sem `GOOGLE_API_KEY`, o agente usa fallback por regras.
- Sem scraping real do SIGAA.
- Sem parsing real de PDF.
- Sem calendário.
