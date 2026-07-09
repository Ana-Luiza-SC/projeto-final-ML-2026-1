---
name: normalizacao-horarios-unb
description: Converte códigos de horário do SIGAA/UnB e tabelas semanais extraídas do atestado de matrícula em eventos estruturados de calendário.
---

# Skill: Normalização de Horários UnB

## Regras mínimas

- Converter horários compactos como `24M12`, `24M34`, `24T23` e `24T45`.
- Usar tabela semanal como fonte preferencial quando disponível.
- Agrupar horários consecutivos da mesma disciplina.
- Ignorar células vazias ou `---`.
- Não inventar horário ausente.
