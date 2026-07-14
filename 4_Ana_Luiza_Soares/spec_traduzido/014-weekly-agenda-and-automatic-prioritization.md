# Spec 014 — Agenda semanal e priorização automática de estudos

> Idioma: Português do Brasil
> Fonte canônica: [../specs/014-weekly-agenda-and-automatic-prioritization.md](../specs/014-weekly-agenda-and-automatic-prioritization.md)
> Status da tradução: sincronizada
> Última sincronização: 2026-07-13

> **Relação:** a Spec 017 substitui a direção exclusivamente não agendada por blocos planejados com preview e confirmação. A Spec 018 é canônica para a UX atual. A prioridade automática determinística continua válida.

## Problema, objetivo e escopo

O modelo de sessões geradas era rígido e podia transformar recomendação em calendário que o estudante não cumpriria. Esta spec introduziu uma agenda semanal com eventos acadêmicos confirmados, fila priorizada de itens ainda não agendados, score determinístico controlado pelo backend e explicação opcional por LLM sem autoridade sobre o score.

Abrange visão semanal, eventos/prazos, prioridade automática auditável, override do usuário sem apagar o registro autoritativo, contratos, persistência/migração, estados do frontend, autorização, observabilidade e rollout. Não abrange calendário externo, SIGAA autenticado, invenção de evidências, prioridade por LLM, criação automática de atividades de estudo, adaptação de método ou automação mensal/diária avançada.

## Terminologia

- **evento acadêmico:** item datado, como prova, trabalho, apresentação, atividade ou prazo;
- **prioridade:** ordem/urgência calculada pelo backend;
- **demanda estimada de estudo:** estimativa separada e qualificada por evidência;
- **bloco planejado:** reserva de tempo; a Spec 017 o torna persistível após confirmação;
- **atividade de estudo:** execução real, tratada pela Spec 015;
- **fallback:** caminho determinístico degradado;
- **guardrail:** validação/restrição de entrada, saída ou ação.

## Requisitos funcionais e regra determinística

O backend deve formar candidatos somente com disciplinas/conteúdos/avaliações pertencentes ao usuário, separar eventos agendados de prioridades, usar prazos futuros confirmados, estado do conteúdo, peso efetivo, risco acadêmico e evidência disponível, e retornar `priority_score`, `priority_band`, razões, `evidence_used` e `missing_evidence`. Dados ausentes produzem incerteza, nunca conclusão favorável.

O LLM pode resumir razões já calculadas. Não pode definir score, data, peso, nota, domínio, dificuldade, conteúdo ou relação. Override significa inclusão/exclusão/ordenação de apresentação, preservando score, versão do algoritmo e evidências.

Itens atrasados/bloqueados e dados insuficientes precisam de estados explícitos. Avaliações canceladas, concluídas ou passadas não governam preparação futura. A fila usa desempate estável e isolamento por usuário.

## Persistência, API e frontend

A persistência deve manter origem, vínculo com disciplina/conteúdo/avaliação, score/faixa/razão, evidências, versão e timestamps. Migração de sessões antigas não pode afirmar execução; sessões geradas podem ser mantidas como legado ou convertidas de forma auditável, sem duplicação silenciosa.

O frontend semanal apresenta eventos confirmados e prioridades separadamente, explica dados usados/ausentes, não exige prioridade numérica nem duração máxima e não cria atividade automaticamente. Estados de vazio, erro, atraso, bloqueio e falta de evidência são legíveis.

## Guardrails, observabilidade e testes

Validar ownership, enums, limites, prazos, evidência e saída estruturada. Registrar versão, contagens, latência, fallback e categorias de erro sem prompt integral, segredo ou dado pessoal. Testar cálculo/determinismo/desempate, prazos, pesos, ausência de evidência, isolamento, override, migração, LLM inválido, fallback e estados da UI.

## Compatibilidade e limitações

O endpoint legado da Spec 007 pode permanecer temporariamente, mas a UX não deve depender de `available_hours_per_week`, prioridades manuais, `max_session_minutes` ou sessões rígidas. Specs 017/018 passam a ser autoritativas para planejamento e calendário.
