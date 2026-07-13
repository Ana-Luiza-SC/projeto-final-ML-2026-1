---
name: pdf-atestado-matricula
description: Extrai disciplinas, atividades acadêmicas, turmas, docentes, locais, status e códigos de horário de PDFs de atestado de matrícula do SIGAA/UnB enviados pelo estudante.
---

# Skill: PDF de Atestado de Matrícula SIGAA/UnB

Esta skill será usada futuramente para orientar o parsing de PDFs de atestado de matrícula do SIGAA/UnB.

## Regras mínimas

- O parser deve separar disciplinas regulares de atividades acadêmicas.
- O parser deve lidar com a tabela principal do atestado: código, componente/docente, turma, status e horário.
- O parser deve lidar com atividade de monitoria/orientação sem horário fixo.
- O parser deve lidar com tabela semanal de horários.
- O parser nunca deve salvar automaticamente sem revisão humana.
- O parser não deve armazenar PDF bruto por padrão.
- O parser não deve registrar dados pessoais em logs.
