# Spec 016 — Feedback de estudo e adaptação de método

> Idioma: Português do Brasil
> Fonte canônica: [../specs/016-study-feedback-and-method-adaptation.md](../specs/016-study-feedback-and-method-adaptation.md)
> Status da tradução: sincronizada
> Última sincronização: 2026-07-13

## Problema, objetivo e princípios

Após concluir uma atividade, o estudante registra uma avaliação curta que pode melhorar recomendações futuras. A adaptação deve ser determinística, auditável e cautelosa. Não infere estilo fixo, não diagnostica e não declara método preferido após uma única atividade. Prioridade, demanda, dificuldade do estudante e ajuste de método permanecem scores separados.

## Escopo e não objetivos

Abrange feedback pós-estudo, campos mínimos, baseline de adaptação, confiança/dados insuficientes, separação entre preferência subjetiva e desempenho objetivo, persistência, APIs, frontend, guardrails, logs e testes. Exclui diagnóstico clínico/psicológico, estilos de aprendizagem fixos, adaptação somente por LLM, fusão com prioridade, previsão automática de nota, dificuldade de professor/taxa histórica e dados biométricos/de saúde.

## Terminologia e catálogo

- **feedback:** avaliação enviada pelo estudante após atividade;
- **observação comparável:** mesmo usuário, tipo de tarefa e contexto suficientemente semelhante;
- **preferência subjetiva:** foco, fadiga, eficácia percebida e adequação;
- **desempenho objetivo:** resultado mensurável/autoteste, imediato ou tardio;
- **confiança:** evidência que sustenta o ajuste;
- **dados insuficientes:** estado em que não se afirma preferência.

`method_id` deve vir do catálogo ativo da Spec 015: `retrieval_practice`, `distributed_practice`, `interleaving`, `worked_examples`, `self_explanation`, `pomodoro`. Métodos desconhecidos/retirados são rejeitados ou isolados para migração.

## Requisitos funcionais e modelo

Feedback pertence ao usuário e a uma atividade concluída, aceita escalas limitadas para foco/fadiga/eficácia/fit, comentário opcional limitado e resultado objetivo opcional com tipo/escala explícitos. Deve ser idempotente ou versionado e guardar timestamps/versão do algoritmo.

O algoritmo agrega somente observações comparáveis, usa mínimo de amostras antes de ranking, evita que uma única resposta domine, pondera recência/qualidade de forma versionada, mantém subjetivo e objetivo separados e retorna score, confiança, contagem, razões e estado `insufficient_data` quando necessário. LLM pode explicar, nunca calcular/alterar score.

## API, frontend e fallback

Contratos devem criar/consultar feedback e retornar adaptação por contexto/método com evidências agregadas, nunca dados de outro usuário. A UI aparece após conclusão, permite pular campos opcionais, explica uso do dado e apresenta incerteza. Sem LLM, baseline determinística permanece completa; sem observações comparáveis, usar ordem base do catálogo e declarar insuficiência.

## Guardrails, privacidade e observabilidade

Validar atividade concluída, ownership, método, escalas, tamanho, duplicação e compatibilidade de medidas. Não inferir saúde/traço, não prometer aprendizagem/nota, não misturar contextos incompatíveis, não expor feedback individual em logs. Registrar versão, contagens, confiança/faixa, fallback e latência sem texto livre/prompt/segredo.

## Testes e aceite

Cobrir dados insuficientes, uma observação sem preferência, mínimo configurado, separação subjetiva/objetiva, comparabilidade, recência, empate estável, método desconhecido, ownership, duplicação, escala inválida, explicação LLM inválida/fallback, privacidade e integração após atividade concluída.

## Status

Não foram encontrados modelo, rotas, UI ou testes de feedback/adaptação. A spec permanece `planned` e depende do ciclo de atividade da Spec 015.
