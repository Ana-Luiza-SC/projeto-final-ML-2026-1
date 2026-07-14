# Spec 015 — Catálogo de métodos e estudo sob demanda

> Idioma: Português do Brasil
> Fonte canônica: [../specs/015-study-method-catalog-and-on-demand-study.md](../specs/015-study-method-catalog-and-on-demand-study.md)
> Status da tradução: sincronizada
> Última sincronização: 2026-07-13

## Problema e objetivo

Depois que a agenda identifica o que merece atenção, o estudante inicia manualmente uma atividade quando estiver pronto. O sistema recomenda métodos de um catálogo local, versionado e auditável; o estudante pode aceitar ou substituir a recomendação. A atividade deve suportar recuperação do timer, interrupção, cancelamento e conclusão.

## Fonte canônica de conhecimento

- `backend/app/knowledge/study_methods/study_methods.json`: fonte canônica legível por máquina;
- `evidence_based_study_methods_rag.pdf`: fonte humana/auditável;
- `README.md`: guia de checksum, metadados e upsert.

JSON e PDF não podem ser incorporados na mesma coleção vetorial, pois duplicariam conteúdo/ranking. A coleção padrão usa somente `study_methods.json`, um chunk por método, com chave idempotente `document_id + method_id + schema_version`.

O serviço legado `study_strategy_catalog.py` usa ids antigos. A migração futura deve versionar APIs ou mapear `spaced_practice` → `distributed_practice` e `concrete_examples` → `worked_examples`.

## Terminologia e catálogo inicial

Métodos iniciais: `retrieval_practice`, `distributed_practice`, `interleaving`, `worked_examples`, `self_explanation` e `pomodoro`. Método de estudo não é estilo fixo, diagnóstico ou promessa de nota. Prioridade decide **o que** estudar; recomendação de método decide **como** estudar.

## Fluxo funcional

1. O estudante escolhe uma prioridade/conteúdo e solicita iniciar estudo.
2. O backend reconstrói contexto pertencente ao usuário e consulta o JSON canônico.
3. Uma baseline determinística filtra/rankeia métodos compatíveis com tarefa, prazo, evidência e restrições.
4. O LLM, se usado, apenas explica ou seleciona entre opções válidas; saída inválida cai em fallback.
5. O frontend mostra método, razão, evidência, cuidados e permite override explícito.
6. A criação da atividade exige ação humana e registra método recomendado/escolhido separadamente.
7. Timer deve sobreviver a recarregamento por timestamps do servidor; pause/interrupção/cancelamento/conclusão são estados explícitos e idempotentes.

## Modelo e contratos

Uma atividade pertence ao usuário e disciplina/conteúdo, pode referenciar avaliação/prioridade/bloco, guarda `method_id`, fonte da recomendação, timestamps de início/pausa/fim, duração efetiva, estado e metadados mínimos. Não use duração inventada quando não houver disponibilidade/entrada. A execução real nunca é inferida de um bloco planejado.

Contratos devem permitir listar métodos, obter recomendação estruturada, iniciar, consultar, pausar/retomar, cancelar e concluir atividade. IDs, rotas, chaves JSON, enums e timestamps permanecem em inglês conforme a fonte canônica.

## Baseline, fallback e guardrails

Sem LLM, o catálogo e regras locais continuam funcionando. Nunca recomendar método desconhecido, inventar referência, prometer domínio/aprovação, diagnosticar estilo, alterar prioridade/nota/data ou persistir sem confirmação. Validar ownership, estado de transição, idempotência, conflito, payload e versão do catálogo. Logs não contêm conteúdo pessoal, prompt integral, resposta integral ou segredo.

## Frontend, observabilidade e testes

A UI diferencia recomendação/override, bloco planejado/atividade real e estados do timer; restaura atividade ativa com horário do servidor e mostra erro/fallback amigável. Registrar modo, versão, ids seguros, método recomendado/escolhido, transição e latência.

Testar carregamento/checksum/catalog ids, ranking determinístico, evidência, método desconhecido, LLM inválido, fallback, override, ownership, transições/idempotência, recuperação de timer, cancelamento/conclusão, privacidade e acessibilidade básica.

## Status e limitações

O JSON canônico, loader e recomendações do assistente existem. O ciclo persistente de atividade/timer/transições não foi encontrado no repositório; por isso o status canônico é `partial`. A Spec 016 depende desta atividade para feedback/adaptação.
