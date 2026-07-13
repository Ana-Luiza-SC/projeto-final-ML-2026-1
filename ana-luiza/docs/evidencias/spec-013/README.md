# Evidências — Spec 013

## Objetivo

Validar calendário acadêmico persistente, sincronização com avaliações, preview confirmado de eventos do plano, planejamento temporal, seed, build e preparação para deploy.

## Cenário testado

- Disciplina A `FGA-QS` com Prova 1 em 14/07/2026 e Prova 2 em 16/07/2026.
- Disciplina B `FGA-ML` sem avaliação datada.
- Conteúdo difícil e não iniciado.
- Conteúdo revisado.
- Associação herdada por nó pai.
- Disponibilidade demonstrável segunda, quarta e sexta.

## Comandos executados e resultados

```bash
cd backend && ./.venv/bin/pytest tests/test_course_plan_records.py tests/test_study_plan_agent.py -q
# 51 passed in 4.67s

cd backend && ./.venv/bin/pytest tests/test_academic_calendar.py -q
# 5 passed in 1.62s

cd backend && ./.venv/bin/pytest -q
# 219 passed, 1 skipped in 12.07s

cd frontend && npm run build
# tsc -b && vite build concluído com sucesso

cd backend && DATABASE_URL=sqlite:////tmp/estudaunb-empty-migration.db ./.venv/bin/alembic upgrade head
# migrations 001 e 002 aplicadas em banco vazio

cd backend && PYTHONPATH=. EMAIL_TESTE=<email-demo> SENHA_TESTE=<senha-demo> AUTH_SECRET=<segredo-local> ./.venv/bin/python scripts/seed_demo.py
# {'user': 'demo@example.invalid', 'disciplines': ['FGA-QS', 'FGA-ML'], 'events': 3}

cd backend && PYTHONPATH=. EMAIL_TESTE=<email-demo> SENHA_TESTE=<senha-demo> AUTH_SECRET=<segredo-local> ./.venv/bin/python scripts/seed_demo.py
# {'user': 'demo@example.invalid', 'disciplines': ['FGA-QS', 'FGA-ML'], 'events': 3}
```

## Evidências de persistência

- `academic_events` foi adicionada em migration não destrutiva `002_academic_calendar`.
- Seed executado duas vezes manteve 3 eventos, sem duplicação.
- Testes existentes de persistência continuam na suíte completa.

## Evidências de isolamento

- `test_calendar_routes_are_authenticated_and_isolated` valida rota protegida e que usuário 2 não lista eventos do usuário 1.

## Evidências do planejamento temporal

- Testes de planejamento cobrem prova terça/quinta, disponibilidade segunda/quarta/sexta, falta de capacidade, avaliação passada, associação herdada e LLM inválido sem poder mover sessão após prazo.
- Correção aplicada: chamadas a `next_date_for_weekday` agora recebem explicitamente a referência `local_today()` do serviço para manter política `America/Sao_Paulo`.

## Evidências de build

- `npm run build` passou com TypeScript e Vite.

## Evidências de Docker/deploy

- Arquivos atualizados: `backend/Dockerfile`, `frontend/Dockerfile`, `docker-compose.yml`, `render.yaml`, `.env.example`.
- Backend usa `$PORT`; frontend usa `VITE_API_URL`; CORS usa `CORS_ORIGINS`; startup executa migration.

```bash
docker compose config --quiet
# sem saída, exit 0

docker compose build
# ana-luiza-backend Built; ana-luiza-frontend Built

docker compose up -d
# backend e frontend Started

curl -sS -i http://localhost:8000/api/health
# HTTP/1.1 200 OK; {"status":"ok"}

curl -sS -i http://localhost:5173/
# HTTP/1.1 200 OK; HTML da SPA

docker compose exec -T backend python -c "from app.auth import ensure_user; ensure_user('<email-smoke>','<senha-smoke>', update_password=True)"
# exit 0

curl ... /api/auth/login
# login do usuário sanitizado retornou token bearer; o token não foi registrado na documentação

curl ... /api/calendar/events ... Authorization: Bearer <token>
# HTTP/1.1 200 OK; []

docker compose down
# containers e rede removidos
```

## Evidências de health check

- Endpoint público `/api/health` permanece sem autenticação e retornou HTTP 200 no container Docker.

## Limitações

- Screenshots não foram capturadas nesta execução; evidências são textuais e reproduzíveis.
- Deploy real não foi executado por ausência de credenciais Render/Neon.
- Deploy real não foi executado por ausência de credenciais Render/Neon.
