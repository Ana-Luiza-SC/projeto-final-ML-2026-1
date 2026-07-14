# Spec 012 — Persistência, autenticação restrita e catálogo acadêmico

## Problema

O armazenamento em memória perde disciplinas, avaliações, planos, faltas, conteúdos e associações ao reiniciar. As rotas acadêmicas também não possuem identidade de usuário. A consulta pública do SIGAA enriquece uma disciplina, mas ainda não há catálogo persistente separado das seleções pessoais.

## Fluxo e arquitetura

- SQLAlchemy usa `DATABASE_URL`, com SQLite local e compatibilidade futura com PostgreSQL.
- Migrações Alembic criam usuários, catálogo, disciplinas do usuário, avaliações, faltas, planos, conteúdos, associações e análises de complexidade.
- Fachadas compatíveis substituem os dicionários antigos; o banco é a única fonte de verdade acadêmica. Apenas previews com TTL permanecem temporários.
- Middleware autentica rotas acadêmicas por token assinado. Login público usa o usuário idempotente de `EMAIL_TESTE`/`SENHA_TESTE`; cadastro público fica desabilitado por padrão.
- O catálogo público recebe upsert idempotente dos componentes encontrados pelo scraper público. A seleção do estudante referencia uma cópia auditável do catálogo sem compartilhar dados pessoais.

## Contratos

- `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me`.
- `GET /api/catalog/components/{code}` e atualização sob demanda pelo fluxo SIGAA existente.
- `POST /api/disciplines/{id}/complexity-analysis` analisa somente a disciplina escolhida, persiste resultado e aceita reanálise explícita.
- Respostas acadêmicas existentes permanecem retrocompatíveis.

## Guardrails e fallback

- senhas PBKDF2 com salt; token HMAC com segredo de ambiente e expiração;
- nenhuma senha, token, prompt ou ementa integral em logs;
- isolamento obrigatório por `user_id`;
- cadastro condicionado a `ALLOW_REGISTRATION=true`;
- ementa limitada e sanitizada;
- scraper público mantém timeout, cache, retry limitado e bloqueio de autenticação;
- complexidade é estimativa, nunca dificuldade objetiva, pré-requisito ou conteúdo de prova;
- LLM inválido/indisponível usa regra local identificada.

## Arquivos locais e Git

- O SQLite local é artefato de execução e resolve de forma independente do diretório atual para `backend/data/estudaunb.db`; no Docker, `DATABASE_URL` aponta para `/data/estudaunb.db` em volume persistente.
- O Git deve ignorar explicitamente o banco principal e seus arquivos `-wal`, `-shm` e `-journal`, além dos demais bancos SQLite criados em `backend/data/`.
- `backend/data/.gitkeep` preserva somente o diretório vazio no repositório.
- As regras não podem ocultar migrações Alembic, modelos SQLAlchemy, scripts de importação, fixtures HTML sanitizadas nem `.env.example`.
- Bancos locais já criados no caminho legado `backend/estudaunb.db` e seus arquivos auxiliares também permanecem ignorados durante a transição.

## Página inicial pública e autenticação no produto

- `/` é uma landing page pública e nunca redireciona automaticamente para login ou painel.
- `/login` e `/register` são públicas; disciplinas, planejamento, importação, recomendações e demais telas acadêmicas são protegidas.
- A tentativa de abrir rota protegida sem sessão preserva o destino e leva a `/login`; após autenticação válida, o usuário retorna ao destino seguro.
- A landing apresenta propósito, dor, funcionalidades atuais, calendário futuro explicitamente identificado como planejado, guardrails, fluxo em três passos e chamadas para entrar/criar conta.
- O login oferece e-mail, senha, visibilidade da senha, validação acessível, loading e erros amigáveis; usuário autenticado em `/login` segue para a área privada.
- O cadastro consulta `GET /api/auth/registration-status` e só exibe o formulário completo quando o backend autoriza. A criação exige confirmação explícita, validação equivalente no frontend/backend e autentica automaticamente a nova conta.
- Nenhuma credencial de demonstração é embutida no bundle; o responsável pelo ambiente fornece os valores configurados por `EMAIL_TESTE` e `SENHA_TESTE`.
- Logout remove a sessão local e retorna a uma rota pública.
- Layout público reutiliza tokens e tipografia existentes, com foco visível, labels, erros associados, contraste, responsividade e ausência de overflow horizontal.

## Critérios de aceitação

- migração funciona em banco vazio;
- dados sobrevivem à reinicialização do backend;
- usuário de teste é criado/atualizado idempotentemente;
- rotas acadêmicas exigem sessão e isolam usuários;
- catálogo e ementa persistem por upsert;
- visão geral mostra ementa, origem e sincronização;
- análise ocorre somente sob demanda e é reutilizada até reanálise;
- banco SQLite e arquivos auxiliares de runtime não aparecem no status do Git;
- landing pública, login e cadastro são acessíveis por `/`, `/login` e `/register`;
- cadastro desabilitado não exibe o formulário completo; quando habilitado, cria usuário isolado sem persistir senha em texto puro;
- rotas acadêmicas redirecionam visitantes para login e restauram o destino após autenticação;
- scraper é testado apenas com fixtures;
- suíte, frontend, Compose e smoke autenticado passam.

## Limitações

Sem recuperação de senha, login social, rate limiting distribuído, sincronização integral no startup ou análise em lote do catálogo. O cadastro público pode ser desativado por ambiente.

## Evidências de validação

- Alembic `001_persistence_catalog` aplicado com sucesso em SQLite vazio em `/tmp`.
- Caminho padrão verificado tanto da raiz quanto de `backend/`: `backend/data/estudaunb.db`.
- `git status --ignored` identifica `backend/data/estudaunb.db` como ignorado e `backend/data/.gitkeep` como rastreável; regras equivalentes cobrem `-wal`, `-shm` e `-journal`.
- Migrações, modelos SQLAlchemy, fixtures sanitizadas e `.env.example` permanecem rastreados.
- Testes direcionados de autenticação, persistência, catálogo, complexidade, conteúdos e SIGAA: aprovados; a suíte principal usa fixtures sanitizadas e não depende da rede pública.
- Suíte completa do backend: `214 passed, 1 skipped`.
- Build TypeScript/Vite: concluído, 48 módulos transformados.
- `git diff --check` e `docker compose config --quiet`: sem erros.
- Docker Compose: imagens backend/frontend construídas; migração executada; health backend e HTTP frontend retornaram 200.
- Smoke público: `/`, `/login`, `/register` e o fallback SPA de `/disciplines` retornaram HTTP 200 pelo nginx.
- Login e cadastro habilitado retornam token pelo mesmo fluxo; testes do `RegisterPage` cobrem loading, estados habilitado/desabilitado, sucesso, duplicidade, erro de rede e submissão única.
- Bundle produzido não contém nomes/valores de credenciais de demonstração.
- Smoke autenticado: criação retornou 201; disciplina, carga horária e ementa continuaram disponíveis com HTTP 200 após reiniciar o backend.

A validação visual interativa foi limitada ao build e aos smokes HTTP porque o ambiente não possui navegador headless. Landing, autenticação e cadastro foram validados por tipos/build, contratos estáticos e login real da API; desktop, viewport móvel e redirecionamentos executados pelo browser ainda requerem inspeção manual.
