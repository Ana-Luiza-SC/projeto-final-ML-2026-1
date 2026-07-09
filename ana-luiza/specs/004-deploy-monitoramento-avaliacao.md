# Spec 004 — Deploy, Monitoramento e Avaliação do EstudaUnB

## 1. Título

Deploy, Docker, Monitoramento e Avaliação do EstudaUnB para entrega final.

## 2. Objetivo

Preparar o EstudaUnB para a entrega do trabalho final, garantindo que o sistema seja executável, demonstrável, confiável e avaliável.

Esta fatia deve definir a estrutura de Docker/Docker Compose, variáveis de ambiente, logs seguros, monitoramento mínimo e plano de avaliação do agente, da API e da UX. O foco é transformar o MVP já implementado em um produto demonstrável de ponta a ponta.

## 3. Problema que esta fatia resolve

O projeto já possui backend FastAPI, Swagger/OpenAPI, frontend React/Vite, cálculo acadêmico determinístico e agente de recomendação com fallback por regras e integração opcional com Google/Gemini via `GOOGLE_API_KEY`.

Ainda falta padronizar como executar o sistema completo, como demonstrá-lo, como verificar sua confiabilidade e como avaliar se o agente cumpre os guardrails acadêmicos e de privacidade. Esta spec resolve essa lacuna criando um plano de deploy local, monitoramento e avaliação.

## 4. Escopo

Esta fatia deve especificar:

- Dockerfile para backend.
- Dockerfile para frontend.
- `docker-compose.yml` na raiz.
- Execução local com `docker compose up --build`.
- Backend disponível em `http://localhost:8000`.
- Frontend disponível em `http://localhost:5173` ou porta equivalente documentada.
- Swagger disponível em `http://localhost:8000/docs`.
- Frontend consumindo backend via `VITE_API_BASE_URL`.
- Variáveis de ambiente necessárias para backend, frontend e agente.
- Logs seguros para API, simulação e agente.
- Plano de avaliação do agente.
- Plano de avaliação da API.
- Plano de avaliação da UX.
- Casos extremos e guardrails.
- Roteiro de demonstração para banca ou entrega final.

## 5. Fora do escopo

- Importação real de PDF.
- Scraping real do SIGAA.
- Calendário.
- Autenticação.
- Banco persistente.
- Deploy cloud obrigatório.
- Histórico persistente de recomendações.
- Taxa de reprovação por professor.
- Avaliação de professor.
- Integração com Google Calendar.
- Treinamento ou fine-tuning de modelo.

## 6. Estratégia de deploy local

O deploy local deve priorizar reprodutibilidade e simplicidade.

Fluxo esperado:

```bash
docker compose up --build
```

Serviços esperados:

- `backend`: FastAPI em `http://localhost:8000`.
- `frontend`: React/Vite em `http://localhost:5173` ou porta equivalente.

Após subir os serviços, deve ser possível:

- Acessar o frontend.
- Ver status da API na Home.
- Acessar Swagger em `http://localhost:8000/docs`.
- Criar disciplina.
- Cadastrar faltas.
- Cadastrar avaliação.
- Ver simulação acadêmica.
- Gerar recomendação de estudo.
- Usar fallback sem `GOOGLE_API_KEY`.

## 7. Estratégia de deploy público, se aplicável

Deploy público não é obrigatório para esta fatia.

Se houver tempo, uma opção futura pode ser:

- Backend em serviço compatível com Docker.
- Frontend em serviço estático ou container separado.
- Variáveis de ambiente configuradas no provedor, nunca commitadas.
- CORS restrito ao domínio público do frontend.
- Swagger acessível apenas se apropriado para demonstração.

Regras para qualquer deploy público:

- Não expor `GOOGLE_API_KEY` no frontend.
- Não commitar `.env` real.
- Não abrir CORS irrestrito sem justificativa.
- Não armazenar PDF bruto.
- Não incluir dados pessoais reais em fixtures ou logs.

## 8. Docker e docker-compose

A implementação futura deve criar:

- `backend/Dockerfile`.
- `frontend/Dockerfile`.
- `docker-compose.yml` na raiz.

### Backend

Requisitos do container backend:

- Usar imagem Python estável.
- Instalar `backend/requirements.txt`.
- Expor porta `8000`.
- Rodar FastAPI via `uvicorn app.main:app --host 0.0.0.0 --port 8000`.
- Ler variáveis LLM do ambiente.
- Funcionar sem `GOOGLE_API_KEY` usando fallback por regras.

### Frontend

Requisitos do container frontend:

- Usar Node para build/execução do Vite ou estratégia equivalente simples.
- Expor porta `5173` ou porta equivalente documentada.
- Configurar `VITE_API_BASE_URL=http://localhost:8000` para ambiente local.
- Não receber `GOOGLE_API_KEY`, pois chave de provedor LLM é segredo do backend.

