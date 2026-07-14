# Spec 013 — Academic Calendar, Temporal Planning, and Deployment Preparation

> Canonical language: English
> Translation: [../spec_traduzido/013-calendario-academico-planejamento-deploy.md](../spec_traduzido/013-calendario-academico-planejamento-deploy.md)
> Status: implemented
> Last reviewed: 2026-07-13

> **Relationship notice:** The separate weekly-agenda presentation and generated-session terminology were refined by Specs 017 and 018. Month and Week calendar views now display confirmed planned study blocks; planning input belongs on `/study-plan`.

## Goal

Implement the last major pre-delivery MVP iteration: persistent academic calendar, assessment events, assisted extraction of course-plan events with human review, Month/Week visualization, temporal planning corrections, demo seed, deployment preparation, and evidence documentation.

## Implemented P0 scope

- owner-isolated persistent `academic_events` entity;
- authenticated calendar CRUD;
- idempotent assessment-to-event synchronization;
- preview of events extracted from a confirmed course plan, with human confirmation before persistence;
- protected `/calendar` with Month/Week views, filters, manual creation, and extraction preview;
- weekly planning with explicit `America/Sao_Paulo` temporal reference;
- idempotent demonstration seed with Tuesday/Thursday scenario and an undated discipline;
- Docker/Render/Neon preparation through environment variables, health check, and migrations;
- targeted tests and evidence documentation.

Specs 017/018 later moved availability and planning controls to `/study-plan`, added recurrence and confirmed planned study blocks, and removed the duplicated planning agenda from `/calendar`.

## Maintained non-goals

The implementation does not include Google Calendar, Outlook, notifications, email, push, drag-and-drop, collaboration, public sharing, professor scraping, a new ML model, password recovery, or social login. Configuration-controlled public registration was added after this specification and is documented by Spec 012's evolution notice.
