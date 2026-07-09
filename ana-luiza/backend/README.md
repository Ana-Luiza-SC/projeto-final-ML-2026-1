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
- Sem frontend.
- Sem autenticação.
- Sem LLM.
- Sem scraping real do SIGAA.
- Sem parsing real de PDF.
- Sem calendário.