### Compose

O `docker-compose.yml` deve:

- Subir backend e frontend.
- Mapear `8000:8000` para backend.
- Mapear `5173:5173` ou equivalente para frontend.
- Passar `VITE_API_BASE_URL=http://localhost:8000` para o frontend.
- Passar variáveis LLM para o backend usando `.env` local ou valores vazios seguros.
- Não exigir `GOOGLE_API_KEY` para o sistema iniciar.

Comando ideal:

```bash
docker compose up --build
```

## 9. Variáveis de ambiente

Variáveis documentadas:

```env
LLM_PROVIDER=google
GOOGLE_API_KEY=
LLM_MODEL=gemini-2.5-flash
LLM_TIMEOUT_SECONDS=8
LLM_FALLBACK_ENABLED=true
VITE_API_BASE_URL=http://localhost:8000
```

Regras:

- Não commitar `.env` real.
- Manter `.env.example` com `GOOGLE_API_KEY` vazio.
- O sistema deve funcionar sem `GOOGLE_API_KEY` usando fallback por regras.
- O sistema não deve expor `GOOGLE_API_KEY` em logs, Swagger, frontend ou respostas de erro.
- O frontend não deve receber `GOOGLE_API_KEY`.
- O backend deve ler `GOOGLE_API_KEY` apenas do ambiente.
- Em Docker Compose, o valor pode vir de `.env` local não versionado.

## 10. Monitoramento e logs

Eventos mínimos esperados:

- `discipline_created`
- `assessment_created`
- `attendance_updated`
- `simulation_generated`
- `agent_recommendation_requested`
- `llm_called`
- `llm_failed`
- `llm_timeout`
- `fallback_used`
- `agent_recommendation_generated`

Campos esperados nos logs, quando aplicável:

- `timestamp`.
- `event`.
- `latency_ms`.
- `provider`.
- `used_fallback`.
- `error_type`.
- `status_code`.
- `discipline_id`, quando não for sensível no contexto do sistema.
- Quantidade de conteúdos pendentes.
- Nível de dedicação retornado.

Logs não podem conter:

- `GOOGLE_API_KEY`.
- Nome completo do estudante.
- Matrícula.
- PDF bruto.
- Código de verificação.
- Prompt completo com dados sensíveis.

Requisitos de implementação futura:

- Logs em formato estruturado ou semi-estruturado.
- Erros técnicos podem ser registrados sem dados pessoais.
- Respostas ao frontend devem continuar amigáveis.
- Fallback deve ser logado sem vazar prompt ou chave.

## 11. Avaliação do agente

A avaliação do agente deve usar cenários manuais controlados, sem dados pessoais reais.

Cenários mínimos:

| Caso | Situação | Verificações esperadas |
| --- | --- | --- |
| 1 | Estudante com menção projetada MM e frequência adequada | Dedicação baixa ou média; menciona situação por nota; menciona frequência; não afirma aprovação final se houver avaliações pendentes; gera ações úteis. |
| 2 | Estudante com menção projetada MS e frequência desconhecida | Não afirma aprovação final; informa frequência ausente; dedicação baixa ou média conforme pendências; recomenda registrar faltas/frequência. |
| 3 | Estudante com menção projetada MI e frequência adequada | Dedicação alta; menciona risco por nota; recomenda priorizar avaliações/conteúdos críticos. |
| 4 | Estudante com frequência abaixo de 75% | Dedicação alta; risco por falta aparece antes de conteúdo; não afirma aprovação final. |
| 5 | Estudante com nota necessária maior que 10 | Dedicação alta; alerta meta inalcançável apenas com avaliações restantes; sugere rever meta e priorizar recuperação. |
| 6 | Estudante sem avaliações cadastradas | Informa dados insuficientes; recomenda cadastrar avaliações/pesos; não inventa menção. |
| 7 | Estudante com vários conteúdos difíceis pendentes | Aumenta prioridade; recomenda começar pelos conteúdos difíceis; reasons citam pendências. |
| 8 | Ausência de `GOOGLE_API_KEY` | Usa fallback por regras; `used_fallback=true`; `provider=rules`; resposta mantém actions e reasons. |

Para cada caso, registrar:

- Dedicação recomendada.
- Se menciona risco por nota.
- Se menciona risco por falta.
- Se não afirma aprovação final indevidamente.
- Se gera ações úteis.
- Se fallback é acionado quando necessário.
- Latência aproximada.

## 12. Avaliação da API

A avaliação da API deve verificar:

- `GET /api/health` retorna status OK.
- Swagger abre em `/docs`.
- OpenAPI JSON abre em `/openapi.json`.
- Cadastro manual de disciplina funciona.
- Cadastro de avaliação funciona.
- Atualização de faltas/frequência funciona.
- Simulação acadêmica retorna menção, frequência, riscos e warnings.
- `POST /api/agent/study-recommendation` funciona com fallback sem `GOOGLE_API_KEY`.
- Entrada inválida retorna erro amigável.
- Disciplina inexistente retorna erro amigável.
- Falhas do LLM não causam erro cru quando fallback está habilitado.

