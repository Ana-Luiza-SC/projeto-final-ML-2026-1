---
name: calculo-notas-risco-academico
description: Calcula média parcial, menção provável, nota necessária, frequência, risco de reprovação por nota e risco de reprovação por falta segundo regras acadêmicas da UnB.
---

# Skill: Cálculo de Notas, Menções e Risco Acadêmico

## Regras mínimas

- Cálculo determinístico.
- Não usar LLM.
- Aceitar pesos em decimal ou porcentagem.
- Validar notas entre 0 e 10.
- Calcular contribuição atual.
- Calcular peso concluído.
- Calcular peso restante.
- Calcular nota necessária.
- Calcular média parcial.
- Converter nota para menção.
- Calcular frequência.
- Calcular percentual de faltas.
- Classificar risco por nota.
- Classificar risco por falta.
- Gerar situação acadêmica.

## Regras de menção

- `9.0 <= nota <= 10.0`: SS
- `7.0 <= nota < 9.0`: MS
- `5.0 <= nota < 7.0`: MM
- `3.0 <= nota < 5.0`: MI
- `0.0 < nota < 3.0`: II
- `nota == 0.0`: SR

## Regras de aprovação

- SS, MS e MM são menções de aprovação.
- MI, II e SR são menções de reprovação.
- Frequência mínima exigida: 75%.
- Frequência abaixo de 75% deve gerar risco/reprovação por falta.
- Se frequência for desconhecida, não afirmar aprovação final.
