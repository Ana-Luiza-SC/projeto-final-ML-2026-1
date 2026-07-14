# Deploy

## Render + Neon/PostgreSQL

1. Criar banco PostgreSQL externo, por exemplo Neon.
2. Criar Web Service do backend com Docker usando `backend/`.
3. Configurar variáveis: `DATABASE_URL`, `AUTH_SECRET`, `EMAIL_TESTE`, `SENHA_TESTE`, `ALLOW_REGISTRATION=false`, `CORS_ORIGINS`, opcional `GOOGLE_API_KEY`. Em `dev`, `ALLOW_REGISTRATION` é reservada e não habilita cadastro porque o endpoint não está presente.
4. Health check: `/api/health`.
5. O container executa `alembic upgrade head` no startup e usa `$PORT`.
6. Criar Static Site do frontend usando `frontend/`, build `npm ci && npm run build`, publish `dist`.
7. Configurar `VITE_API_URL` com a URL pública do backend.
8. Garantir rewrite SPA de `/*` para `/index.html`.

O arquivo `render.yaml` documenta essa separação sem incluir senha, URL real ou chave.

## Local com Docker

```bash
docker compose up --build
```

O Compose usa volume para dados locais do backend e passa `DATABASE_URL` configurável.

## Limitações

Serviços gratuitos podem ter cold start, limites de conexão e indisponibilidade temporária. O backend deve iniciar mesmo sem SIGAA e sem LLM.

Não há evidência neste branch de um deploy público concluído. Após provisionar Render/Neon, registrar smoke test, URL verificada, migrations aplicadas e política de CORS no índice de evidências.
