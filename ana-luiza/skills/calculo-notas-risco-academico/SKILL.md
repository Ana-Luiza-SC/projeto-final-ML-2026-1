---
name: calculo-notas-risco-academico
description: Calcula média parcial, menção provável, nota necessária, frequência, risco de reprovação por nota e risco de reprovação por falta segundo regras acadêmicas da UnB.
---

# Skill: Cálculo de Notas, Menções e Risco Acadêmico

## Objetivo

Implementar cálculos determinísticos de desempenho acadêmico para disciplinas da UnB.

Esta skill não deve usar LLM. O cálculo precisa ser previsível, testável e auditável.

O sistema deve calcular:

- média numérica parcial;
- contribuição atual;
- peso concluído;
- peso restante;
- nota necessária nas avaliações restantes;
- menção atual ou provável;
- frequência;
- percentual de faltas;
- risco de reprovação por nota;
- risco de reprovação por falta;
- situação acadêmica resumida.

## Regras acadêmicas da UnB

A UnB utiliza menções em vez de apenas nota final numérica.

Faixas de menção:

- SS: 9,0 a 10,0
- MS: 7,0 a 8,9
- MM: 5,0 a 6,9
- MI: 3,0 a 4,9
- II: 0,1 a 2,9
- SR: 0,0 ou reprovação por falta/sem rendimento

Menções de aprovação:

- SS
- MS
- MM

Menções de reprovação:

- MI
- II
- SR

Regra de frequência:

- O estudante precisa ter frequência mínima de 75%.
- Se a frequência for inferior a 75%, há risco/reprovação por falta.
- Em termos de faltas, isso equivale a ultrapassar 25% de faltas.

## Entradas

- avaliações;
- peso de cada avaliação;
- nota recebida, se houver;
- média alvo;
- carga horária total da disciplina, se disponível;
- total de encontros/aulas, se disponível;
- faltas registradas pelo estudante;
- data da próxima avaliação, se houver;
- conteúdos associados, se houver.

## Campos de avaliação

Cada avaliação deve conter:

- name
- weight
- grade
- date
- topics

## Campos de frequência

A disciplina deve conter pelo menos uma das opções:

### Opção A — por carga horária

- total_class_hours
- missed_class_hours

### Opção B — por encontros/aulas

- total_classes
- missed_classes

Se nenhum desses dados existir, o sistema deve retornar frequência como `unknown`.

## Regras para pesos

- Aceitar pesos em decimal ou porcentagem.
- Normalizar pesos quando necessário.
- Validar pesos positivos.
- Alertar se a soma dos pesos for diferente de 100%.
- Não inventar peso ausente.

## Regras para notas

- Validar notas entre 0 e 10.
- Não inventar nota futura.
- Chamar o resultado de simulação, não de previsão estatística.
- Se a nota ainda não existe, usar `null`.

## Fórmulas de nota

Contribuição atual:

```text
contribuicao_atual = soma(nota * peso)
````

Peso concluído:

```text
peso_concluido = soma(pesos com nota)
```

Peso restante:

```text
peso_restante = 1 - peso_concluido
```

Nota média necessária nas avaliações restantes:

```text
necessaria_restante = (media_alvo - contribuicao_atual) / peso_restante
```

Média parcial ponderada apenas das avaliações concluídas:

```text
media_parcial = contribuicao_atual / peso_concluido
```

## Fórmulas de frequência

Quando usar carga horária:

```text
percentual_faltas = missed_class_hours / total_class_hours
frequencia = 1 - percentual_faltas
```

Quando usar número de aulas/encontros:

```text
percentual_faltas = missed_classes / total_classes
frequencia = 1 - percentual_faltas
```

## Conversão de nota para menção

```text
nota >= 9.0 e nota <= 10.0 -> SS
nota >= 7.0 e nota < 9.0 -> MS
nota >= 5.0 e nota < 7.0 -> MM
nota >= 3.0 e nota < 5.0 -> MI
nota > 0.0 e nota < 3.0 -> II
nota == 0.0 -> SR
```

## Regra de aprovação

A situação deve considerar nota e frequência.

Aprovado:

```text
menção em [MM, MS, SS] e frequência >= 75%
```

Reprovado por nota:

```text
menção em [MI, II, SR] e frequência >= 75%
```

Reprovado por falta:

```text
frequência < 75%
```

Atenção:

* Se a frequência for menor que 75%, a situação deve destacar risco ou reprovação por falta, mesmo que a nota esteja alta.
* Se a frequência ainda for desconhecida, não afirmar aprovação final.
* Se a nota final ainda não existir, retornar situação como simulação ou risco, não como resultado final.

## Classificação de risco por nota

Risco baixo:

```text
necessaria_restante <= 6.0
```

Risco médio:

```text
6.0 < necessaria_restante <= 8.0
```

Risco alto:

```text
necessaria_restante > 8.0
```

Casos especiais:

* Se a meta já foi atingida e ainda há peso restante, risco baixo.
* Se não há peso restante e a meta não foi atingida, risco alto.
* Se não há avaliações cadastradas, retornar dados insuficientes.
* Se a nota necessária restante for maior que 10, indicar que a meta não é alcançável apenas pelas avaliações restantes.

## Classificação de risco por falta

Risco baixo:

```text
percentual_faltas <= 15%
```

Risco médio:

```text
15% < percentual_faltas <= 25%
```

Risco alto:

```text
percentual_faltas > 25%
```

Atenção:

* A fronteira institucional deve ser tratada como frequência mínima de 75%.
* Portanto, o sistema deve considerar reprovação por falta quando frequência < 75%.
* Se o percentual de faltas estiver próximo de 25%, exibir alerta preventivo.
* Se os dados de frequência forem desconhecidos, retornar `attendance_status: "unknown"`.

## Saída esperada

```json
{
  "current_contribution": 5.3,
  "partial_average": 7.57,
  "completed_weight": 0.7,
  "remaining_weight": 0.3,
  "target_average": 6.0,
  "required_average_on_remaining": 2.34,
  "current_mention": "MS",
  "projected_mention": "MM",
  "grade_risk_level": "low",
  "attendance": {
    "status": "known",
    "frequency_percentage": 87.5,
    "absence_percentage": 12.5,
    "missed_classes": 4,
    "total_classes": 32,
    "attendance_risk_level": "low",
    "risk_of_failure_by_absence": false
  },
  "academic_status": {
    "status": "on_track",
    "reasons": [
      "Menção projetada suficiente para aprovação.",
      "Frequência acima do mínimo de 75%."
    ]
  },
  "warnings": []
}
```

## Situações acadêmicas possíveis

* `on_track`: situação adequada no momento.
* `grade_risk`: risco por nota.
* `attendance_risk`: risco por falta.
* `grade_and_attendance_risk`: risco por nota e falta.
* `failed_by_grade`: reprovado por nota, quando não há avaliações restantes.
* `failed_by_attendance`: reprovado por falta.
* `insufficient_data`: dados insuficientes.

## Testes obrigatórios

Criar testes para:

* pesos em decimal;
* pesos em porcentagem;
* nota necessária baixa;
* nota necessária alta;
* meta já atingida;
* nota necessária maior que 10;
* sem avaliações;
* pesos somando mais de 100%;
* nota inválida;
* peso inválido;
* conversão de nota para SS;
* conversão de nota para MS;
* conversão de nota para MM;
* conversão de nota para MI;
* conversão de nota para II;
* conversão de nota zero para SR;
* aprovação com MM e frequência >= 75%;
* reprovação por nota com MI;
* reprovação por falta com frequência < 75%;
* frequência desconhecida;
* alerta quando faltas se aproximam de 25%.
