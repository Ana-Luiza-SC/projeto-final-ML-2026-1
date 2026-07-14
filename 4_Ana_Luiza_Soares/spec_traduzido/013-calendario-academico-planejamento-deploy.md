# Spec 013 — Calendário acadêmico, planejamento temporal e preparação para deploy

> Idioma: Português do Brasil
> Fonte canônica: [../specs/013-calendario-academico-planejamento-deploy.md](../specs/013-calendario-academico-planejamento-deploy.md)
> Status da tradução: sincronizada
> Última sincronização: 2026-07-13

## Objetivo

Implementar a última grande iteração do MVP EstudaUnB antes da entrega: calendário acadêmico persistente, eventos de avaliações, extração assistida de eventos do plano de ensino com revisão humana, visualização mensal/semanal, correção de restrições temporais do planejamento, seed de demonstração, preparação para deploy e documentação/evidências.

## Escopo P0 implementado

- Entidade persistente `academic_events`, isolada por usuário.
- CRUD autenticado do calendário.
- Sincronização idempotente avaliação → evento.
- Preview de eventos extraídos do plano confirmado e confirmação humana antes de persistir.
- Tela protegida `/calendar` com calendário mensal, filtros, criação manual, preview de extração e agenda semanal.
- Planejamento semanal com referência temporal explícita em `America/Sao_Paulo`.
- Seed idempotente de demonstração com cenário terça/quinta e disciplina sem avaliação datada.
- Preparação de Docker/Render/Neon via variáveis de ambiente, health check e migrations.
- Testes direcionados e documentação de evidências.

## Fora do escopo mantido

Não foram implementados Google Calendar, Outlook, notificações, e-mail, push, drag-and-drop, colaboração, compartilhamento público, scraping docente, novo modelo de ML, cadastro público funcional, recuperação de senha ou login social.
