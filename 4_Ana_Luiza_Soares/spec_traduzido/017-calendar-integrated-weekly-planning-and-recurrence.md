# Spec 017 — Planejamento semanal integrado ao calendário e recorrência

> Idioma: Português do Brasil
> Fonte canônica: [../specs/017-calendar-integrated-weekly-planning-and-recurrence.md](../specs/017-calendar-integrated-weekly-planning-and-recurrence.md)
> Status da tradução: sincronizada
> Última sincronização: 2026-07-13

> **Relação:** a Spec 018 refina a arquitetura de informação e explicações, preservando contratos de bloco planejado, recorrência, confirmação e calendário.

## Problema e objetivo

A UX misturava prioridade manual, sessões geradas talvez não persistidas e calendário mensal com agenda semanal duplicada. Esta spec substitui sessões rígidas por blocos planejados integrados ao calendário e adiciona recorrência a eventos acadêmicos manuais, mantendo distinção: prioridade decide ordem; bloco reserva tempo; atividade registra execução.

## Escopo e não objetivos

Abrange disponibilidade por dia/janela, total derivado pelo backend, prioridade automática, preview/confirmação de blocos, persistência como eventos, visões Month/Week sem agenda duplicada, recorrência manual, API/migração/frontend/guardrails/testes. Exclui calendário externo, SIGAA autenticado, prioridade/datas/notas inventadas por LLM, criação automática de atividade real, Pomodoro para geração, recorrência infinita de blocos e métodos/timers/feedback das Specs 015/016.

## Fluxo canônico

1. Estudante informa janelas de disponibilidade para a semana em `America/Sao_Paulo`.
2. Backend valida sobreposição/limites e deriva minutos totais; não pede horas semanais duplicadas.
3. Backend ranqueia prioridades determinísticas e demanda estimada com evidência/ausências separadas.
4. Alocador remove conflitos com eventos, respeita prazos futuros e blocos mínimos, podendo alocar vários blocos por disciplina.
5. Preview retorna `study_plan_id`, semana, disponibilidade, `ranked_priorities`, `planned_blocks`, `unallocated_priorities`, `capacity_analysis`, conflitos, warnings, versão e timestamp.
6. Nada persiste até confirmação explícita.
7. Confirmação revalida ownership, expiração, conflitos, disciplina, prazo e idempotência; persiste `event_type=study_block`, `origin=study_plan`, `state=planned`.

## Capacidade, prioridade e guardrails

Prioridade é backend-owned; usuário pode incluir/excluir, não fornecer score numérico. Demanda desconhecida permanece desconhecida. Análise de capacidade expõe minutos solicitados/alocados/restantes/disponíveis/usáveis/bloqueados, alocados a prioridades maiores, mínimo útil, prazo, `reason_code` e eventos bloqueadores. Avaliações passadas/concluídas não governam preparação nem podem consumir cursor compartilhado e bloquear outras prioridades.

Nenhum LLM altera score, janela, bloco, conflito ou prazo. Não gerar bloco após prazo, no passado, fora da disponibilidade ou sobre evento. Revalidar na confirmação e retornar conflito introduzido depois do preview.

## Calendário e recorrência

`/calendar` oferece Month e Week temporal e não contém formulário duplicado de planejamento. Eventos manuais aceitam recorrência finita `daily`, `weekly`, `biweekly`/intervalo e `custom_weekly`, weekdays e término por data/contagem. Armazenar regra/serie e expandir ocorrências na consulta sem materialização infinita. Eventos de avaliação continuam projeções da avaliação; blocos de estudo não podem ser criados manualmente como evento comum.

## Persistência, compatibilidade e UX

Preservar eventos e API legados. Blocos antigos não comprovam execução. A rota `/study-plan` concentra janelas, prioridades, capacidade, preview e confirmação; o calendário apenas visualiza/gerencia eventos. Mostrar timezone, duração derivada, razões/evidências, pendências e estados de loading/erro/expiração/conflito.

## Observabilidade, testes e aceite

Registrar versão, contagens, minutos, conflitos, razões, confirmação/idempotência, recorrência expandida e latência sem conteúdo sensível. Testar resumo/sobreposição, prioridade, múltiplos blocos, conflito/prazo, capacidade parcial, preview sem persistência, confirmação/revalidação/idempotência/isolamento, expansão recorrente finita, Month/Week e ausência de agenda duplicada. A implementação atual possui serviços, UI e testes correspondentes.