Métricas mínimas:

- Latência média do endpoint do agente.
- Taxa de fallback.
- Taxa de erro da API.
- Percentual de respostas com `recommended_actions` não vazio.
- Percentual de respostas com `reasons` não vazio.
- Acerto esperado dos cenários manuais de avaliação.

## 13. Avaliação da UX

A avaliação da UX deve medir se um usuário consegue executar o fluxo principal sem ajuda técnica.

Fluxo avaliado:

1. Abrir frontend.
2. Confirmar status da API.
3. Cadastrar disciplina.
4. Abrir detalhe.
5. Inserir faltas.
6. Inserir avaliação.
7. Consultar simulação.
8. Inserir conteúdos pendentes.
9. Gerar recomendação.

Métrica mínima:

- Tempo para um usuário cadastrar disciplina, avaliação e gerar recomendação.

Critérios qualitativos:

- Mensagens de erro são amigáveis.
- Interface não mostra stack trace.
- A recomendação é apresentada como simulação.
- O sistema não afirma aprovação final quando há dados pendentes.
- Aviso de fallback é visível quando usado.
- Swagger é fácil de encontrar no roteiro de demonstração.

## 14. Casos extremos e guardrails

Testes e verificações esperadas:

- `discipline_id` inexistente.
- Entrada vazia.
- `difficulty` inválido.
- `status` inválido.
- `user_goal` muito longo.
- API do LLM indisponível.
- Timeout do LLM.
- Resposta inválida do LLM.
- Frontend com backend fora do ar.
- Tentativa de pedir avaliação de professor.
- Tentativa de pedir taxa histórica sem fonte.
- Ausência de `GOOGLE_API_KEY`.
- Conteúdos pendentes vazios.
- Frequência desconhecida.
- Frequência abaixo de 75%.
- Nota necessária maior que 10.

Guardrails obrigatórios:

- Não avaliar professor como fácil ou difícil.
- Não afirmar taxa histórica sem fonte.
- Não inventar dados do SIGAA.
- Não expor dados sensíveis.
- Não enviar `GOOGLE_API_KEY` ao frontend.
- Não registrar prompt completo com dados sensíveis.
- Não afirmar aprovação final sem nota final e frequência final.

## 15. Roteiro de demonstração

Roteiro mínimo:

1. Abrir frontend.
2. Mostrar status da API.
3. Abrir Swagger em `http://localhost:8000/docs`.
4. Criar disciplina manualmente.
5. Inserir faltas.
6. Inserir avaliação.
7. Ver simulação acadêmica com menção, frequência e riscos.
8. Inserir conteúdos pendentes.
9. Gerar recomendação de estudo.
10. Mostrar fallback funcionando sem `GOOGLE_API_KEY`.
11. Mostrar que o sistema não expõe dados sensíveis.

Demonstração sugerida para fallback:

- Rodar sem `GOOGLE_API_KEY`.
- Gerar recomendação.
- Mostrar `provider=rules` e `used_fallback=true` no painel ou resposta.
- Explicar que a recomendação continua auditável porque usa regras determinísticas e a simulação do backend.

## 16. Critérios de aceite

A spec será aceita se:

- `specs/004-deploy-monitoramento-avaliacao.md` existir.
- A spec definir Docker/Docker Compose.
- A spec definir variáveis de ambiente.
- A spec definir monitoramento/logs.
- A spec definir avaliação do agente.
- A spec definir avaliação da API.
- A spec definir avaliação da UX.
- A spec definir roteiro de demo.
- A spec preservar o fallback sem `GOOGLE_API_KEY`.
- A spec não expandir escopo para PDF, SIGAA ou calendário.

Critérios futuros de implementação:

- `docker compose up --build` sobe backend e frontend.
- Swagger continua acessível.
- Frontend consome backend pelo valor de `VITE_API_BASE_URL`.
- `.env` real não é commitado.
- `GOOGLE_API_KEY` não aparece em logs, Swagger, frontend ou erro de API.
- Avaliação mínima do agente é documentada com resultados.

## 17. Próximos passos

1. Criar `backend/Dockerfile`.
2. Criar `frontend/Dockerfile`.
3. Criar `docker-compose.yml` na raiz.
4. Revisar `.env.example` para incluir backend e frontend.
5. Adicionar logs para eventos de disciplina, avaliação, frequência e simulação.
6. Criar roteiro de avaliação manual do agente com os oito cenários mínimos.
7. Executar `docker compose up --build` e validar o roteiro de demonstração.
8. Registrar resultados de latência, fallback, erros e avaliação da UX em documentação de entrega.
