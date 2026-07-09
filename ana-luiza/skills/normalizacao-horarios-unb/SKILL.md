---
name: normalizacao-horarios-unb
description: Converte códigos de horário do SIGAA/UnB e tabelas semanais extraídas do atestado de matrícula em eventos estruturados de calendário.
---

# Skill: Normalização de Horários UnB

## Objetivo

Converter horários acadêmicos do SIGAA/UnB em eventos semanais estruturados.

O sistema deve lidar com:

1. Código compacto do SIGAA, como `24M12`, `24M34`, `24T23`, `24T45`.
2. Tabela de horários extraída do atestado de matrícula.

## Regras

- Usar a tabela semanal como fonte mais confiável quando ela estiver disponível.
- Agrupar linhas consecutivas da mesma disciplina no mesmo dia.
- Ignorar células `---`.
- Converter dias da semana para formato normalizado.
- Retornar `schedule: null` quando não houver horário.
- Não inventar horário ausente.

## Mapeamento de dias

- Dom -> sunday
- Seg -> monday
- Ter -> tuesday
- Qua -> wednesday
- Qui -> thursday
- Sex -> friday
- Sab -> saturday

## Exemplo de saída

```json
[
  {
    "discipline_code": "FGA0315",
    "day": "monday",
    "start_time": "10:00",
    "end_time": "11:50"
  },
  {
    "discipline_code": "FGA0315",
    "day": "wednesday",
    "start_time": "10:00",
    "end_time": "11:50"
  }
]
````

## Regras de agrupamento

Se a tabela tiver:

```text
10:00 - 10:55 FGA0315
10:55 - 11:50 FGA0315
```

o resultado deve ser:

```json
{
  "discipline_code": "FGA0315",
  "start_time": "10:00",
  "end_time": "11:50"
}
```

## Testes obrigatórios

Criar testes para:

* converter tabela semanal;
* agrupar horários consecutivos;
* ignorar `---`;
* lidar com disciplina sem horário;
* converter segunda e quarta;
* preservar horário inicial e final corretamente.
