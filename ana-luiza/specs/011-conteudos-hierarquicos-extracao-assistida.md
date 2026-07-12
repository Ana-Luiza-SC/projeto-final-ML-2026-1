# Spec 011 — Conteúdos hierárquicos e extração assistida

## Problema

O projeto já possui uma árvore mínima de conteúdos, CRUD, associações com avaliações e uso no agente e no planejamento, mas a funcionalidade ainda não está documentada como uma fatia coesa. Também não existe um fluxo seguro para transformar os conteúdos de um plano de ensino confirmado em uma proposta editável: qualquer persistência automática misturaria interpretação do modelo com dados confirmados pelo estudante.

## Fluxo

1. O estudante confirma os dados estruturados do plano de ensino.
2. `POST /api/disciplines/{discipline_id}/contents/extract-preview` usa somente esses dados confirmados.
3. O agente propõe uma hierarquia; o retorno é validado e, em falha, um fallback local propõe nós raiz sem inventar relações.
4. O frontend apresenta título, descrição, pai, evidência, confiança e avisos para edição ou remoção.
5. `POST /api/disciplines/{discipline_id}/contents/confirm-preview` revalida a proposta completa.
6. Somente após confirmação humana os nós são persistidos com estado inicial `not_started`.

Cadastro manual, associação com avaliações, recomendações e planejamento permanecem disponíveis independentemente da extração.

## Arquitetura e contratos

`ContentNode` pertence a uma disciplina, referencia opcionalmente outro nó da mesma disciplina e contém título, descrição, dificuldade e estado. A árvore tem no máximo cinco níveis e cem nós por disciplina.

O preview contém `preview_id`, expiração, `draft_nodes`, `warnings`, `source`, `model`, `used_fallback` e `latency_ms`. Cada rascunho contém identificadores temporários próprios e do pai, título, descrição opcional, evidência literal curta do plano, confiança entre 0 e 1 e avisos. A confirmação recebe o `preview_id` e a lista editada. Identificadores temporários servem somente para a prévia.

A seleção de conteúdos de uma avaliação preserva os nós originalmente selecionados e resolve nós efetivos com `association_origin=direct|inherited` e `selected_ancestor_id`. Sobreposições são deduplicadas.

## Guardrails

- nenhuma extração sem plano confirmado;
- nenhuma persistência durante o preview;
- somente dados da disciplina solicitada são enviados ao agente;
- evidências precisam corresponder a trechos estruturados do plano confirmado;
- HTML, títulos vazios, referências externas, ciclos, pais ausentes e excesso de profundidade são rejeitados;
- relações inferidas não viram pré-requisitos persistentes;
- dificuldade, estado, datas e pesos não são definidos pelo modelo;
- logs registram somente IDs, contagens, provedor, modelo, latência e categoria de fallback;
- descrições, prompt e resposta integral não são registrados.

## Fallback

Sem chave, em timeout, indisponibilidade ou JSON inválido, o backend cria uma prévia local identificada usando cada item confirmado de `contents` como nó raiz. O fallback não inventa subtópicos nem relações. Se o plano não possuir conteúdos explícitos, retorna aviso amigável e lista vazia; o cadastro manual continua disponível.

## Critérios de aceitação

- aba Conteúdos visível e funcional na página da disciplina;
- CRUD manual, movimentação, limites, isolamento e exclusão segura validados;
- preview não altera `CONTENT_NODES`;
- resposta válida do agente é validada e editável;
- timeout, indisponibilidade, resposta inválida ou evidência inexistente acionam fallback identificado;
- confirmação reaplica ciclo, profundidade, quantidade, sanitização e isolamento;
- associações diretas/herdadas continuam auditáveis;
- agente e planejamento usam somente conteúdos da disciplina solicitada;
- conteúdo geral não é apresentado como conteúdo confirmado de uma avaliação;
- suíte backend, build frontend, diff e execução Docker passam.

## Estratégia de testes

Testes de API cobrem ausência de plano, fallback, LLM válido/inválido/timeout, ausência de persistência no preview, edição e confirmação, preview expirado, evidência incompatível, ciclos, pai ausente, profundidade e limite. Os testes existentes cobrem CRUD, associações, deduplicação, prioridades, agente e planejamento. O frontend é validado pelo TypeScript/Vite e por smoke test HTTP no Compose.

## Limitações

O armazenamento permanece em memória. Não há calendário, agenda, drag-and-drop, canvas, banco de dados, grafo de pré-requisitos ou integração externa adicional. A hierarquia representa organização confirmada pelo estudante, não dependência pedagógica automática.

## Evidências de validação

- testes direcionados de conteúdos, agente e planejamento: 62 aprovados;
- suíte completa do backend: 197 aprovados e 1 ignorado;
- build TypeScript/Vite local e dentro da imagem Docker: concluído;
- `git diff --check`: sem erros;
- backend e frontend no Compose: HTTP 200;
- smoke HTTP: plano confirmado, preview sem persistência, edição da hierarquia, confirmação, associação com descendentes e recomendação em fallback com evidências diretas e herdadas.
