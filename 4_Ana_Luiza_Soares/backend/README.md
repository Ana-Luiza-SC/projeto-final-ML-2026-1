# Backend EstudaUnB

Backend do EstudaUnB com FastAPI, SQLAlchemy, Alembic, autenticação, persistência acadêmica, integrações públicas e fallbacks determinísticos.

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

API publicada: https://projeto-final-ml-2026-1.onrender.com/docs

## Componentes curriculares públicos do SIGAA

Endpoints disponíveis:

- `GET /api/sigaa/components/search?query=FGA0315`
- `PATCH /api/disciplines/{id}/sigaa-component`

A fonte usada é a página pública de componentes curriculares do SIGAA/UnB: https://sigaa.unb.br/sigaa/public/componentes/busca_componentes.jsf

A implementação é best-effort porque o SIGAA usa JSF. O parser usa `requests` e `BeautifulSoup`; se a fonte pública não responder, mudar de estrutura ou não retornar o componente, a API devolve `not_found` ou `error` com warning amigável. O cadastro manual continua sendo o fallback funcional.

O cache local fica em arquivo JSON runtime ignorado pelo Git. Os testes usam fixtures HTML locais e não fazem chamada real ao SIGAA.

Esta integração não acessa área autenticada, não solicita login ou senha, não armazena dados pessoais, não consulta taxa de reprovação e não avalia professor.


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
- `GET /api/sigaa/components/search?query=FGA0315`
- `PATCH /api/disciplines/{id}/sigaa-component`

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

## Limitações atuais

- O frontend permanece separado em `../frontend`.
- O LLM é opcional; sem `GOOGLE_API_KEY`, o agente usa fallback por regras.
- A consulta SIGAA é limitada a páginas públicas e pode falhar quando o HTML/JSF mudar; cadastro manual e cache são os fallbacks.
- PDFs são processados temporariamente e dependem de revisão humana; OCR não é garantido.
- Não há sincronização com calendários externos, notificações, recuperação de senha ou login social.
- O ciclo de atividade/timer e a adaptação pós-estudo das Specs 015/016 não estão implementados.

## Persistência, autenticação e catálogo local

Os dados acadêmicos usam SQLAlchemy e `DATABASE_URL` (resolvido para `backend/data/estudaunb.db` por padrão, independentemente do diretório de execução). Execute `alembic upgrade head` antes da API. O Compose usa um volume SQLite persistente; PostgreSQL pode ser selecionado por URL sem alterar os serviços.

O cadastro público é controlado por `ALLOW_REGISTRATION`; `true`, `1`, `yes` e `on` habilitam novas contas, enquanto qualquer outro valor mantém o cadastro fechado. `GET /api/auth/registration-status` expõe somente esse estado. `POST /api/auth/register` cria usuário ativo com nome de exibição, e-mail normalizado e senha PBKDF2-SHA256, retornando o mesmo token HMAC do login. Na inicialização, `EMAIL_TESTE` e `SENHA_TESTE` continuam criando ou atualizando apenas o usuário de demonstração configurado.

A busca pública do SIGAA mantém sessão JSF/ViewState, timeout, repetição limitada e intervalo entre consultas. Resultados enriquecidos são sanitizados e gravados com upsert em `catalog_components`; disciplinas do estudante apenas referenciam/copiam os metadados acadêmicos, sem apagar avaliações ou conteúdos. `POST /api/disciplines/{id}/complexity-analysis` analisa somente a disciplina solicitada e persiste o resultado, com fallback auditável.

## Assistente contextual e ações

`POST /api/assistant/contextual/messages` reconstrói o contexto acadêmico no backend a partir de identificadores do usuário e nunca persiste uma sugestão diretamente. Ações mutáveis são enumerações explícitas, temporárias e vinculadas ao proprietário. `POST /api/assistant/actions/{action_id}/confirm` revalida preview, disciplina, conflitos e idempotência antes de criar um bloco.

As sugestões de método usam `app/knowledge/study_methods/study_methods.json`. O JSON é a fonte canônica para máquina; o PDF é evidência humana auditável e não deve ser incorporado na mesma coleção vetorial, evitando conteúdo duplicado. O endpoint contextual funciona em fallback determinístico mesmo sem provedor LLM.
